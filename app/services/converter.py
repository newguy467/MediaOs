"""Tdarr-style library file converter — queue + ffmpeg worker."""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import ConvertJob, ConvertPreset
from app.services.media_player import probe, _library_roots

log = logging.getLogger(__name__)

_worker_lock = threading.Lock()
_active_jobs: dict[int, subprocess.Popen] = {}  # job_id -> proc

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".ts", ".m2ts", ".wmv", ".flv", ".webm", ".mpg", ".mpeg"}


def _utcnow():
    return datetime.now(timezone.utc)


def ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def seed_default_presets(db: Session) -> None:
    """Insert any missing default presets (including HW) by name."""
    existing = {p.name for p in db.query(ConvertPreset).all()}
    defaults = [
        ConvertPreset(
            name="H.264 Fast (universal)",
            description="Browser/device friendly H.264 + AAC in MP4",
            video_codec="libx264",
            video_crf=23,
            video_preset="veryfast",
            audio_codec="aac",
            audio_bitrate="160k",
            container="mp4",
            skip_codecs="h264,avc",
            is_default=True,
        ),
        ConvertPreset(
            name="HEVC / x265 space saver",
            description="Smaller files, modern devices",
            video_codec="libx265",
            video_crf=28,
            video_preset="medium",
            audio_codec="aac",
            audio_bitrate="128k",
            container="mkv",
            skip_codecs="hevc,h265",
        ),
        ConvertPreset(
            name="AV1 (SVT)",
            description="Best compression — slower encode",
            video_codec="libsvtav1",
            video_crf=30,
            video_preset="6",
            audio_codec="libopus",
            audio_bitrate="96k",
            container="mkv",
            skip_codecs="av1",
        ),
        ConvertPreset(
            name="Remux to MKV (copy)",
            description="No re-encode — change container only",
            video_codec="copy",
            audio_codec="copy",
            container="mkv",
            video_crf=0,
            video_preset="ultrafast",
        ),
        ConvertPreset(
            name="NVENC H.264 (GPU)",
            description="NVIDIA hardware encode — fast, needs NVENC",
            video_codec="h264_nvenc",
            video_crf=23,
            video_preset="p4",
            audio_codec="aac",
            audio_bitrate="160k",
            container="mp4",
            skip_codecs="h264,avc",
            hwaccel="cuda",
        ),
        ConvertPreset(
            name="NVENC HEVC (GPU)",
            description="NVIDIA HEVC — space + speed",
            video_codec="hevc_nvenc",
            video_crf=28,
            video_preset="p4",
            audio_codec="aac",
            audio_bitrate="128k",
            container="mkv",
            skip_codecs="hevc,h265",
            hwaccel="cuda",
        ),
        ConvertPreset(
            name="QSV H.264 (Intel)",
            description="Intel Quick Sync H.264",
            video_codec="h264_qsv",
            video_crf=23,
            video_preset="medium",
            audio_codec="aac",
            audio_bitrate="160k",
            container="mp4",
            skip_codecs="h264,avc",
            hwaccel="qsv",
        ),
        ConvertPreset(
            name="QSV HEVC (Intel)",
            description="Intel Quick Sync HEVC",
            video_codec="hevc_qsv",
            video_crf=28,
            video_preset="medium",
            audio_codec="aac",
            audio_bitrate="128k",
            container="mkv",
            skip_codecs="hevc,h265",
            hwaccel="qsv",
        ),
        ConvertPreset(
            name="AMF H.264 (AMD)",
            description="AMD AMF hardware H.264 — needs AMD GPU + amf ffmpeg",
            video_codec="h264_amf",
            video_crf=23,
            video_preset="quality",
            audio_codec="aac",
            audio_bitrate="160k",
            container="mp4",
            skip_codecs="h264,avc",
            hwaccel="amf",
        ),
        ConvertPreset(
            name="AMF HEVC (AMD)",
            description="AMD AMF HEVC — space + GPU speed",
            video_codec="hevc_amf",
            video_crf=28,
            video_preset="quality",
            audio_codec="aac",
            audio_bitrate="128k",
            container="mkv",
            skip_codecs="hevc,h265",
            hwaccel="amf",
        ),
    ]
    added = 0
    for p in defaults:
        if p.name in existing:
            continue
        db.add(p)
        added += 1
    if added:
        db.commit()


