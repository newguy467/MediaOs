"""Dashboard widgets — Prismarr-inspired calendar/activity/queue summary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import ItemStatus, Activity, Download, Episode, MediaItem, MediaType


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
    rows = db.query(Download).order_by(Download.id.desc()).limit(limit).all()
    out = []
    for r in rows:
        st = r.status.value if hasattr(r.status, "value") else str(r.status or "")
        if st in ("completed", "failed", "removed"):
            continue
        out.append({
            "id": r.id,
            "title": getattr(r, "release_title", None) or getattr(r, "title", None),
            "status": st,
            "progress": getattr(r, "progress", None),
        })
        if len(out) >= limit:
            break
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
    for mt in (MediaType.movie, MediaType.tv, MediaType.music, MediaType.book, MediaType.audiobook, MediaType.comic, MediaType.adult):
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




def widget_library_counts(db: Session) -> dict[str, int]:
    out = {}
    for mt in MediaType:
        try:
            out[mt.value if hasattr(mt, "value") else str(mt)] = (
                db.query(MediaItem).filter(MediaItem.media_type == mt).count()
            )
        except Exception:
            out[str(mt)] = 0
    return out


def widget_health() -> dict[str, Any]:
    import os
    return {
        "version": os.environ.get("APP_VERSION", "4.9.0"),
        "status": "ok",
    }


def widget_recent_downloads(db: Session, limit: int = 12) -> list[dict]:
    rows = (
        db.query(MediaItem)
        .filter(MediaItem.status == ItemStatus.downloaded)
        .order_by(MediaItem.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "year": r.year,
            "media_type": r.media_type.value if hasattr(r.media_type, "value") else str(r.media_type),
            "poster_path": r.poster_path,
            "file_path": r.file_path,
        }
        for r in rows
    ]


DEFAULT_WIDGET_LAYOUT = [
    {"id": "stats", "enabled": True},
    {"id": "calendar", "enabled": True},
    {"id": "queue", "enabled": True},
    {"id": "wanted", "enabled": True},
    {"id": "activity", "enabled": True},
    {"id": "recent", "enabled": True},
    {"id": "health", "enabled": True},
]


def dashboard_bundle(db: Session) -> dict[str, Any]:
    return {
        "activity": widget_activity(db),
        "queue": widget_queue(db),
        "calendar": widget_calendar(db),
        "wanted": widget_wanted_counts(db),
        "library": widget_library_counts(db),
        "recent": widget_recent_downloads(db),
        "health": widget_health(),
        "layout_default": DEFAULT_WIDGET_LAYOUT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
