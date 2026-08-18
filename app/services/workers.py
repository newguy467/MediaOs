"""Background worker job registry with rich progress (MediaOs-style)."""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable



# MediaOs-style worker kinds
KIND_SEARCH = "search"
KIND_IMPORT = "import"
KIND_STREAM = "stream"
KIND_SUBTITLE = "subtitle"
KIND_PORTAL = "portal"
KIND_CHANNEL = "channel"
KIND_CLEANUP = "cleanup"
KIND_CONVERT = "convert"
KIND_GENERIC = "generic"

@dataclass
class Job:
    id: str
    name: str
    status: str = "queued"  # queued | running | done | failed
    kind: str = KIND_GENERIC
    progress: float = 0.0
    message: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    result: Any = None

    def update(self, *, progress: float | None = None, message: str | None = None) -> None:
        if progress is not None:
            self.progress = max(0.0, min(100.0, float(progress)))
        if message is not None:
            self.message = message


_jobs: dict[str, Job] = {}
_lock = threading.Lock()
_MAX_JOBS = 200


def list_jobs(limit: int = 50) -> list[dict]:
    with _lock:
        rows = sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)[:limit]
        return [_serialize(j) for j in rows]


def get_job(job_id: str) -> dict | None:
    with _lock:
        j = _jobs.get(job_id)
        return _serialize(j) if j else None


def _serialize(j: Job) -> dict:
    return {
        "id": j.id,
        "name": j.name,
        "kind": getattr(j, "kind", KIND_GENERIC),
        "status": j.status,
        "progress": j.progress,
        "message": j.message,
        "created_at": j.created_at,
        "finished_at": j.finished_at,
        "result": j.result,
    }


def _trim() -> None:
    if len(_jobs) <= _MAX_JOBS:
        return
    ordered = sorted(_jobs.values(), key=lambda j: j.created_at)
    for j in ordered[: len(_jobs) - _MAX_JOBS]:
        _jobs.pop(j.id, None)


def submit(name: str, fn: Callable[[Job], Any]) -> str:
    job_id = uuid.uuid4().hex[:12]
    job = Job(id=job_id, name=name)

    def _run():
        with _lock:
            job.status = "running"
            job.progress = 1
        try:
            result = fn(job)
            with _lock:
                job.status = "done"
                job.progress = 100
                job.result = result
                job.finished_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            with _lock:
                job.status = "failed"
                job.message = str(e)
                job.finished_at = datetime.now(timezone.utc).isoformat()

    with _lock:
        _jobs[job_id] = job
        _trim()
    threading.Thread(target=_run, name=f"job-{job_id}", daemon=True).start()
    return job_id