def scan_libraries(
    db: Session,
    *,
    roots: list[str] | None = None,
    preset_id: int | None = None,
    limit: int = 200,
) -> dict:
    """Scan library roots for video files; enqueue those matching preset filters."""
    preset = None
    if preset_id:
        preset = db.get(ConvertPreset, preset_id)
    if not preset:
        preset = db.query(ConvertPreset).filter(ConvertPreset.is_default.is_(True)).first()
    if not preset:
        preset = db.query(ConvertPreset).filter(ConvertPreset.enabled.is_(True)).first()

    search_roots = [Path(r) for r in (roots or [])] or _library_roots()
    queued = 0
    scanned = 0
    skipped = 0
    existing = {
        j.source_path
        for j in db.query(ConvertJob)
        .filter(ConvertJob.status.in_(["queued", "running"]))
        .all()
    }

    for root in search_roots:
        if not root.exists():
            continue
        for dirpath, _, files in os.walk(root):
            for name in files:
                ext = Path(name).suffix.lower()
                if ext not in VIDEO_EXTS:
                    continue
                path = str(Path(dirpath) / name)
                scanned += 1
                if path in existing:
                    skipped += 1
                    continue
                if scanned > limit * 5 and queued >= limit:
                    break
                info = probe(Path(path))
                vcodec = (info.get("video_codec") or "").lower()
                if preset and not _should_convert(preset, vcodec, Path(path)):
                    skipped += 1
                    continue
                job = ConvertJob(
                    source_path=path,
                    preset_id=preset.id if preset else None,
                    preset_name=preset.name if preset else None,
                    status="queued",
                    source_codec=vcodec or None,
                    source_size=info.get("size"),
                )
                db.add(job)
                existing.add(path)
                queued += 1
                if queued >= limit:
                    break
            if queued >= limit:
                break
        if queued >= limit:
            break
    db.commit()
    return {"scanned": scanned, "queued": queued, "skipped": skipped, "preset": preset.name if preset else None}


def _should_convert(preset: ConvertPreset, vcodec: str, path: Path) -> bool:
    skip = [c.strip().lower() for c in (preset.skip_codecs or "").split(",") if c.strip()]
    only = [c.strip().lower() for c in (preset.only_codecs or "").split(",") if c.strip()]
    vc = (vcodec or "").lower()
    if skip and any(s in vc for s in skip):
        return False
    if only and not any(o in vc for o in only):
        return False
    # already has output suffix
    if preset.output_suffix and preset.output_suffix in path.stem:
        return False
    return True


def _output_path(job: ConvertJob, preset: ConvertPreset | None) -> Path:
    """Staging path while ffmpeg writes.

    Modes:
      new_file   — keep original; final = stem + output_suffix + .container
      replace    — delete original after success; final = original path (maybe new ext)
      rename_old — rename original to stem + backup_suffix + old ext; final = original path with new container
    """
    src = Path(job.source_path)
    container = (preset.container if preset else "mp4") or "mp4"
    suffix = (preset.output_suffix if preset else ".converted") or ".converted"
    mode = (preset.output_mode if preset else "new_file") or "new_file"
    if mode in ("replace", "rename_old"):
        # always stage to temp next to source
        return src.with_name(src.stem + ".mediaos-tmp." + container)
    return src.with_name(src.stem + suffix + f".{container}")


