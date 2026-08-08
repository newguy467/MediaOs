"""
Music hierarchy: Artist → Album → Track (Lidarr + Headphones inspired).

MediaOs already has music_completeness.py for album-level %.
This module adds the tree-oriented views and wanted hierarchy helpers
needed for a full Lidarr-style experience in v4.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import MediaItem, MediaType

log = logging.getLogger("mediaos.music_hierarchy")


def get_artist_tree(db: Session, artist_name: str) -> dict[str, Any]:
    """
    Return artist → albums → (track completeness summary).
    Used by the Music wanted / library UI.
    """
    albums = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.music,
            MediaItem.artist_name == artist_name,
        )
        .order_by(MediaItem.year.desc().nullslast(), MediaItem.title)
        .all()
    )
    album_rows = []
    for a in albums:
        # Completeness is computed by music_completeness service in real flow
        album_rows.append({
            "id": a.id,
            "title": a.title,
            "year": a.year,
            "monitored": a.monitored,
            "status": a.status.value if a.status else None,
            "file_path": a.file_path,
            "quality_profile": a.quality_profile,
        })
    return {
        "artist": artist_name,
        "album_count": len(album_rows),
        "albums": album_rows,
    }


def list_wanted_hierarchy(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    """
    Wanted music ordered for hierarchy UI: artists with missing/wanted albums first.
    """
    wanted = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.music,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_(["wanted", "missing"]),
        )
        .order_by(MediaItem.artist_name, MediaItem.year.nullslast(), MediaItem.title)
        .limit(limit)
        .all()
    )
    # Group by artist for tree rendering
    tree: dict[str, list] = {}
    for item in wanted:
        key = item.artist_name or "Unknown Artist"
        tree.setdefault(key, []).append({
            "id": item.id,
            "title": item.title,
            "year": item.year,
            "status": item.status.value if item.status else None,
        })
    return [{"artist": k, "albums": v} for k, v in tree.items()]
