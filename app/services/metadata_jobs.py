"""Background metadata refresh job queue with SSE progress.

UI bulk refresh can enqueue many item IDs; a single worker processes them
and publishes `metadata_job` events for live progress.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.sse import publish as sse_publish

log = logging.getLogger("mediaos.metadata_jobs")

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_queue: list[str] = []
_worker_started = False
_worker_stop = threading.Event()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_worker() -> None:
    global _worker_started
    with _lock:
        if _worker_started:
            return
        _worker_started = True
        t = threading.Thread(target=_worker_loop, name="mediaos-metadata-jobs", daemon=True)
        t.start()


def _worker_loop() -> None:
    while not _worker_stop.is_set():
        job_id = None
        with _lock:
            if _queue:
                job_id = _queue.pop(0)
                job = _jobs.get(job_id)
                if job:
                    job["status"] = "running"
                    job["started_at"] = _utcnow()
        if not job_id:
            time.sleep(0.4)
            continue
        try:
            _run_job(job_id)
        except Exception as exc:
            log.exception("metadata job %s failed: %s", job_id, exc)
            with _lock:
                job = _jobs.get(job_id)
                if job:
                    job["status"] = "failed"
                    job["error"] = str(exc)
                    job["finished_at"] = _utcnow()
            sse_publish("metadata_job", {"job_id": job_id, "status": "failed", "error": str(exc)})


def _refresh_one(db, item_id: int) -> dict[str, Any]:
    from app.models import MediaItem

    try:
        item = db.get(MediaItem, item_id)
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"id": item_id, "ok": False, "error": str(e)}
    if not item:
        return {"id": item_id, "ok": False, "error": "not found"}
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
        item.updated_at = datetime.now(timezone.utc)
        db.add(item)
        db.commit()
        return {"id": item_id, "ok": True, "media_type": mt}
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"id": item_id, "ok": False, "error": str(e), "media_type": mt}


def _run_job(job_id: str) -> None:
    from app.database import SessionLocal

    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        ids = list(job.get("item_ids") or [])
        job["total"] = len(ids)
        job["done"] = 0
        job["ok"] = 0
        job["failed"] = 0
        job["results"] = []

    db = SessionLocal()
    try:
        for item_id in ids:
            result = _refresh_one(db, int(item_id))
            with _lock:
                job = _jobs.get(job_id)
                if not job:
                    return
                job["results"].append(result)
                job["done"] = int(job.get("done") or 0) + 1
                if result.get("ok"):
                    job["ok"] = int(job.get("ok") or 0) + 1
                else:
                    job["failed"] = int(job.get("failed") or 0) + 1
                progress = {
                    "job_id": job_id,
                    "status": "running",
                    "done": job["done"],
                    "total": job["total"],
                    "ok": job["ok"],
                    "failed": job["failed"],
                    "last": result,
                }
            sse_publish("metadata_job", progress)
        with _lock:
            job = _jobs.get(job_id)
            if job:
                job["status"] = "completed"
                job["finished_at"] = _utcnow()
                final = {
                    "job_id": job_id,
                    "status": "completed",
                    "done": job["done"],
                    "total": job["total"],
                    "ok": job["ok"],
                    "failed": job["failed"],
                }
        sse_publish("metadata_job", final)
    finally:
        db.close()


def enqueue(item_ids: list[int], *, note: str | None = None) -> dict[str, Any]:
    """Enqueue a bulk metadata refresh job. Returns job summary."""
    ids = [int(x) for x in item_ids if x is not None]
    if not ids:
        return {"ok": False, "error": "no item_ids"}
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "status": "queued",
        "item_ids": ids,
        "total": len(ids),
        "done": 0,
        "ok": 0,
        "failed": 0,
        "results": [],
        "note": note,
        "created_at": _utcnow(),
        "started_at": None,
        "finished_at": None,
        "error": None,
    }
    with _lock:
        _jobs[job_id] = job
        _queue.append(job_id)
    _ensure_worker()
    sse_publish("metadata_job", {"job_id": job_id, "status": "queued", "total": len(ids)})
    return {"ok": True, "job_id": job_id, "total": len(ids), "status": "queued"}


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    with _lock:
        items = sorted(_jobs.values(), key=lambda j: j.get("created_at") or "", reverse=True)
        return [dict(j) for j in items[:limit]]
