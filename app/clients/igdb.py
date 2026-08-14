"""IGDB (Twitch) metadata client — Questarr-depth game search & detail."""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_TOKEN: str | None = None
_TOKEN_EXP: float = 0.0
_BASE = "https://api.igdb.com/v4"


def _cfg() -> tuple[str, str]:
    client_id = (getattr(settings, "igdb_client_id", None) or getattr(settings, "twitch_client_id", None) or "").strip()
    secret = (getattr(settings, "igdb_client_secret", None) or getattr(settings, "twitch_client_secret", None) or "").strip()
    return client_id, secret


def configured() -> bool:
    c, s = _cfg()
    return bool(c and s)


def enabled() -> bool:
    return configured()


def _oauth_token() -> str | None:
    global _TOKEN, _TOKEN_EXP
    if _TOKEN and time.time() < _TOKEN_EXP - 60:
        return _TOKEN
    client_id, secret = _cfg()
    if not client_id or not secret:
        return None
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(
                "https://id.twitch.tv/oauth2/token",
                params={
                    "client_id": client_id,
                    "client_secret": secret,
                    "grant_type": "client_credentials",
                },
            )
            r.raise_for_status()
            data = r.json()
            _TOKEN = data["access_token"]
            _TOKEN_EXP = time.time() + int(data.get("expires_in", 3600))
            return _TOKEN
    except Exception as e:
        log.warning("IGDB oauth failed: %s", e)
        return None


def _headers() -> dict[str, str] | None:
    client_id, _ = _cfg()
    tok = _oauth_token()
    if not client_id or not tok:
        return None
    return {"Client-ID": client_id, "Authorization": f"Bearer {tok}"}


def _post(path: str, body: str) -> list[dict]:
    headers = _headers()
    if not headers:
        return []
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{_BASE}/{path}", headers=headers, content=body)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
    except Exception as e:
        log.warning("IGDB %s failed: %s", path, e)
        return []


def search_games(query: str, *, limit: int = 25) -> list[dict[str, Any]]:
    q = (query or "").strip().replace('"', "")
    if not q:
        return []
    if not configured():
        return [{"id": None, "title": q, "source": "local", "note": "IGDB not configured — set IGDB_CLIENT_ID/SECRET"}]

    body = (
        f'search "{q}"; '
        f"fields id,name,slug,summary,first_release_date,cover.image_id,genres.name,"
        f"platforms.name,platforms.slug,rating,rating_count,category,url; "
        f"limit {int(limit)};"
    )
    rows = _post("games", body)
    out = []
    for g in rows:
        cover = None
        if isinstance(g.get("cover"), dict) and g["cover"].get("image_id"):
            cover = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{g['cover']['image_id']}.jpg"
        platforms = []
        for p in g.get("platforms") or []:
            if isinstance(p, dict):
                platforms.append({"name": p.get("name"), "slug": p.get("slug")})
        genres = [x.get("name") for x in (g.get("genres") or []) if isinstance(x, dict) and x.get("name")]
        year = None
        if g.get("first_release_date"):
            try:
                year = int(time.gmtime(int(g["first_release_date"])).tm_year)
            except Exception:
                pass
        out.append({
            "igdb_id": g.get("id"),
            "title": g.get("name"),
            "slug": g.get("slug"),
            "overview": g.get("summary"),
            "year": year,
            "poster_path": cover,
            "platforms": platforms,
            "genres": genres,
            "rating": g.get("rating"),
            "rating_count": g.get("rating_count"),
            "url": g.get("url"),
            "source": "igdb",
        })
    return out


def game_detail(igdb_id: int) -> dict[str, Any] | None:
    body = (
        f"where id = {int(igdb_id)}; "
        "fields id,name,slug,summary,storyline,first_release_date,cover.image_id,"
        "genres.name,platforms.name,platforms.slug,rating,rating_count,"
        "involved_companies.company.name,involved_companies.developer,"
        "involved_companies.publisher,websites.url,websites.category,"
        "screenshots.image_id,videos.video_id,similar_games.name,similar_games.id,url; "
        "limit 1;"
    )
    rows = _post("games", body)
    if not rows:
        return None
    g = rows[0]
    cover = None
    if isinstance(g.get("cover"), dict) and g["cover"].get("image_id"):
        cover = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{g['cover']['image_id']}.jpg"
    screenshots = []
    for s in g.get("screenshots") or []:
        if isinstance(s, dict) and s.get("image_id"):
            screenshots.append(f"https://images.igdb.com/igdb/image/upload/t_screenshot_med/{s['image_id']}.jpg")
    developers, publishers = [], []
    for ic in g.get("involved_companies") or []:
        if not isinstance(ic, dict):
            continue
        name = (ic.get("company") or {}).get("name") if isinstance(ic.get("company"), dict) else None
        if not name:
            continue
        if ic.get("developer"):
            developers.append(name)
        if ic.get("publisher"):
            publishers.append(name)
    year = None
    if g.get("first_release_date"):
        try:
            year = int(time.gmtime(int(g["first_release_date"])).tm_year)
        except Exception:
            pass
    return {
        "igdb_id": g.get("id"),
        "title": g.get("name"),
        "slug": g.get("slug"),
        "overview": g.get("summary") or g.get("storyline"),
        "year": year,
        "poster_path": cover,
        "screenshots": screenshots,
        "platforms": [
            {"name": p.get("name"), "slug": p.get("slug")}
            for p in (g.get("platforms") or [])
            if isinstance(p, dict)
        ],
        "genres": [x.get("name") for x in (g.get("genres") or []) if isinstance(x, dict)],
        "developers": developers,
        "publishers": publishers,
        "rating": g.get("rating"),
        "url": g.get("url"),
        "source": "igdb",
    }


def search(query: str, limit: int = 25) -> list[dict]:
    return search_games(query, limit=limit)
