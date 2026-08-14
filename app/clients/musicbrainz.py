"""MusicBrainz search (no API key required; identify mediaos in User-Agent)."""
from __future__ import annotations

import hashlib

import httpx

BASE = "https://musicbrainz.org/ws/2"


def _stable_int_id(mbid: str) -> int:
    """Deterministic string -> int id, stable across process restarts.

    Python's built-in hash() is salted per-process for str objects
    (PYTHONHASHSEED) unless hash randomization is explicitly disabled, so it
    must not be used here — using it would make external_id matching for the
    same MusicBrainz UUID silently fail after every app restart, creating
    duplicate MediaItem rows instead of recognizing an already-added release.
    """
    digest = hashlib.sha256(mbid.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % (10**12)


class MusicBrainzClient:
    def _cover_url(self, mbid: str | None, kind: str = "release-group") -> str | None:
        if not mbid:
            return None
        return f"https://coverartarchive.org/{kind}/{mbid}/front-250"

    def __init__(self):
        self.client = httpx.Client(
            base_url=BASE,
            headers={"User-Agent": "mediaos/0.5.0 (self-hosted media manager)"},
            params={"fmt": "json"},
            timeout=20.0,
        )

    def search_release_group(self, query: str, limit: int = 20) -> list[dict]:
        resp = self.client.get(
            "/release-group",
            params={"query": query, "limit": limit},
        )
        resp.raise_for_status()
        rows = []
        for r in resp.json().get("release-groups", []):
            artist = ""
            ac = r.get("artist-credit") or []
            if ac:
                artist = ac[0].get("name") or ac[0].get("artist", {}).get("name") or ""
            year = None
            if r.get("first-release-date"):
                try:
                    year = int(str(r["first-release-date"])[:4])
                except ValueError:
                    pass
            # MusicBrainz IDs are UUIDs — store hash as int-like? We use string external via external_source
            # For MediaItem.external_id (int), hash the UUID stably.
            ext = _stable_int_id(r["id"])
            rows.append(
                {
                    "external_id": ext,
                    "external_mbid": r["id"],
                    "media_type": "music",
                    "title": f"{artist} - {r.get('title')}" if artist else r.get("title"),
                    "album": r.get("title"),
                    "artist": artist,
                    "year": year,
                    "overview": (r.get("primary-type") or "")
                    + (" / " + ", ".join(r.get("secondary-types") or []) if r.get("secondary-types") else ""),
                    "poster_path": self._cover_url(r.get("id")),
                }
            )
        return rows

    def get_release_group(self, mbid: str) -> dict:
        resp = self.client.get(f"/release-group/{mbid}", params={"inc": "artists"})
        resp.raise_for_status()
        r = resp.json()
        artist = ""
        ac = r.get("artist-credit") or []
        if ac:
            artist = ac[0].get("name") or ""
        year = None
        if r.get("first-release-date"):
            try:
                year = int(str(r["first-release-date"])[:4])
            except ValueError:
                pass
        ext = _stable_int_id(r["id"])
        return {
            "external_id": ext,
            "external_mbid": r["id"],
            "title": f"{artist} - {r.get('title')}" if artist else r.get("title"),
            "album": r.get("title"),
            "artist": artist,
            "year": year,
            "overview": r.get("primary-type"),
            "poster_path": self._cover_url(r.get("id")),
        }



    def search_artist(self, query: str, limit: int = 10) -> list[dict]:
        resp = self.client.get("/artist", params={"query": query, "limit": limit})
        resp.raise_for_status()
        rows = []
        for a in resp.json().get("artists", []):
            rows.append(
                {
                    "mbid": a["id"],
                    "name": a.get("name"),
                    "disambiguation": a.get("disambiguation"),
                    "type": a.get("type"),
                    "country": a.get("country"),
                }
            )
        return rows

    def artist_release_groups(self, artist_mbid: str, limit: int = 100) -> list[dict]:
        """Full discography browse (Lidarr-style)."""
        resp = self.client.get(
            "/release-group",
            params={
                "artist": artist_mbid,
                "limit": limit,
                "offset": 0,
                "type": "album|ep|single",
            },
        )
        resp.raise_for_status()
        rows = []
        for r in resp.json().get("release-groups", []):
            year = None
            if r.get("first-release-date"):
                try:
                    year = int(str(r["first-release-date"])[:4])
                except ValueError:
                    pass
            ext = _stable_int_id(r["id"])
            rows.append(
                {
                    "external_id": ext,
                    "external_mbid": r["id"],
                    "media_type": "music",
                    "title": r.get("title"),
                    "album": r.get("title"),
                    "year": year,
                    "overview": r.get("primary-type"),
                    "poster_path": self._cover_url(r.get("id")),
                }
            )
        return rows

    def release_group_tracks(self, release_group_mbid: str) -> list[dict]:
        """Track list via first release of a release-group."""
        resp = self.client.get(
            "/release",
            params={
                "release-group": release_group_mbid,
                "limit": 1,
                "inc": "recordings",
            },
        )
        resp.raise_for_status()
        releases = resp.json().get("releases") or []
        if not releases:
            return []
        rel_id = releases[0]["id"]
        resp2 = self.client.get(
            f"/release/{rel_id}",
            params={"inc": "recordings"},
        )
        resp2.raise_for_status()
        tracks = []
        for medium in resp2.json().get("media") or []:
            disc = medium.get("position") or 1
            for tr in medium.get("tracks") or []:
                rec = tr.get("recording") or {}
                tracks.append(
                    {
                        "disc": disc,
                        "position": tr.get("position"),
                        "title": tr.get("title") or rec.get("title"),
                        "length_ms": tr.get("length") or rec.get("length"),
                        "recording_mbid": rec.get("id"),
                    }
                )
        return tracks

    def lookup_release_tracks(self, release_mbid: str) -> list[dict]:
        """Return tracks for a MusicBrainz release (or release-group first release)."""
        # Try release endpoint with recordings
        try:
            r = self.client.get(
                f"/release/{release_mbid}",
                params={"inc": "recordings", "fmt": "json"},
            )
            if r.status_code == 404:
                # maybe release-group id — pick first release
                rg = self.client.get(
                    f"/release-group/{release_mbid}",
                    params={"inc": "releases", "fmt": "json"},
                )
                rg.raise_for_status()
                releases = (rg.json() or {}).get("releases") or []
                if not releases:
                    return []
                return self.lookup_release_tracks(releases[0]["id"])
            r.raise_for_status()
            data = r.json() or {}
            out = []
            for media in data.get("media") or []:
                disc = int(media.get("position") or 1)
                for tr in media.get("tracks") or []:
                    rec = tr.get("recording") or {}
                    length = rec.get("length") or tr.get("length")
                    out.append({
                        "title": tr.get("title") or rec.get("title"),
                        "track_number": int(tr.get("position") or tr.get("number") or 0) or 1,
                        "disc_number": disc,
                        "duration_ms": int(length) if length else None,
                        "recording_mbid": rec.get("id"),
                        "id": rec.get("id"),
                    })
            return out
        except Exception:
            return []


musicbrainz_client = MusicBrainzClient()

