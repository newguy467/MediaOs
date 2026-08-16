"""Tdarr-style file converter API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.auth import require_permission
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ConvertJob, ConvertPreset, ConvertWatchFolder
from app.services.converter import (
    cancel_job,
    process_next_job,
    process_queue_batch,
    queue_stats,
    savings_report,
    scan_libraries,
    seed_default_presets,
    within_convert_schedule,
)

router = APIRouter(prefix="/converter", tags=["converter"],
    dependencies=[Depends(require_permission("converter.view", "converter.manage"))],
)


class PresetIn(BaseModel):
    name: str
    description: str | None = None
    video_codec: str = "libx264"
    video_crf: int = 23
    video_preset: str = "medium"
    audio_codec: str = "aac"
    audio_bitrate: str = "160k"
    container: str = "mp4"
    only_codecs: str | None = None
    skip_codecs: str | None = None
    max_height: int | None = None
    output_mode: str = "new_file"  # new_file | replace | rename_old
    output_suffix: str = ".converted"
    backup_suffix: str = ".original"
    hwaccel: str | None = "none"
    extra_args: str | None = None
    enabled: bool = True
    is_default: bool = False


class PresetOut(PresetIn):
    id: int

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: int
    source_path: str
    output_path: str | None
    preset_id: int | None
    preset_name: str | None
    status: str
    progress: float
    message: str | None
    source_codec: str | None
    source_size: int | None
    output_size: int | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    class Config:
        from_attributes = True


class ScanIn(BaseModel):
    roots: list[str] | None = None
    preset_id: int | None = None
    limit: int = 100


class EnqueueIn(BaseModel):
    path: str
    preset_id: int | None = None


@router.on_event("startup")
def _seed():
    """Seed presets + library watch folders (Tdarr-class pipeline)."""
    try:
        from app.database import SessionLocal
        from app.services.converter import seed_default_presets, seed_library_watch_folders
        db = SessionLocal()
        try:
            seed_default_presets(db)
            seed_library_watch_folders(db)
        finally:
            db.close()
    except Exception:
        pass


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    seed_default_presets(db)
    return queue_stats(db)


@router.get("/presets", response_model=list[PresetOut])
def list_presets(db: Session = Depends(get_db)):
    seed_default_presets(db)
    return db.query(ConvertPreset).order_by(ConvertPreset.name).all()


@router.post("/presets", response_model=PresetOut)
def create_preset(body: PresetIn, db: Session = Depends(get_db)):
    if db.query(ConvertPreset).filter(ConvertPreset.name == body.name).first():
        raise HTTPException(409, "Preset name exists")
    row = ConvertPreset(**body.model_dump())
    if body.is_default:
        for p in db.query(ConvertPreset).filter(ConvertPreset.is_default.is_(True)):
            p.is_default = False
            db.add(p)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/presets/{preset_id}", response_model=PresetOut)
def update_preset(preset_id: int, body: PresetIn, db: Session = Depends(get_db)):
    row = db.get(ConvertPreset, preset_id)
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    if body.is_default:
        for p in db.query(ConvertPreset).filter(ConvertPreset.is_default.is_(True), ConvertPreset.id != preset_id):
            p.is_default = False
            db.add(p)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/presets/{preset_id}", status_code=204)
def delete_preset(preset_id: int, db: Session = Depends(get_db)):
    row = db.get(ConvertPreset, preset_id)
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row)
    db.commit()


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(status: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(ConvertJob).order_by(ConvertJob.id.desc())
    if status:
        q = q.filter(ConvertJob.status == status)
    return q.limit(limit).all()


@router.post("/jobs/enqueue", response_model=JobOut)
def enqueue(body: EnqueueIn, db: Session = Depends(get_db)):
    from pathlib import Path
    from app.services.media_player import probe
    from app.services.converter import path_within_library_roots
    target = Path(body.path)
    if not path_within_library_roots(target):
        raise HTTPException(400, "path must be inside a configured library folder")
    if not target.is_file():
        raise HTTPException(404, "File not found")
    preset = db.get(ConvertPreset, body.preset_id) if body.preset_id else (
        db.query(ConvertPreset).filter(ConvertPreset.is_default.is_(True)).first()
    )
    info = probe(Path(body.path))
    job = ConvertJob(
        source_path=body.path,
        preset_id=preset.id if preset else None,
        preset_name=preset.name if preset else None,
        status="queued",
        source_codec=info.get("video_codec"),
        source_size=info.get("size"),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/scan")
def scan(body: ScanIn, db: Session = Depends(get_db)):
    seed_default_presets(db)
    return scan_libraries(db, roots=body.roots, preset_id=body.preset_id, limit=body.limit)


@router.post("/worker/tick")
def worker_tick(db: Session = Depends(get_db)):
    """Process up to max_workers jobs (also called by scheduler)."""
    results = process_queue_batch(db)
    return {"results": results, "schedule_ok": within_convert_schedule()}


@router.post("/jobs/{job_id}/cancel")
def cancel(job_id: int, db: Session = Depends(get_db)):
    ok = cancel_job(db, job_id)
    if not ok:
        raise HTTPException(400, "Cannot cancel")
    return {"ok": True}




@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: int, db: Session = Depends(get_db)):
    """Re-queue a failed or cancelled conversion job."""
    job = db.get(ConvertJob, job_id)
    if not job:
        raise HTTPException(404, "Not found")
    if job.status not in ("failed", "cancelled", "done"):
        raise HTTPException(400, f"Cannot retry status={job.status}")
    job.status = "queued"
    job.progress = 0
    if hasattr(job, "message"):
        job.message = "requeued"
    db.add(job)
    db.commit()
    return {"ok": True, "id": job_id, "status": "queued"}

@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(ConvertJob, job_id)
    if not job:
        raise HTTPException(404, "Not found")
    if job.status == "running":
        cancel_job(db, job_id)
    db.delete(job)
    db.commit()


@router.post("/jobs/clear")
def clear_jobs(status: str = "done", db: Session = Depends(get_db)):
    n = db.query(ConvertJob).filter(ConvertJob.status == status).delete()
    db.commit()
    return {"deleted": n}


@router.get("/hw")
def hardware_status():
    """Detect available NVENC / QSV / VAAPI / AMF encoders + setup wizard hints."""
    from app.services.converter import detect_hw_encoders
    from app.config import settings
    info = detect_hw_encoders()
    info["watch_folders"] = settings.converter_watch_folders or ""
    info["watch_interval_minutes"] = settings.converter_watch_interval_minutes
    info["watch_limit"] = settings.converter_watch_limit
    info["hwaccel_default"] = settings.converter_hwaccel_default
    info["amf"] = info.get("amf", False)

    # Recommended profile for the host
    if info.get("nvenc"):
        recommended = "nvidia"
    elif info.get("qsv"):
        recommended = "intel"
    elif info.get("amf") or info.get("vaapi"):
        recommended = "amd"
    else:
        recommended = "software"

    profiles = {
        "software": {
            "id": "software",
            "label": "CPU only (always works)",
            "compose": "docker compose -f docker-compose.yml up -d",
            "notes": "Use H.264 Fast / HEVC / AV1 software presets. No GPU devices required.",
        },
        "nvidia": {
            "id": "nvidia",
            "label": "NVIDIA NVENC",
            "compose": "docker compose -f docker-compose.yml -f docker-compose.nvidia.yml up -d",
            "notes": "Install host NVIDIA driver + nvidia-container-toolkit, then re-create the container.",
            "checklist": [
                "NVIDIA driver installed on host (nvidia-smi works)",
                "nvidia-container-toolkit installed",
                "Restart Docker after toolkit install",
                "Compose with docker-compose.nvidia.yml",
                "GET /api/converter/hw shows nvenc: true",
            ],
        },
        "intel": {
            "id": "intel",
            "label": "Intel Quick Sync (QSV)",
            "compose": "RENDER_GID=$(getent group render | cut -d: -f3) VIDEO_GID=$(getent group video | cut -d: -f3) \
  docker compose -f docker-compose.yml -f docker-compose.intel.yml up -d",
            "notes": "Pass /dev/dri and match render/video group IDs on the host.",
            "checklist": [
                "Intel iGPU present",
                "ls -l /dev/dri shows card* and renderD*",
                "Set RENDER_GID / VIDEO_GID from getent group",
                "Compose with docker-compose.intel.yml",
                "GET /api/converter/hw shows qsv: true",
            ],
        },
        "amd": {
            "id": "amd",
            "label": "AMD AMF / VAAPI",
            "compose": "RENDER_GID=$(getent group render | cut -d: -f3) VIDEO_GID=$(getent group video | cut -d: -f3) \
  docker compose -f docker-compose.yml -f docker-compose.amd.yml up -d",
            "notes": "AMF availability depends on the ffmpeg build; VAAPI is common on Linux.",
            "checklist": [
                "AMD GPU present",
                "ls -l /dev/dri shows devices",
                "Compose with docker-compose.amd.yml",
                "GET /api/converter/hw shows amf or vaapi encoders",
            ],
        },
    }

    info["recommended"] = recommended
    info["profiles"] = profiles
    info["docs"] = "docs/GPU.md"
    info["max_workers"] = getattr(settings, "converter_max_workers", 2)
    info["schedule_start_hour"] = getattr(settings, "converter_schedule_start_hour", None)
    info["schedule_end_hour"] = getattr(settings, "converter_schedule_end_hour", None)
    info["schedule_ok"] = within_convert_schedule()
    return info


@router.post("/watch/scan")
def watch_scan_now(db: Session = Depends(get_db)):
    from app.services.converter import watch_folder_scan
    return watch_folder_scan(db)



class WatchFolderIn(BaseModel):
    path: str
    preset_id: int | None = None
    enabled: bool = True
    recursive: bool = True
    notes: str | None = None


class WatchFolderOut(WatchFolderIn):
    id: int
    last_scan_at: datetime | None = None
    last_queued: int = 0

    class Config:
        from_attributes = True


@router.get("/watch-folders", response_model=list[WatchFolderOut])
def list_watch_folders(db: Session = Depends(get_db)):
    return db.query(ConvertWatchFolder).order_by(ConvertWatchFolder.path).all()


@router.post("/watch-folders", response_model=WatchFolderOut)
def add_watch_folder(body: WatchFolderIn, db: Session = Depends(get_db)):
    path = body.path.strip()
    if not path:
        raise HTTPException(400, "path required")
    if db.query(ConvertWatchFolder).filter(ConvertWatchFolder.path == path).first():
        raise HTTPException(409, "Folder already mapped")
    if body.preset_id and not db.get(ConvertPreset, body.preset_id):
        raise HTTPException(400, "Invalid preset_id")
    row = ConvertWatchFolder(
        path=path,
        preset_id=body.preset_id,
        enabled=body.enabled,
        recursive=body.recursive,
        notes=body.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/watch-folders/{folder_id}", response_model=WatchFolderOut)
def update_watch_folder(folder_id: int, body: WatchFolderIn, db: Session = Depends(get_db)):
    row = db.get(ConvertWatchFolder, folder_id)
    if not row:
        raise HTTPException(404, "Not found")
    row.path = body.path.strip()
    row.preset_id = body.preset_id
    row.enabled = body.enabled
    row.recursive = body.recursive
    row.notes = body.notes
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/watch-folders/{folder_id}", status_code=204)
def delete_watch_folder(folder_id: int, db: Session = Depends(get_db)):
    row = db.get(ConvertWatchFolder, folder_id)
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row)
    db.commit()



@router.get("/savings")
def savings(db: Session = Depends(get_db)):
    """Disk savings across completed conversions (HandBrake/Tdarr style)."""
    return savings_report(db)


@router.post("/seed-libraries")
def seed_libraries(db: Session = Depends(get_db), _perm: list = Depends(require_permission("settings", "library.manage"))):
    """Register MediaOS library roots as Tdarr-class watch folders."""
    from app.services.converter import seed_library_watch_folders
    return seed_library_watch_folders(db)


@router.get("/tdarr/status")
def tdarr_external_status(_perm: list = Depends(require_permission("settings", "library.manage"))):
    """Status of optional external Tdarr server (when TDARR_URL is configured)."""
    from app.clients.tdarr import tdarr_client
    return tdarr_client.status()


@router.get("/pipeline")
def converter_pipeline(db: Session = Depends(get_db)):
    """Tdarr-class pipeline summary: presets, watch folders, queue, health settings."""
    from app.config import settings
    from app.models import ConvertPreset, ConvertWatchFolder, ConvertJob
    from app.services.converter import queue_stats, detect_hw_encoders
    return {
        "mode": "native-tdarr-class",
        "health_check": bool(getattr(settings, "converter_health_check", True)),
        "max_attempts": int(getattr(settings, "converter_max_attempts", 3) or 3),
        "max_workers": int(getattr(settings, "converter_max_workers", 2) or 2),
        "auto_seed_libraries": bool(getattr(settings, "converter_auto_seed_libraries", True)),
        "external_tdarr": {
            "enabled": bool(getattr(settings, "tdarr_enabled", False)),
            "url": (getattr(settings, "tdarr_url", None) or "") or None,
        },
        "presets": db.query(ConvertPreset).count(),
        "watch_folders": db.query(ConvertWatchFolder).count(),
        "queue": queue_stats(db),
        "hw": detect_hw_encoders(),
        "failed_health": db.query(ConvertJob).filter(ConvertJob.health_ok.is_(False)).count(),
    }

