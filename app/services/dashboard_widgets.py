"""Dashboard widgets — Prismarr-inspired calendar/activity/queue summary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import Activity, Episode, MediaItem, MediaType, QueueItem


def widget_activity(db: Session, limit: int = 20) -> list[dict]:
    rows = db.query(Activity).order_by(Activity.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "event": r.event,
            "message": getattr(r, "message", None) or getattr(r, "title", None),
            "media_type": r.media_type,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def widget_queue(db: Session, limit: int = 20) -> list[dict]:
    rows = db.query(QueueItem).order_by(QueueItem.id.desc()).limit(limit).all()
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "title": getattr(r, "title", None) or getattr(r, "name", None),
            "status": str(getattr(r, "status", None) or ""),
            "progress": getattr(r, "progress", None),
        })
    return out


def widget_calendar(db: Session, days: int = 14) -> list[dict]:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    # Episodes with air dates in range if column exists
    eps = db.query(Episode).limit(500).all()
    items = []
    for e in eps:
        air = getattr(e, "air_date", None) or getattr(e, "air_date_utc", None)
        if not air:
            continue
        if isinstance(air, str):
            try:
                air_dt = datetime.fromisoformat(air.replace("Z", "+00:00"))
            except Exception:
                continue
        else:
            air_dt = air
        if air_dt.tzinfo is None:
            air_dt = air_dt.replace(tzinfo=timezone.utc)
        if now - timedelta(days=1) <= air_dt <= end:
            series = e.series
            items.append({
                "type": "episode",
                "series": series.title if series else None,
                "season": e.season_number,
                "episode": e.episode_number,
                "title": e.title,
                "air_date": air_dt.isoformat(),
                "status": str(e.status.value if hasattr(e.status, "value") else e.status),
            })
    items.sort(key=lambda x: x.get("air_date") or "")
    return items[:100]


def widget_wanted_counts(db: Session) -> dict[str, int]:
    from app.models import ItemStatus
    counts = {}
    for mt in (MediaType.movie, MediaType.tv, MediaType.music, MediaType.comic):
        try:
            n = (
                db.query(MediaItem)
                .filter(
                    MediaItem.media_type == mt,
                    MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
                )
                .count()
            )
            counts[mt.value if hasattr(mt, "value") else str(mt)] = n
        except Exception:
            counts[str(mt)] = 0
    return counts


def dashboard_bundle(db: Session) -> dict[str, Any]:
    return {
        "activity": widget_activity(db),
        "queue": widget_queue(db),
        "calendar": widget_calendar(db),
        "wanted": widget_wanted_counts(db),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
