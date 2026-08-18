"""
Anime-oriented helpers (MediaOS v2).

Uses existing series_type == 'anime' on MediaItem / Episode where present.
Provides absolute-number style views and simple scoring notes.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Episode, MediaItem, MediaType


def list_anime_series(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    rows = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.tv)
        .filter(
            (MediaItem.series_type == "anime")
            | (MediaItem.title.ilike("%anime%"))  # weak fallback
        )
        .order_by(MediaItem.title)
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "title": r.title,
            "year": r.year,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "monitored": r.monitored,
            "series_type": getattr(r, "series_type", None) or "anime",
        })
    return out


def absolute_episode_map(db: Session, series_id: int) -> list[dict[str, Any]]:
    """Return episodes ordered for absolute numbering preference."""
    eps = (
        db.query(Episode)
        .filter(Episode.media_item_id == series_id)
        .order_by(Episode.season_number, Episode.episode_number)
        .all()
    )
    abs_no = 0
    out = []
    for e in eps:
        # skip specials (season 0) from absolute count by default
        if (e.season_number or 0) > 0:
            abs_no += 1
        out.append({
            "id": e.id,
            "season": e.season_number,
            "episode": e.episode_number,
            "absolute": abs_no if (e.season_number or 0) > 0 else None,
            "title": e.title,
            "status": e.status.value if hasattr(e.status, "value") else str(getattr(e, "status", "")),
            "file_path": getattr(e, "file_path", None),
        })
    return out
