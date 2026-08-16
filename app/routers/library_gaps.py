"""API surface for major library gap tools."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_permission, require_admin
from app.database import get_db
from app.models import MediaItem, PathMap
from app.services import library_gaps as lg
from app.services.tracking_aggregate import sync_series_tracking

router = APIRouter(prefix="/library", tags=["library-gaps"])


@router.get("/duplicates")
def list_duplicates(
    media_type: str | None = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _=Depends(require_permission("library")),
):
    return {"items": lg.find_duplicates(db, media_type=media_type, limit=limit)}


class MergeIn(BaseModel):
    keep_id: int
    drop_ids: list[int]


@router.post("/duplicates/merge")
def merge_duplicates(body: MergeIn, db: Session = Depends(get_db), _=Depends(require_permission("library.manage"))):
    keep = db.get(MediaItem, body.keep_id)
    if not keep:
        raise HTTPException(404, "keep_id not found")
    dropped = []
    for did in body.drop_ids:
        if did == body.keep_id:
            continue
        row = db.get(MediaItem, did)
        if not row:
            continue
        # Prefer keep's empty fields filled from drop
        if not keep.file_path and row.file_path:
            keep.file_path = row.file_path
        if not keep.poster_path and row.poster_path:
            keep.poster_path = row.poster_path
        if not keep.external_id and row.external_id:
            keep.external_id = row.external_id
            keep.external_source = row.external_source
        db.delete(row)
        dropped.append(did)
    db.add(keep)
    db.commit()
    return {"ok": True, "keep_id": keep.id, "dropped": dropped}


@router.get("/attention")
def attention(db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    return {"items": lg.needs_attention(db)}


class StatusIn(BaseModel):
    status: str
    force: bool = False


@router.post("/items/{item_id}/status")
def set_item_status(item_id: int, body: StatusIn, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    item = db.get(MediaItem, item_id)
    if not item:
        raise HTTPException(404, "Not found")
    applied = lg.transition_status(item, body.status, force=body.force)
    db.add(item)
    db.commit()
    return {"ok": True, "id": item.id, "status": applied}


@router.post("/tv/{series_id}/sync-tracking")
def sync_tv_tracking(series_id: int, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    out = sync_series_tracking(db, series_id)
    if not out:
        raise HTTPException(404, "Not a TV series")
    return out


@router.get("/path-maps")
def list_path_maps(db: Session = Depends(get_db), _=Depends(require_permission("settings"))):
    rows = db.query(PathMap).order_by(PathMap.id).all()
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "container_prefix": r.container_prefix,
                "host_prefix": r.host_prefix,
                "media_type": r.media_type,
                "enabled": r.enabled,
            }
            for r in rows
        ]
    }


class PathMapIn(BaseModel):
    name: str = "default"
    container_prefix: str
    host_prefix: str
    media_type: str | None = None
    enabled: bool = True


@router.post("/path-maps")
def create_path_map(body: PathMapIn, db: Session = Depends(get_db), _=Depends(require_admin)):
    row = PathMap(
        name=body.name,
        container_prefix=body.container_prefix,
        host_prefix=body.host_prefix,
        media_type=body.media_type,
        enabled=body.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


@router.post("/path-maps/dry-run")
def path_map_dry_run(body: dict, db: Session = Depends(get_db), _=Depends(require_permission("settings"))):
    path = body.get("path") or ""
    return lg.dry_run_organize_path(db, path, body.get("media_type"))


@router.post("/metadata/refresh/{item_id}")
def refresh_metadata(item_id: int, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Soft metadata touch — delegates to type-specific refresh when available."""
    item = db.get(MediaItem, item_id)
    if not item:
        raise HTTPException(404, "Not found")
    mt = item.media_type.value if hasattr(item.media_type, "value") else str(item.media_type)
    try:
        if mt == "tv":
            from app.services import tv as tv_svc
            if hasattr(tv_svc, "refresh_series"):
                tv_svc.refresh_series(db, item_id)
        elif mt == "movie":
            from app.services import movies as mov_svc
            if hasattr(mov_svc, "refresh_movie"):
                mov_svc.refresh_movie(db, item_id)
        item.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        db.add(item)
        db.commit()
    except Exception as e:
        raise HTTPException(502, f"refresh failed: {e}")
    return {"ok": True, "id": item_id, "media_type": mt}


class BulkMetadataIn(BaseModel):
    item_ids: list[int]
    note: str | None = None


@router.post("/metadata/jobs")
def enqueue_metadata_job(body: BulkMetadataIn, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Enqueue bulk metadata refresh (background worker + SSE progress on channel metadata_job)."""
    from app.services.metadata_jobs import enqueue
    return enqueue(body.item_ids, note=body.note)


@router.get("/metadata/jobs")
def list_metadata_jobs(limit: int = Query(20, le=100), _=Depends(require_permission("library"))):
    from app.services.metadata_jobs import list_jobs
    return {"items": list_jobs(limit=limit)}


@router.get("/metadata/jobs/{job_id}")
def get_metadata_job(job_id: str, _=Depends(require_permission("library"))):
    from app.services.metadata_jobs import get_job
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job

@router.get("/path-conflicts")
def path_conflicts_report(db: Session = Depends(get_db), _=Depends(require_permission("settings", "library.view"))):
    """Hubstarr-style path footgun report: duplicates, host-vs-container hints, module gaps."""
    from app.services.path_conflicts import full_report
    return full_report(db)


@router.get("/path-help")
def path_help(_: list = Depends(require_permission("settings", "library.view"))):
    """Per-field help for library/download paths."""
    from app.services.settings_help import PATH_HELP
    return {"fields": PATH_HELP}
