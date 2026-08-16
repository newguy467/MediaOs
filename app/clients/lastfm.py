"""Last.fm music scrobbling — signed track.scrobble via the Audioscrobbler API."""
from __future__ import annotations

import hashlib
import logging
import time

import requests

from app.config import settings

log = logging.getLogger(__name__)
API = "https://ws.audioscrobbler.com/2.0/"


class LastfmClient:
    def enabled(self) -> bool:
        return bool(
            getattr(settings, "lastfm_api_key", "")
            and getattr(settings, "lastfm_api_secret", "")
            and getattr(settings, "lastfm_session_key", "")
        )

    def _sign(self, params: dict[str, str]) -> str:
        """Last.fm's request-signing scheme: concatenate every param name+value
        pair sorted alphabetically by name (excluding 'format' and 'callback'),
        append the shared api secret, then md5 the whole string.
        """
        ordered = "".join(f"{k}{params[k]}" for k in sorted(params) if k not in ("format", "callback"))
        raw = (ordered + settings.lastfm_api_secret).encode("utf-8")
        return hashlib.md5(raw).hexdigest()

    def scrobble(
        self,
        artist: str,
        track: str,
        album: str | None = None,
        duration_seconds: int | None = None,
        timestamp: int | None = None,
    ) -> bool:
        """Push a completed play to Last.fm.

        Requires a pre-authorized session key (lastfm_session_key). Obtaining
        one is a one-time out-of-band handshake — auth.getToken, the user
        authorizing that token in a browser, then auth.getSession to exchange
        it for a session key — which is not implemented here; the resulting
        key is pasted directly into Settings once obtained.
        """
        if not self.enabled():
            return False
        if not artist or not track:
            log.debug("lastfm scrobble-out: missing artist/track, skipping")
            return False

        params = {
            "method": "track.scrobble",
            "artist": artist,
            "track": track,
            "timestamp": str(timestamp or int(time.time())),
            "api_key": settings.lastfm_api_key,
            "sk": settings.lastfm_session_key,
        }
        if album:
            params["album"] = album
        if duration_seconds:
            params["duration"] = str(duration_seconds)
        params["api_sig"] = self._sign(params)
        params["format"] = "json"

        try:
            r = requests.post(API, data=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            attrs = (data.get("scrobbles") or {}).get("@attr") or {}
            if "accepted" in attrs:
                return int(attrs["accepted"]) > 0
            return "error" not in data
        except Exception as e:
            log.warning("lastfm scrobble-out failed (track=%s): %s", track, e)
            return False


lastfm_client = LastfmClient()
