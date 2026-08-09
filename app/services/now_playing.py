"""Plex / Tautulli now-playing snapshot for the dashboard widget."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("mediaos.now_playing")


def _tautulli_sessions() -> list[dict[str, Any]]:
    base = (settings.tautulli_url or "").rstrip("/")
    key = settings.tautulli_api_key or ""
    if not base or not key:
        return []
    url = f"{base}/api/v2"
    params = {"apikey": key, "cmd": "get_activity"}
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json().get("response", {}).get("data", {})
            sessions = data.get("sessions") or []
            out = []
            for s in sessions:
                out.append({
                    "source": "tautulli",
                    "user": s.get("user") or s.get("friendly_name"),
                    "title": s.get("full_title") or s.get("title"),
                    "state": s.get("state"),
                    "progress_percent": s.get("progress_percent"),
                    "player": s.get("player"),
                    "media_type": s.get("media_type"),
                })
            return out
    except Exception as e:
        log.warning("tautulli activity failed: %s", e)
        return []


def _plex_sessions() -> list[dict[str, Any]]:
    base = (settings.plex_url or "").rstrip("/")
    token = settings.plex_token or ""
    if not base or not token:
        return []
    url = f"{base}/status/sessions"
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(url, params={"X-Plex-Token": token}, headers={"Accept": "application/json"})
            r.raise_for_status()
            data = r.json()
            media = (data.get("MediaContainer") or {}).get("Metadata") or []
            out = []
            for m in media:
                title = m.get("title") or ""
                if m.get("grandparentTitle"):
                    title = f"{m.get('grandparentTitle')} — {title}"
                user = None
                if m.get("User"):
                    user = m["User"].get("title")
                out.append({
                    "source": "plex",
                    "user": user,
                    "title": title,
                    "state": "playing",
                    "progress_percent": None,
                    "player": (m.get("Player") or {}).get("title"),
                    "media_type": m.get("type"),
                })
            return out
    except Exception as e:
        log.warning("plex sessions failed: %s", e)
        return []


def get_now_playing() -> dict[str, Any]:
    sessions = _tautulli_sessions() or _plex_sessions()
    configured = bool(
        (settings.tautulli_url and settings.tautulli_api_key)
        or (settings.plex_url and settings.plex_token)
    )
    return {
        "ok": True,
        "configured": configured,
        "count": len(sessions),
        "sessions": sessions,
        "hint": None if configured else "Set TAUTULLI_URL + TAUTULLI_API_KEY or PLEX_URL + PLEX_TOKEN",
    }
