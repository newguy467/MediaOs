"""OpenSubtitles.com REST API client (v1).

Requires OPENSUBTITLES_API_KEY. Optional username/password for higher quotas
and authenticated download.
"""
from __future__ import annotations

import logging
import struct
from pathlib import Path

import httpx

from app.config import settings

log = logging.getLogger(__name__)

BASE = "https://api.opensubtitles.com/api/v1"
USER_AGENT = "mediaos v2.6.1"


def movie_hash(path: Path) -> str | None:
    """OpenSubtitles moviehash: size + XOR of first/last 64 KiB as little-endian u64s."""
    try:
        size = path.stat().st_size
        if size < 65536 * 2:
            return None
        with path.open("rb") as f:
            head = f.read(65536)
            f.seek(max(0, size - 65536))
            tail = f.read(65536)
        h = size
        for chunk in (head, tail):
            for i in range(0, 65536, 8):
                (n,) = struct.unpack("<Q", chunk[i : i + 8])
                h = (h + n) & 0xFFFFFFFFFFFFFFFF
        return f"{h:016x}"
    except Exception as exc:
        log.debug("moviehash failed for %s: %s", path, exc)
        return None


class OpenSubtitlesClient:
    def __init__(self) -> None:
        self._token: str | None = None
        self._client = httpx.Client(
            base_url=BASE,
            timeout=30.0,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def _headers(self) -> dict[str, str]:
        h = {"Api-Key": settings.opensubtitles_api_key}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def login(self) -> bool:
        user = (settings.opensubtitles_username or "").strip()
        pw = (settings.opensubtitles_password or "").strip()
        if not user or not pw:
            return False
        try:
            r = self._client.post(
                "/login",
                headers=self._headers(),
                json={"username": user, "password": pw},
            )
            r.raise_for_status()
            self._token = r.json().get("token")
            return bool(self._token)
        except Exception as exc:
            log.warning("OpenSubtitles login failed: %s", exc)
            return False

    def search(
        self,
        *,
        languages: str = "en",
        tmdb_id: int | None = None,
        parent_tmdb_id: int | None = None,
        season_number: int | None = None,
        episode_number: int | None = None,
        query: str | None = None,
        moviehash: str | None = None,
        type_: str | None = None,
    ) -> list[dict]:
        params: dict = {"languages": languages, "order_by": "download_count", "order_direction": "desc"}
        if tmdb_id is not None:
            params["tmdb_id"] = tmdb_id
        if parent_tmdb_id is not None:
            params["parent_tmdb_id"] = parent_tmdb_id
        if season_number is not None:
            params["season_number"] = season_number
        if episode_number is not None:
            params["episode_number"] = episode_number
        if query:
            params["query"] = query
        if moviehash:
            params["moviehash"] = moviehash
        if type_:
            params["type"] = type_

        try:
            r = self._client.get("/subtitles", headers=self._headers(), params=params)
            r.raise_for_status()
            return r.json().get("data") or []
        except Exception as exc:
            log.warning("OpenSubtitles search failed: %s", exc)
            return []

    def download_file_id(self, file_id: int) -> tuple[str, str] | None:
        """Return (temporary_url, suggested_filename) or None."""
        if not self._token:
            self.login()
        try:
            r = self._client.post(
                "/download",
                headers=self._headers(),
                json={"file_id": file_id},
            )
            r.raise_for_status()
            data = r.json()
            link = data.get("link")
            name = data.get("file_name") or f"{file_id}.srt"
            if not link:
                return None
            return link, name
        except Exception as exc:
            log.warning("OpenSubtitles download request failed: %s", exc)
            return None

    def fetch_best_srt(
        self,
        dest_video: Path,
        *,
        languages: str = "en",
        tmdb_id: int | None = None,
        parent_tmdb_id: int | None = None,
        season: int | None = None,
        episode: int | None = None,
        title_query: str | None = None,
        hearing_impaired: str = "include",
    ) -> Path | None:
        """Search, download best match, write .srt next to video. Returns path or None."""
        if not settings.opensubtitles_api_key:
            return None
        if not dest_video.exists():
            return None

        langs = [x.strip() for x in languages.split(",") if x.strip()] or ["en"]
        lang_param = ",".join(langs)

        # Prefer hash match when possible
        mh = movie_hash(dest_video)
        rows = []
        if mh:
            rows = self.search(languages=lang_param, moviehash=mh)
        if not rows and tmdb_id is not None:
            rows = self.search(
                languages=lang_param,
                tmdb_id=tmdb_id,
                type_="movie" if season is None else "episode",
            )
        if not rows and parent_tmdb_id is not None and season is not None:
            rows = self.search(
                languages=lang_param,
                parent_tmdb_id=parent_tmdb_id,
                season_number=season,
                episode_number=episode,
                type_="episode",
            )
        if not rows and title_query:
            rows = self.search(
                languages=lang_param,
                query=title_query,
                season_number=season,
                episode_number=episode,
            )

        # Hearing-impaired preference: prefer | include | exclude
        hi_pref = (hearing_impaired or "include").lower()
        if hi_pref in ("prefer", "exclude") and rows:
            def _is_hi(row: dict) -> bool:
                attrs = row.get("attributes") or {}
                return bool(attrs.get("hearing_impaired"))
            if hi_pref == "prefer":
                hi_rows = [r for r in rows if _is_hi(r)]
                if hi_rows:
                    rows = hi_rows + [r for r in rows if not _is_hi(r)]
            elif hi_pref == "exclude":
                non = [r for r in rows if not _is_hi(r)]
                if non:
                    rows = non

        if not rows:
            log.info("No subtitles found for %s", dest_video.name)
            return None

        # Pick first with a file_id, prefer matching language order
        file_id = None
        for row in rows:
            attrs = row.get("attributes") or {}
            lang = (attrs.get("language") or "").lower()
            files = attrs.get("files") or []
            if not files:
                continue
            fid = files[0].get("file_id")
            if fid is None:
                continue
            if lang in langs or not langs:
                file_id = int(fid)
                break
            if file_id is None:
                file_id = int(fid)

        if file_id is None:
            return None

        got = self.download_file_id(file_id)
        if not got:
            return None
        link, _suggested = got

        # Save as video_stem.lang.srt (or .srt for single lang)
        primary = langs[0] if langs else "en"
        srt_name = f"{dest_video.stem}.{primary}.srt" if len(langs) > 1 else f"{dest_video.stem}.srt"
        srt_path = dest_video.parent / srt_name
        existing = list(dest_video.parent.glob(f"{dest_video.stem}*.srt"))
        if existing:
            log.debug("Subtitle already present: %s", existing[0])
            return existing[0]
        if srt_path.exists():
            log.debug("Subtitle already present: %s", srt_path)
            return srt_path

        try:
            r = httpx.get(link, timeout=60.0, follow_redirects=True)
            r.raise_for_status()
            srt_path.write_bytes(r.content)
            log.info("Downloaded subtitle → %s", srt_path)
            return srt_path
        except Exception as exc:
            log.warning("Failed to write subtitle %s: %s", srt_path, exc)
            return None


opensubtitles_client = OpenSubtitlesClient()
