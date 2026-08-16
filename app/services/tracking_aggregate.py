"""Episode-aware tracking aggregation for TV series."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Episode, ItemStatus, MediaItem, MediaType, TrackedItem


def series_episode_stats(db: Session, series_id: int) -> dict:
    eps = db.query(Episode).filter(Episode.media_item_id == series_id).all()
    total = len(eps)
    have = sum(1 for e in eps if e.file_path or getattr(e, "status", None) == ItemStatus.downloaded)
    pct = (100.0 * have / total) if total else 0.0
    return {"total": total, "have": have, "percent": round(pct, 1)}


def sync_series_tracking(db: Session, series_id: int) -> dict | None:
    """Upsert TrackedItem progress from episode file coverage."""
    series = db.get(MediaItem, series_id)
    if not series or series.media_type != MediaType.tv:
        return None
    stats = series_episode_stats(db, series_id)
    tracked = db.query(TrackedItem).filter(TrackedItem.media_item_id == series_id).first()
    now = datetime.now(timezone.utc)
    status = "completed" if stats["percent"] >= 99 and stats["total"] else (
        "in_progress" if stats["have"] else "planned"
    )
    if tracked:
        tracked.progress_percent = stats["percent"]
        if status == "completed":
            tracked.status = "completed"
            tracked.completed_at = tracked.completed_at or now
        elif tracked.status in ("", "planned", None) and stats["have"]:
            tracked.status = "in_progress"
            tracked.started_at = tracked.started_at or now
        tracked.updated_at = now
        db.add(tracked)
    else:
        tracked = TrackedItem(
            media_item_id=series_id,
            status=status,
            progress_percent=stats["percent"],
            started_at=now if status == "in_progress" else None,
            completed_at=now if status == "completed" else None,
        )
        db.add(tracked)
    db.commit()
    return {"series_id": series_id, "status": status, **stats}
