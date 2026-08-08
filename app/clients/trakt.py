"""Trakt.tv lists / trending for smart lists & discover."""
from __future__ import annotations

import logging
from typing import Any

import requests

from app.config import settings

log = logging.getLogger(__name__)
API = "https://api.trakt.tv"


class TraktClient:
    def enabled(self) -> bool:
        return bool(getattr(settings, "trakt_client_id", "") or "")

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": settings.trakt_client_id,
        }
        if getattr(settings, "trakt_access_token", ""):
            h["Authorization"] = f"Bearer {settings.trakt_access_token}"
        return h

    def trending_movies(self, limit: int = 20) -> list[dict]:
        if not self.enabled():
            return []
        r = requests.get(f"{API}/movies/trending", headers=self._headers(), params={"limit": limit}, timeout=20)
        r.raise_for_status()
        out = []
        for row in r.json():
            m = row.get("movie") or {}
            ids = m.get("ids") or {}
            out.append({
                "title": m.get("title"),
                "year": m.get("year"),
                "tmdb_id": ids.get("tmdb"),
                "trakt_id": ids.get("trakt"),
                "imdb_id": ids.get("imdb"),
                "external_id": ids.get("tmdb"),
                "watchers": row.get("watchers"),
            })
        return out

    def trending_shows(self, limit: int = 20) -> list[dict]:
        if not self.enabled():
            return []
        r = requests.get(f"{API}/shows/trending", headers=self._headers(), params={"limit": limit}, timeout=20)
        r.raise_for_status()
        out = []
        for row in r.json():
            s = row.get("show") or {}
            ids = s.get("ids") or {}
            out.append({
                "title": s.get("title"),
                "year": s.get("year"),
                "tmdb_id": ids.get("tmdb"),
                "tvdb_id": ids.get("tvdb"),
                "trakt_id": ids.get("trakt"),
                "imdb_id": ids.get("imdb"),
                "external_id": ids.get("tvdb") or ids.get("tmdb"),
                "watchers": row.get("watchers"),
            })
        return out

    def list_items(self, username: str, list_id: str) -> list[dict]:
        """Return normalized movie/show rows from a user list.
        list_id may be numeric id or slug.
        """
        if not self.enabled():
            return []
        r = requests.get(
            f"{API}/users/{username}/lists/{list_id}/items",
            headers=self._headers(),
            timeout=30,
            params={"extended": "full"},
        )
        r.raise_for_status()
        out: list[dict] = []
        for row in r.json() or []:
            kind = row.get("type")
            obj = row.get(kind) or row.get("movie") or row.get("show") or {}
            ids = obj.get("ids") or {}
            tmdb = ids.get("tmdb")
            out.append({
                "title": obj.get("title"),
                "year": obj.get("year"),
                "overview": obj.get("overview"),
                "tmdb_id": tmdb,
                "tvdb_id": ids.get("tvdb"),
                "trakt_id": ids.get("trakt"),
                "imdb_id": ids.get("imdb"),
                "external_id": tmdb,
                "media_type": "movie" if kind == "movie" else "tv",
                "vote_average": (obj.get("rating") or 0) * 2 if obj.get("rating") else None,
            })
        return out

    def popular_movies(self, limit: int = 50) -> list[dict]:
        if not self.enabled():
            return []
        r = requests.get(f"{API}/movies/popular", headers=self._headers(), params={"limit": limit}, timeout=20)
        r.raise_for_status()
        out = []
        for m in r.json():
            ids = m.get("ids") or {}
            out.append({
                "title": m.get("title"),
                "year": m.get("year"),
                "tmdb_id": ids.get("tmdb"),
                "imdb_id": ids.get("imdb"),
                "external_id": ids.get("tmdb"),
            })
        return out

    def test(self) -> dict:
        if not self.enabled():
            return {"ok": False, "error": "not configured"}
        try:
            self.trending_movies(1)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}


trakt_client = TraktClient()
