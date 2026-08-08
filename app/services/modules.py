"""
Module registry — which library domains are enabled in MediaOs.

TV & Movies are always on (core). Optional modules:
  music, books, audiobooks, comics, manga, livetv, youtube, podcasts, converter

Stored in AppSetting key "enabled_modules" as JSON list.
Used by: setup wizard, Module Store UI, sidebar filtering.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import AppSetting

log = logging.getLogger("mediaos.modules")

# Core — always enabled, cannot be turned off
CORE_MODULES = ["movies", "tv"]

# Optional modules users can enable in wizard or Module Store
OPTIONAL_MODULES = [
    {
        "id": "music",
        "label": "Music",
        "description": "Artists, albums, tracks — Lidarr-style hierarchy + completeness",
        "icon": "music",
        "default": False,
        "requires_path": "music_library_path",
    },
    {
        "id": "books",
        "label": "Books",
        "description": "eBooks with Readarr-style monitoring and organize",
        "icon": "book",
        "default": False,
        "requires_path": "books_library_path",
    },
    {
        "id": "audiobooks",
        "label": "Audiobooks",
        "description": "Audiobook library with Audnexus metadata",
        "icon": "headphones",
        "default": False,
        "requires_path": "audiobooks_library_path",
    },
    {
        "id": "comics",
        "label": "Comics / Manga",
        "description": "Pull-list automation, story arcs, metatagging (Mylar-level)",
        "icon": "book",
        "default": False,
        "requires_path": "comics_library_path",
    },
    {
        "id": "livetv",
        "label": "Live TV",
        "description": "Channels, EPG, portal scan, groups (Cinephage-inspired)",
        "icon": "radio",
        "default": False,
        "requires_path": None,
    },
    {
        "id": "youtube",
        "label": "YouTube Creators",
        "description": "Channel tracking + yt-dlp downloads",
        "icon": "play",
        "default": False,
        "requires_path": "youtube_library_path",
    },
    {
        "id": "podcasts",
        "label": "Podcasts",
        "description": "Podcast subscriptions and episodes",
        "icon": "radio",
        "default": False,
        "requires_path": "podcasts_library_path",
    },
    {
        "id": "converter",
        "label": "Converter",
        "description": "HandBrake-style transcoding queue (GPU/CPU)",
        "icon": "activity",
        "default": False,
        "requires_path": None,
    },
]

SETTING_KEY = "enabled_modules"


def _get_row(db: Session) -> AppSetting | None:
    return db.query(AppSetting).filter(AppSetting.key == SETTING_KEY).first()


def get_enabled(db: Session) -> list[str]:
    """Return list of enabled module ids (always includes core)."""
    row = _get_row(db)
    enabled: list[str] = list(CORE_MODULES)
    if row and row.value:
        try:
            extra = json.loads(row.value)
            if isinstance(extra, list):
                for m in extra:
                    if m not in enabled and any(o["id"] == m for o in OPTIONAL_MODULES):
                        enabled.append(m)
        except Exception:
            pass
    return enabled


def set_enabled(db: Session, module_ids: list[str]) -> list[str]:
    """
    Persist enabled optional modules. Core (movies, tv) always stay on.
    Returns the final enabled list.
    """
    optional_ids = {o["id"] for o in OPTIONAL_MODULES}
    cleaned = [m for m in module_ids if m in optional_ids]
    # Store only optional; core is implicit
    row = _get_row(db)
    payload = json.dumps(cleaned)
    if row:
        row.value = payload
    else:
        db.add(AppSetting(key=SETTING_KEY, value=payload))
    db.commit()
    return get_enabled(db)


def enable_module(db: Session, module_id: str) -> list[str]:
    current = get_enabled(db)
    if module_id not in current:
        current.append(module_id)
    return set_enabled(db, current)


def disable_module(db: Session, module_id: str) -> list[str]:
    if module_id in CORE_MODULES:
        return get_enabled(db)  # cannot disable core
    current = [m for m in get_enabled(db) if m != module_id]
    return set_enabled(db, current)


def catalog() -> list[dict[str, Any]]:
    """Full catalog for Module Store + wizard."""
    return [
        {
            "id": "movies",
            "label": "Movies",
            "description": "Movie library — always enabled (core)",
            "icon": "film",
            "core": True,
            "default": True,
        },
        {
            "id": "tv",
            "label": "TV Shows",
            "description": "Series & episodes — always enabled (core)",
            "icon": "tv",
            "core": True,
            "default": True,
        },
        *[
            {
                **o,
                "core": False,
            }
            for o in OPTIONAL_MODULES
        ],
    ]


def status(db: Session) -> dict[str, Any]:
    enabled = get_enabled(db)
    return {
        "enabled": enabled,
        "core": CORE_MODULES,
        "optional": [o["id"] for o in OPTIONAL_MODULES],
        "catalog": [
            {
                **item,
                "enabled": item["id"] in enabled,
            }
            for item in catalog()
        ],
    }
