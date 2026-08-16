"""ListenBrainz music scrobbling — a simple bearer-token POST to submit-listens."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from app.config import settings

log = logging.getLogger(__name__)
API = "https://api.listenbrainz.org/1/submit-listens"


class ListenBrainzClient:
    def enabled(self) -> bool:
        return bool(getattr(settings, "listenbrainz_token", "") or "")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Token {settings.listenbrainz_token}",
            "Content-Type": "application/json",
        }

    def scrobble(
        self,
        artist: str,
        track: str,
        release: str | None = None,
        duration_ms: int | None = None,
        recording_mbid: str | None = None,
        timestamp: int | None = None,
    ) -> bool:
        if not self.enabled():
            return False
        if not artist or not track:
            log.debug("listenbrainz scrobble-out: missing artist/track, skipping")
            return False

        additional_info: dict[str, Any] = {}
        if duration_ms:
            additional_info["duration_ms"] = int(duration_ms)
        if recording_mbid:
            additional_info["recording_mbid"] = recording_mbid

        track_metadata: dict[str, Any] = {"artist_name": artist, "track_name": track}
        if release:
            track_metadata["release_name"] = release
        if additional_info:
            track_metadata["additional_info"] = additional_info

        payload = {
            "listen_type": "single",
            "payload": [{
                "listened_at": int(timestamp or time.time()),
                "track_metadata": track_metadata,
            }],
        }

        try:
            r = requests.post(API, headers=self._headers(), json=payload, timeout=15)
            r.raise_for_status()
            return True
        except Exception as e:
            log.warning("listenbrainz scrobble-out failed (track=%s): %s", track, e)
            return False


listenbrainz_client = ListenBrainzClient()
