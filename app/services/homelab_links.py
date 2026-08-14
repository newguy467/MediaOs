"""
LEGACY: JSON/AppSetting-backed Homelab links.

Prefer /api/homelab/* (HomelabLink model + router) for the UI Homelab page.
This module remains for /api/system/homelab-links compatibility.

Homelab Apps / Links page (Organizr-lite).

Persists user links in app_settings under key `homelab_links_json`.
Safe defaults ship for Jellyfin / qBittorrent / Portainer / Docs.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import AppSetting

log = logging.getLogger(__name__)

SETTING_KEY = "homelab_links_json"

DEFAULT_LINKS: list[dict[str, Any]] = [
    {"name": "Jellyfin", "url": "http://jellyfin:8096", "icon": "play", "iframe": True},
    {"name": "qBittorrent", "url": "http://qbittorrent:8080", "icon": "download", "iframe": True},
    {"name": "Portainer", "url": "http://portainer:9000", "icon": "box", "iframe": False},
    {"name": "Docs", "url": "https://github.com/newguy467/mediaos", "icon": "book", "iframe": False},
]


def _validate_link(item: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    name = str(item.get("name") or "").strip()
    url = str(item.get("url") or "").strip()
    if not name or not url:
        return None
    # Basic URL safety — no javascript: etc.
    lower = url.lower()
    if lower.startswith("javascript:") or lower.startswith("data:"):
        return None
    return {
        "name": name[:80],
        "url": url[:500],
        "icon": str(item.get("icon") or "box")[:32],
        "iframe": bool(item.get("iframe", False)),
    }


def get_links(db: Session | None = None) -> list[dict[str, Any]]:
    """Return persisted links, or defaults if none saved."""
    if db is None:
        return list(DEFAULT_LINKS)
    try:
        row = db.get(AppSetting, SETTING_KEY)
        if not row or not row.value:
            return list(DEFAULT_LINKS)
        raw = json.loads(row.value)
        if not isinstance(raw, list):
            return list(DEFAULT_LINKS)
        out = []
        for item in raw:
            v = _validate_link(item)
            if v:
                out.append(v)
        return out or list(DEFAULT_LINKS)
    except Exception as e:
        log.warning("homelab get_links failed: %s", e)
        return list(DEFAULT_LINKS)


def save_links(db: Session, links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and persist links. Returns the saved list."""
    cleaned: list[dict[str, Any]] = []
    for item in links or []:
        v = _validate_link(item)
        if v:
            cleaned.append(v)
    # Cap list size
    cleaned = cleaned[:40]
    payload = json.dumps(cleaned)
    row = db.get(AppSetting, SETTING_KEY)
    if row is None:
        row = AppSetting(key=SETTING_KEY, value=payload)
        db.add(row)
    else:
        row.value = payload
    db.commit()
    return cleaned
