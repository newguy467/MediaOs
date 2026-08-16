"""
Module registry — which library domains are enabled in MediaOs.

TV & Movies are always on (core). Optional modules toggled in Module Store.

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

CORE_MODULES = ["movies", "tv"]

# Hubstarr-style catalog: cards, path needs, tags, soft conflicts
OPTIONAL_MODULES = [
    {
        "id": "music",
        "label": "Music",
        "description": "Artists, albums, tracks — Lidarr-style hierarchy + completeness",
        "icon": "music",
        "default": False,
        "requires_path": "music_library_path",
        "path_label": "Music library folder",
        "category": "library",
        "tags": ["lidarr", "path"],
        "conflicts_with": [],
    },
    {
        "id": "books",
        "label": "Books",
        "description": "eBooks with Readarr-style monitoring and organize",
        "icon": "book",
        "default": False,
        "requires_path": "books_library_path",
        "path_label": "Books library folder",
        "category": "library",
        "tags": ["readarr", "path"],
        "conflicts_with": [],
    },
    {
        "id": "audiobooks",
        "label": "Audiobooks",
        "description": "Audiobook library with Audnexus metadata",
        "icon": "headphones",
        "default": False,
        "requires_path": "audiobooks_library_path",
        "path_label": "Audiobooks library folder",
        "category": "library",
        "tags": ["path"],
        "conflicts_with": [],
    },
    {
        "id": "comics",
        "label": "Comics",
        "description": "Pull-list automation, story arcs, metatagging (Mylar-level)",
        "icon": "book",
        "default": False,
        "requires_path": "comics_library_path",
        "path_label": "Comics library folder",
        "category": "library",
        "tags": ["mylar", "path"],
        "conflicts_with": [],
    },
    {
        "id": "manga",
        "label": "Manga",
        "description": "Manga library path and reading list",
        "icon": "book",
        "default": False,
        "requires_path": "manga_library_path",
        "path_label": "Manga library folder",
        "category": "library",
        "tags": ["path"],
        "conflicts_with": [],
    },
    {
        "id": "livetv",
        "label": "Live TV",
        "description": "Channels, EPG, portal scan, groups, DVR — auto channel health cleanup",
        "icon": "radio",
        "default": False,
        "requires_path": None,
        "path_label": None,
        "category": "live",
        "tags": ["epg", "dvr"],
        "conflicts_with": [],
    },
    {
        "id": "youtube",
        "label": "YouTube Creators",
        "description": "Channel tracking + yt-dlp downloads",
        "icon": "play",
        "default": False,
        "requires_path": "youtube_library_path",
        "path_label": "YouTube download folder",
        "category": "creators",
        "tags": ["path", "yt-dlp"],
        "conflicts_with": [],
    },
    {
        "id": "podcasts",
        "label": "Podcasts",
        "description": "Podcast subscriptions and episodes",
        "icon": "radio",
        "default": False,
        "requires_path": "podcasts_library_path",
        "path_label": "Podcasts folder",
        "category": "creators",
        "tags": ["path"],
        "conflicts_with": [],
    },
    {
        "id": "games",
        "label": "Games",
        "description": "Platforms, releases, wanted, grab + install jobs (Questarr-inspired)",
        "icon": "gamepad",
        "default": False,
        "requires_path": "games_library_path",
        "path_label": "Games library folder",
        "category": "games",
        "tags": ["path", "install"],
        "conflicts_with": [],
    },
    {
        "id": "scrobbling",
        "label": "Scrobbling & History",
        "description": "Local watch/play progress, Continue Watching, history",
        "icon": "activity",
        "default": True,
        "requires_path": None,
        "path_label": None,
        "category": "tracking",
        "tags": ["core-adjacent"],
        "conflicts_with": [],
    },
    {
        "id": "tracking",
        "label": "Unified Tracking",
        "description": "Status, ratings, notes across movies, TV, games, books, comics",
        "icon": "list",
        "default": True,
        "requires_path": None,
        "path_label": None,
        "category": "tracking",
        "tags": ["core-adjacent"],
        "conflicts_with": [],
    },
    {
        "id": "homelab",
        "label": "Homelab Links",
        "description": "Custom service links and status checks (Organizr-inspired)",
        "icon": "link",
        "default": True,
        "requires_path": None,
        "path_label": None,
        "category": "ops",
        "tags": [],
        "conflicts_with": [],
    },
    {
        "id": "converter",
        "label": "Converter",
        "description": "Tdarr-style transcode queue and presets",
        "icon": "cpu",
        "default": False,
        "requires_path": None,
        "path_label": None,
        "category": "ops",
        "tags": ["ffmpeg", "heavy"],
        "conflicts_with": [],
    },
    {
        "id": "adult",
        "label": "Adult",
        "description": "Adult library module (permission-gated)",
        "icon": "eye",
        "default": False,
        "requires_path": "adult_library_path",
        "path_label": "Adult library folder",
        "category": "library",
        "tags": ["path", "restricted"],
        "conflicts_with": [],
    },
]

_SETTING_KEY = "enabled_modules"


def _optional_ids() -> set[str]:
    return {m["id"] for m in OPTIONAL_MODULES}


def catalog() -> list[dict[str, Any]]:
    core = [
        {
            "id": "movies",
            "label": "Movies",
            "description": "Radarr-class movie pipeline (always on)",
            "icon": "film",
            "default": True,
            "requires_path": "movies_library_path",
            "path_label": "Movies library folder",
            "category": "core",
            "tags": ["core", "radarr"],
            "conflicts_with": [],
            "core": True,
        },
        {
            "id": "tv",
            "label": "TV",
            "description": "Sonarr-class series pipeline (always on)",
            "icon": "tv",
            "default": True,
            "requires_path": "tv_library_path",
            "path_label": "TV library folder",
            "category": "core",
            "tags": ["core", "sonarr"],
            "conflicts_with": [],
            "core": True,
        },
    ]
    out = core + [{**m, "core": False} for m in OPTIONAL_MODULES]
    return out


def get_enabled(db: Session) -> list[str]:
    row = db.query(AppSetting).filter(AppSetting.key == _SETTING_KEY).first()
    enabled: list[str] = list(CORE_MODULES)
    if row and row.value:
        try:
            data = json.loads(row.value)
            if isinstance(data, list):
                for x in data:
                    if x in _optional_ids() and x not in enabled:
                        enabled.append(str(x))
        except Exception:
            pass
    else:
        for m in OPTIONAL_MODULES:
            if m.get("default") and m["id"] not in enabled:
                enabled.append(m["id"])
    return enabled


def set_enabled(db: Session, modules: list[str]) -> list[str]:
    cleaned = list(CORE_MODULES)
    for m in modules:
        mid = str(m)
        if mid in CORE_MODULES:
            continue
        if mid in _optional_ids() and mid not in cleaned:
            cleaned.append(mid)
    row = db.query(AppSetting).filter(AppSetting.key == _SETTING_KEY).first()
    payload = json.dumps(cleaned)
    if row:
        row.value = payload
        db.add(row)
    else:
        db.add(AppSetting(key=_SETTING_KEY, value=payload))
    db.commit()
    return cleaned


def enable_module(db: Session, module_id: str) -> list[str]:
    enabled = get_enabled(db)
    if module_id in CORE_MODULES:
        return enabled
    if module_id not in _optional_ids():
        return enabled
    if module_id not in enabled:
        enabled.append(module_id)
        return set_enabled(db, enabled)
    return enabled


def disable_module(db: Session, module_id: str) -> list[str]:
    if module_id in CORE_MODULES:
        return get_enabled(db)
    enabled = [m for m in get_enabled(db) if m != module_id]
    return set_enabled(db, enabled)


def _path_configured(settings_obj, key: str | None) -> bool:
    if not key:
        return True
    try:
        val = getattr(settings_obj, key, None) or ""
        return bool(str(val).strip())
    except Exception:
        return False


def detect_conflicts(enabled: list[str]) -> list[dict[str, Any]]:
    """Soft conflicts from catalog conflicts_with + same path key used by multiple enabled modules."""
    by_id = {m["id"]: m for m in catalog()}
    issues: list[dict[str, Any]] = []
    enabled_set = set(enabled)
    for mid in enabled:
        meta = by_id.get(mid) or {}
        for other in meta.get("conflicts_with") or []:
            if other in enabled_set:
                issues.append({
                    "type": "module",
                    "modules": sorted([mid, other]),
                    "message": f"{meta.get('label', mid)} conflicts with {by_id.get(other, {}).get('label', other)}",
                })
    # same requires_path on two enabled modules
    path_owners: dict[str, list[str]] = {}
    for mid in enabled:
        meta = by_id.get(mid) or {}
        pk = meta.get("requires_path")
        if pk:
            path_owners.setdefault(pk, []).append(mid)
    for pk, owners in path_owners.items():
        if len(owners) > 1:
            issues.append({
                "type": "path",
                "path_key": pk,
                "modules": owners,
                "message": f"Modules share path setting {pk}: {', '.join(owners)}",
            })
    # dedupe
    seen = set()
    unique = []
    for i in issues:
        key = (i.get("type"), tuple(i.get("modules") or []), i.get("path_key"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(i)
    return unique


def status(db: Session) -> dict[str, Any]:
    from app.config import settings

    enabled = get_enabled(db)
    cat = []
    for m in catalog():
        on = m["id"] in enabled or m.get("core")
        path_key = m.get("requires_path")
        path_ok = _path_configured(settings, path_key) if path_key else True
        cat.append({
            **m,
            "enabled": bool(on),
            "path_configured": path_ok,
            "needs_path_setup": bool(path_key) and on and not path_ok,
        })
    return {
        "enabled": enabled,
        "catalog": cat,
        "core": list(CORE_MODULES),
        "conflicts": detect_conflicts(enabled),
        "categories": sorted({c.get("category") or "other" for c in cat}),
    }