def _finalize_output(job: ConvertJob, preset: ConvertPreset | None, staged: Path) -> str:
    """Apply output_mode after a successful encode. Returns final path string."""
    src = Path(job.source_path)
    container = (preset.container if preset else "mp4") or "mp4"
    mode = (preset.output_mode if preset else "new_file") or "new_file"
    suffix = (preset.output_suffix if preset else ".converted") or ".converted"
    backup = (getattr(preset, "backup_suffix", None) if preset else None) or ".original"

    if not staged.exists():
        raise FileNotFoundError(f"Staged output missing: {staged}")

    if mode == "new_file":
        # staged path is already the final path
        return str(staged)

    # Final name: same stem as source, new container (replace / rename_old)
    final = src.with_suffix(f".{container}")
    # Avoid clobbering if container matches and we're still writing
    if final.resolve() == src.resolve():
        final = src  # same path — will swap via rename

    if mode == "rename_old":
        # Move original out of the way first
        bak = src.with_name(src.stem + backup + src.suffix)
        n = 1
        while bak.exists():
            bak = src.with_name(f"{src.stem}{backup}.{n}{src.suffix}")
            n += 1
        src.rename(bak)
        if final.exists() and final.resolve() != staged.resolve():
            final.unlink()
        staged.rename(final)
        return str(final)

    if mode == "replace":
        # Remove original, move staged into place
        try:
            if src.exists() and src.resolve() != staged.resolve():
                src.unlink()
        except Exception as exc:
            raise RuntimeError(f"Could not delete original: {exc}") from exc
        if final.exists() and final.resolve() != staged.resolve():
            final.unlink()
        staged.rename(final)
        return str(final)

    return str(staged)


