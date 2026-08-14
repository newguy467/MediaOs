"""Steam Store / Web API helpers for Games module metadata + ownership hints."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_STORE = "https://store.steampowered.com/api"
_API = "https://api.steampowered.com"


def _api_key() -> str:
    return (getattr(settings, "steam_api_key", None) or "").strip()


def search_store(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Unofficial store search (no key required)."""
    q = (query or "").strip()
    if not q:
        return []
    try:
        with httpx.Client(timeout=20.0) as client:
            # Prefer store search endpoint
            r = client.get(
                f"{_STORE}/storesearch/",
                params={"term": q, "l": "english", "cc": "US"},
            )
            if r.status_code != 200:
                # fallback: steam spy-less simple HTML-free endpoint
                r = client.get(
                    "https://store.steampowered.com/api/storesearch/",
                    params={"term": q, "l": "english", "cc": "US"},
                )
            r.raise_for_status()
            data = r.json()
            items = data.get("items") or data.get("hits") or []
            out = []
            for it in items[:limit]:
                appid = it.get("id") or it.get("appid")
                out.append({
                    "steam_appid": appid,
                    "title": it.get("name") or it.get("title"),
                    "poster_path": (it.get("tiny_image") or it.get("small_capsule") or None),
                    "price": (it.get("price") or {}).get("final") if isinstance(it.get("price"), dict) else it.get("price"),
                    "platforms": it.get("platforms") or {},
                    "source": "steam",
                    "url": f"https://store.steampowered.com/app/{appid}/" if appid else None,
                })
            return out
    except Exception as e:
        log.warning("Steam store search failed: %s", e)
        return []


def app_details(appid: int) -> dict[str, Any] | None:
    try:
        with httpx.Client(timeout=25.0) as client:
            r = client.get(f"{_STORE}/appdetails", params={"appids": int(appid), "l": "english"})
            r.raise_for_status()
            data = r.json()
            block = data.get(str(appid)) or data.get(appid)
            if not block or not block.get("success"):
                return None
            d = block.get("data") or {}
            genres = [g.get("description") for g in (d.get("genres") or []) if isinstance(g, dict)]
            return {
                "steam_appid": appid,
                "title": d.get("name"),
                "overview": d.get("short_description") or d.get("detailed_description"),
                "poster_path": d.get("header_image"),
                "screenshots": [s.get("path_full") for s in (d.get("screenshots") or []) if isinstance(s, dict)][:12],
                "developers": d.get("developers") or [],
                "publishers": d.get("publishers") or [],
                "genres": genres,
                "release_date": (d.get("release_date") or {}).get("date"),
                "website": d.get("website"),
                "source": "steam",
                "url": f"https://store.steampowered.com/app/{appid}/",
            }
    except Exception as e:
        log.warning("Steam appdetails failed: %s", e)
        return None


def owned_games(steam_id: str | None = None) -> list[dict[str, Any]]:
    """Requires STEAM_API_KEY + steam id (64-bit)."""
    key = _api_key()
    sid = (steam_id or getattr(settings, "steam_user_id", None) or "").strip()
    if not key or not sid:
        return []
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                f"{_API}/IPlayerService/GetOwnedGames/v1/",
                params={
                    "key": key,
                    "steamid": sid,
                    "include_appinfo": 1,
                    "include_played_free_games": 1,
                },
            )
            r.raise_for_status()
            games = ((r.json().get("response") or {}).get("games")) or []
            return [
                {
                    "steam_appid": g.get("appid"),
                    "title": g.get("name"),
                    "playtime_minutes": g.get("playtime_forever"),
                    "source": "steam_library",
                }
                for g in games
            ]
    except Exception as e:
        log.warning("Steam owned games failed: %s", e)
        return []


def search(query: str, limit: int = 20) -> list[dict]:
    return search_store(query, limit=limit)
