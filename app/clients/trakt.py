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

    def watchlist(self, media_type: str = "movies") -> list[dict]:
        """media_type: movies | shows."""
        if not self.enabled() or not getattr(settings, "trakt_access_token", ""):
            return []
        path = "movies" if media_type.startswith("movie") else "shows"
        try:
            r = requests.get(f"{API}/users/me/watchlist/{path}", headers=self._headers(), timeout=20)
            r.raise_for_status()
            out = []
            for row in r.json() or []:
                m = row.get("movie") or row.get("show") or {}
                ids = m.get("ids") or {}
                out.append({
                    "title": m.get("title"),
                    "year": m.get("year"),
                    "status": "planned",
                    "media_type": "movie" if path == "movies" else "tv",
                    "external_id": ids.get("tmdb") or ids.get("trakt"),
                    "tmdb_id": ids.get("tmdb"),
                })
            return out
        except Exception as e:
            log.warning("trakt watchlist: %s", e)
            return []

    def history(self, media_type: str = "movies", limit: int = 50) -> list[dict]:
        if not self.enabled() or not getattr(settings, "trakt_access_token", ""):
            return []
        path = "movies" if media_type.startswith("movie") else "episodes"
        try:
            r = requests.get(
                f"{API}/users/me/history/{path}",
                headers=self._headers(),
                params={"limit": limit},
                timeout=20,
            )
            r.raise_for_status()
            out = []
            for row in r.json() or []:
                m = row.get("movie") or (row.get("show") if row.get("show") else None) or {}
                if row.get("episode") and row.get("show"):
                    show = row["show"]
                    ep = row["episode"]
                    out.append({
                        "title": show.get("title"),
                        "year": show.get("year"),
                        "status": "completed",
                        "media_type": "tv",
                        "external_id": (show.get("ids") or {}).get("tmdb"),
                        "season": ep.get("season"),
                        "episode": ep.get("number"),
                        "progress": 100,
                    })
                else:
                    ids = (m.get("ids") or {}) if m else {}
                    out.append({
                        "title": (m or {}).get("title"),
                        "year": (m or {}).get("year"),
                        "status": "completed",
                        "media_type": "movie",
                        "external_id": ids.get("tmdb"),
                        "progress": 100,
                    })
            return out
        except Exception as e:
            log.warning("trakt history: %s", e)
            return []

    def scrobble(
        self,
        progress: float,
        media_item_id=None,
        event: str = "scrobble",
        *,
        tmdb_id: int | None = None,
        imdb_id: str | None = None,
        media_type: str = "movie",
        title: str | None = None,
        year: int | None = None,
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Push a play-state update to Trakt's real /scrobble/{start,pause,stop} API.

        Previously this only logged at debug level and returned True
        unconditionally — the trakt_scrobble_out setting looked like it
        worked (no error surfaced anywhere) but never actually reached
        Trakt. Callers must pass tmdb_id/imdb_id (plus season/episode for TV)
        so we can build the `ids` object Trakt requires; without at least
        one id we still return False rather than silently no-op'ing.
        """
        if not self.enabled() or not getattr(settings, "trakt_access_token", ""):
            return False
        if not tmdb_id and not imdb_id:
            log.debug("trakt scrobble-out: no tmdb_id/imdb_id for item=%s, skipping", media_item_id)
            return False

        action = {
            "start": "start", "resume": "start", "playbackstart": "start", "progress": "start", "playbackprogress": "start",
            "pause": "pause", "playbackpause": "pause",
            "stop": "stop", "scrobble": "stop", "playbackstop": "stop",
        }.get((event or "").lower(), "start")

        ids: dict[str, Any] = {}
        if tmdb_id:
            ids["tmdb"] = int(tmdb_id)
        if imdb_id:
            ids["imdb"] = imdb_id

        payload: dict[str, Any] = {"progress": max(0.0, min(100.0, float(progress or 0)))}
        is_episode = media_type == "tv" and season is not None and episode is not None
        if is_episode:
            payload["show"] = {"ids": ids, **({"title": title} if title else {}), **({"year": year} if year else {})}
            payload["episode"] = {"season": int(season), "number": int(episode)}
        else:
            payload["movie"] = {"ids": ids, **({"title": title} if title else {}), **({"year": year} if year else {})}

        try:
            r = requests.post(f"{API}/scrobble/{action}", headers=self._headers(), json=payload, timeout=15)
            r.raise_for_status()
            return True
        except Exception as e:
            log.warning("trakt scrobble-out failed (action=%s item=%s): %s", action, media_item_id, e)
            return False


trakt_client = TraktClient()