def build_ffmpeg_cmd(job: ConvertJob, preset: ConvertPreset | None, out: Path) -> list[str]:
    src = job.source_path
    vcodec = (preset.video_codec if preset else "libx264") or "libx264"
    acodec = (preset.audio_codec if preset else "aac") or "aac"
    crf = preset.video_crf if preset else 23
    preset_name = (preset.video_preset if preset else "veryfast") or "veryfast"
    abit = (preset.audio_bitrate if preset else "160k") or "160k"
    max_h = preset.max_height if preset else None
    hw = ((preset.hwaccel if preset else None) or "none").lower()
    extra = (preset.extra_args if preset else None) or ""

    cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error"]

    # Input hwaccel (decode assist)
    if hw in ("cuda", "nvenc") and vcodec != "copy":
        cmd += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
    elif hw == "qsv" and vcodec != "copy":
        cmd += ["-hwaccel", "qsv", "-hwaccel_output_format", "qsv"]
    elif hw == "vaapi" and vcodec != "copy":
        cmd += ["-hwaccel", "vaapi", "-hwaccel_device", "/dev/dri/renderD128", "-hwaccel_output_format", "vaapi"]
    elif hw in ("amf", "d3d11va") and vcodec != "copy":
        # AMF typically pairs with D3D11VA on Windows; on Linux often software decode + amf encode
        cmd += ["-hwaccel", "auto"]

    cmd += ["-i", src]

    if vcodec == "copy":
        cmd += ["-c:v", "copy"]
    else:
        cmd += ["-c:v", vcodec]
        # Software
        if vcodec in ("libx264", "libx265"):
            cmd += ["-crf", str(crf), "-preset", preset_name]
            if max_h:
                cmd += ["-vf", f"scale=-2:'min({max_h},ih)'"]
            cmd += ["-pix_fmt", "yuv420p"]
        elif vcodec == "libsvtav1":
            cmd += ["-crf", str(crf), "-preset", str(preset_name)]
            if max_h:
                cmd += ["-vf", f"scale=-2:'min({max_h},ih)'"]
            cmd += ["-pix_fmt", "yuv420p"]
        # NVIDIA NVENC
        elif vcodec in ("h264_nvenc", "hevc_nvenc", "av1_nvenc"):
            # cq / cq-like quality; p1-p7 presets
            cmd += ["-preset", preset_name if preset_name.startswith("p") else "p4"]
            cmd += ["-rc", "vbr", "-cq", str(crf), "-b:v", "0"]
            if max_h:
                # scale_cuda when using cuda frames; fallback to scale
                if hw in ("cuda", "nvenc"):
                    cmd += ["-vf", f"scale_cuda=-2:{max_h}"]
                else:
                    cmd += ["-vf", f"scale=-2:'min({max_h},ih)'"]
        # Intel QSV
        elif vcodec in ("h264_qsv", "hevc_qsv", "av1_qsv"):
            cmd += ["-global_quality", str(crf), "-preset", preset_name]
            if max_h:
                if hw == "qsv":
                    cmd += ["-vf", f"scale_qsv=-2:{max_h}"]
                else:
                    cmd += ["-vf", f"scale=-2:'min({max_h},ih)'"]
        # VAAPI encode
        elif vcodec in ("h264_vaapi", "hevc_vaapi"):
            cmd += ["-qp", str(crf)]
            if max_h:
                cmd += ["-vf", f"scale_vaapi=-2:{max_h}"]
        # AMD AMF
        elif vcodec in ("h264_amf", "hevc_amf", "av1_amf"):
            # quality | balanced | speed ; qp / rc cqp
            quality = preset_name if preset_name in ("quality", "balanced", "speed") else "quality"
            cmd += ["-quality", quality, "-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf)]
            if max_h:
                cmd += ["-vf", f"scale=-2:'min({max_h},ih)'"]
        else:
            # generic
            cmd += ["-crf", str(crf)]
            if max_h:
                cmd += ["-vf", f"scale=-2:'min({max_h},ih)'"]

    if acodec == "copy":
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", acodec, "-b:a", abit, "-ac", "2"]

    if extra.strip():
        import shlex
        try:
            cmd += shlex.split(extra)
        except Exception:
            pass

    cmd += ["-progress", "pipe:1", "-nostats", str(out)]
    return cmd


def detect_hw_encoders() -> dict:
    """Probe ffmpeg for NVENC / QSV / VAAPI encoders."""
    import subprocess
    out = {"ffmpeg": False, "nvenc": False, "qsv": False, "vaapi": False, "amf": False, "encoders": []}
    try:
        proc = subprocess.run([ffmpeg_bin(), "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=15)
        text = (proc.stdout or "") + (proc.stderr or "")
        out["ffmpeg"] = True
        for name in ("h264_nvenc", "hevc_nvenc", "av1_nvenc", "h264_qsv", "hevc_qsv", "av1_qsv", "h264_vaapi", "hevc_vaapi", "h264_amf", "hevc_amf", "av1_amf"):
            if name in text:
                out["encoders"].append(name)
                if "nvenc" in name:
                    out["nvenc"] = True
                if "qsv" in name:
                    out["qsv"] = True
                if "vaapi" in name:
                    out["vaapi"] = True
                if "amf" in name:
                    out["amf"] = True
    except Exception as exc:
        out["error"] = str(exc)
    return out


def watch_folder_scan(db: Session) -> dict:
    """Auto-queue from DB watch-folder mappings and/or CONVERTER_WATCH_FOLDERS env."""
    from datetime import datetime, timezone
    from app.config import settings
    from app.models import ConvertWatchFolder

    limit = int(getattr(settings, "converter_watch_limit", 50) or 50)
    total_queued = 0
    total_scanned = 0
    details = []

    # 1) Per-folder DB mappings (preferred)
    rows = (
        db.query(ConvertWatchFolder)
        .filter(ConvertWatchFolder.enabled.is_(True))
        .order_by(ConvertWatchFolder.id)
        .all()
    )
    for row in rows:
        root = row.path
        if not root:
            continue
        r = scan_libraries(
            db,
            roots=[root],
            preset_id=row.preset_id,
            limit=limit,
        )
        row.last_scan_at = datetime.now(timezone.utc)
        row.last_queued = int(r.get("queued") or 0)
        db.add(row)
        total_queued += r.get("queued") or 0
        total_scanned += r.get("scanned") or 0
        details.append({"path": root, "preset_id": row.preset_id, **r})

    # 2) Env fallback when no DB rows
    if not rows:
        raw = (getattr(settings, "converter_watch_folders", None) or "").strip()
        folders = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
        if not folders:
            db.commit()
            return {"enabled": False, "queued": 0, "scanned": 0, "folders": []}
        preset_id = getattr(settings, "converter_watch_preset_id", None)
        r = scan_libraries(db, roots=folders, preset_id=preset_id, limit=limit)
        db.commit()
        return {
            "enabled": True,
            "source": "env",
            "queued": r.get("queued", 0),
            "scanned": r.get("scanned", 0),
            "folders": folders,
            "details": [{"path": f, "preset_id": preset_id, **r} for f in folders],
        }

    db.commit()
    return {
        "enabled": True,
        "source": "db",
        "queued": total_queued,
        "scanned": total_scanned,
        "folders": [d["path"] for d in details],
        "details": details,
    }


def process_next_job(db: Session) -> dict | None:
    """Run one queued job (blocking). Returns summary or None if idle."""
    global _active_jobs
    with _worker_lock:
        # allow multiple: only skip if THIS path is single-threaded caller; batch handles slots
        from app.config import settings
        max_w = max(1, min(8, int(getattr(settings, "converter_max_workers", 1) or 1)))
        live = {jid: p for jid, p in list(_active_jobs.items()) if p.poll() is None}
        _active_jobs.clear()
        _active_jobs.update(live)
        if len(_active_jobs) >= max_w:
            return {"busy": True, "active": list(_active_jobs.keys())}

        job = (
            db.query(ConvertJob)
            .filter(ConvertJob.status == "queued")
            .order_by(ConvertJob.id)
            .first()
        )
        if not job:
            return None

        preset = db.get(ConvertPreset, job.preset_id) if job.preset_id else None
        out = _output_path(job, preset)
        job.output_path = str(out)
        job.status = "running"
        job.started_at = _utcnow()
        job.progress = 0
        job.message = "starting"
        db.add(job)
        db.commit()

        duration = None
        try:
            info = probe(Path(job.source_path))
            duration = info.get("duration")
        except Exception:
            pass

        cmd = build_ffmpeg_cmd(job, preset, out)
        log.info("Convert job %s: %s", job.id, " ".join(cmd[:12]))
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            job.status = "failed"
            job.message = "ffmpeg not found"
            job.finished_at = _utcnow()
            db.add(job)
            db.commit()
            return {"job_id": job.id, "status": "failed", "message": job.message}

        _active_jobs[job.id] = proc
        job.pid = proc.pid
        db.add(job)
        db.commit()

        # parse -progress pipe:1
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if line.startswith("out_time_ms="):
                    try:
                        ms = int(line.split("=", 1)[1])
                        if duration and duration > 0:
                            job.progress = min(99.0, (ms / 1_000_000) / duration * 100)
                            job.message = f"{job.progress:.1f}%"
                            db.add(job)
                            db.commit()
                    except Exception:
                        pass
                elif line.startswith("progress=end"):
                    break
            proc.wait(timeout=86400)
        except Exception as exc:
            try:
                proc.kill()
            except Exception:
                pass
            job.status = "failed"
            job.message = str(exc)[:500]
            job.finished_at = _utcnow()
            db.add(job)
            db.commit()
            _active_jobs.pop(job.id, None)
            return {"job_id": job.id, "status": "failed", "message": job.message}

        _active_jobs.pop(job.id, None)
        rc = proc.returncode
        if rc != 0:
            err = (proc.stderr.read() if proc.stderr else "")[:500]
            job.status = "failed"
            job.message = err or f"ffmpeg exit {rc}"
            job.finished_at = _utcnow()
            db.add(job)
            db.commit()
            return {"job_id": job.id, "status": "failed", "message": job.message}

        # Apply output mode: new_file | replace | rename_old
        try:
            final_path = _finalize_output(job, preset, Path(out))
            job.output_path = final_path
        except Exception as exc:
            job.status = "failed"
            job.message = f"finalize failed: {exc}"
            job.finished_at = _utcnow()
            db.add(job)
            db.commit()
            return {"job_id": job.id, "status": "failed", "message": job.message}

        job.status = "done"
        job.progress = 100.0
        job.message = "complete"
        job.finished_at = _utcnow()
        try:
            job.output_size = Path(job.output_path).stat().st_size if job.output_path else None
        except Exception:
            pass
        db.add(job)
        db.commit()
        return {"job_id": job.id, "status": "done", "output": job.output_path}


def cancel_job(db: Session, job_id: int) -> bool:
    global _active_jobs
    job = db.get(ConvertJob, job_id)
    if not job:
        return False
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = _utcnow()
        db.add(job)
        db.commit()
        return True
    if job.status == "running" and job_id in _active_jobs:
        try:
            _active_jobs[job_id].kill()
        except Exception:
            pass
        _active_jobs.pop(job_id, None)
        job.status = "cancelled"
        job.finished_at = _utcnow()
        job.message = "cancelled"
        db.add(job)
        db.commit()
        return True
    return False


def queue_stats(db: Session) -> dict:
    from sqlalchemy import func
    rows = (
        db.query(ConvertJob.status, func.count(ConvertJob.id))
        .group_by(ConvertJob.status)
        .all()
    )
    counts = {s: c for s, c in rows}
    return {
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0),
        "done": counts.get("done", 0),
        "failed": counts.get("failed", 0),
        "cancelled": counts.get("cancelled", 0),
        "active_job_ids": list(_active_jobs.keys()),
        "active_job_id": next(iter(_active_jobs.keys()), None),
        "savings": savings_report(db),
    }


def _fmt_bytes(n: int | None) -> str:
    if n is None or n < 0:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.1f} {u}" if u != "B" else f"{int(x)} B"
        x /= 1024
    return f"{x:.1f} TB"


def savings_report(db: Session) -> dict:
    """HandBrake/Tdarr-style space savings across completed jobs."""
    done = (
        db.query(ConvertJob)
        .filter(ConvertJob.status == "done")
        .all()
    )
    pairs = []
    src_total = 0
    out_total = 0
    counted = 0
    for j in done:
        if j.source_size and j.output_size and j.source_size > 0:
            src_total += j.source_size
            out_total += j.output_size
            saved = j.source_size - j.output_size
            pct = (saved / j.source_size) * 100.0
            pairs.append({
                "id": j.id,
                "source_path": j.source_path,
                "preset_name": j.preset_name,
                "source_size": j.source_size,
                "output_size": j.output_size,
                "saved": saved,
                "saved_pct": round(pct, 1),
                "source_human": _fmt_bytes(j.source_size),
                "output_human": _fmt_bytes(j.output_size),
                "saved_human": _fmt_bytes(saved),
            })
            counted += 1
    saved_total = src_total - out_total
    pct_total = (saved_total / src_total * 100.0) if src_total else 0.0
    # top savers
    top = sorted(pairs, key=lambda x: x["saved"], reverse=True)[:10]
    return {
        "jobs_with_sizes": counted,
        "jobs_done": len(done),
        "source_bytes": src_total,
        "output_bytes": out_total,
        "saved_bytes": saved_total,
        "saved_pct": round(pct_total, 1),
        "source_human": _fmt_bytes(src_total),
        "output_human": _fmt_bytes(out_total),
        "saved_human": _fmt_bytes(saved_total),
        "top_savers": top,
    }



def within_convert_schedule() -> bool:
    """True if converter is allowed to run now (hour window)."""
    from datetime import datetime
    from app.config import settings
    start = getattr(settings, "converter_schedule_start_hour", None)
    end = getattr(settings, "converter_schedule_end_hour", None)
    if start is None or end is None:
        return True
    try:
        start = int(start)
        end = int(end)
    except Exception:
        return True
    hour = datetime.now().hour
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    # wraps midnight e.g. 22 -> 6
    return hour >= start or hour < end


def process_queue_batch(db: Session) -> list[dict]:
    """Start up to converter_max_workers jobs (Tdarr-style parallel)."""
    from app.config import settings
    if not within_convert_schedule():
        return [{"paused": True, "reason": "outside schedule window"}]
    max_w = max(1, min(8, int(getattr(settings, "converter_max_workers", 1) or 1)))
    results = []
    with _worker_lock:
        active = {jid: proc for jid, proc in list(_active_jobs.items()) if proc.poll() is None}
        _active_jobs.clear()
        _active_jobs.update(active)
        slots = max_w - len(_active_jobs)
    if slots <= 0:
        return [{"busy": True, "active": list(_active_jobs.keys())}]
    for _ in range(slots):
        # process_next_job still does one; call without holding lock for duration
        r = process_next_job(db)
        if not r:
            break
        results.append(r)
        if r.get("status") == "queued" or r.get("idle"):
            break
    return results or [{"idle": True}]
