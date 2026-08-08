import logging
import time

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class QBittorrentClient:
    def __init__(self):
        self.base_url = settings.qbit_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=15.0)
        self._logged_in = False

    def _login(self):
        resp = self.client.post(
            "/api/v2/auth/login",
            data={
                "username": settings.qbit_username,
                "password": settings.qbit_password,
            },
        )
        resp.raise_for_status()
        # qB returns "Ok." or "Ok" depending on version
        body = resp.text.strip().lower().rstrip(".")
        if body != "ok":
            raise RuntimeError(
                f"qBittorrent login failed (got {resp.text!r}) - check credentials"
            )
        self._logged_in = True

    def _ensure_login(self):
        if not self._logged_in:
            self._login()

    def _post_with_reauth(self, path: str, data: dict):
        self._ensure_login()
        resp = self.client.post(path, data=data)
        if resp.status_code == 403:
            self._logged_in = False
            self._ensure_login()
            resp = self.client.post(path, data=data)
        resp.raise_for_status()
        return resp

    def add_torrent(self, url: str, save_path: str, category: str = "mediaos"):
        self._post_with_reauth(
            "/api/v2/torrents/add",
            {
                "urls": url,
                "savepath": save_path,
                "category": category,
            },
        )

    def list_torrents(self, category: str | None = "mediaos") -> list[dict]:
        self._ensure_login()
        params = {}
        if category:
            params["category"] = category
        resp = self.client.get("/api/v2/torrents/info", params=params)
        if resp.status_code == 403:
            self._logged_in = False
            self._ensure_login()
            resp = self.client.get("/api/v2/torrents/info", params=params)
        resp.raise_for_status()
        return resp.json()

    def find_torrent_hash(
        self,
        release_title: str,
        category: str,
        *,
        retries: int = 8,
        delay: float = 0.75,
    ) -> str | None:
        """Poll qB until the new torrent appears. Match by exact name first,
        then by case-insensitive containment as a fallback."""
        title = (release_title or "").strip()
        title_lower = title.lower()

        for attempt in range(retries):
            try:
                torrents = self.list_torrents(category=category)
            except Exception as exc:
                log.warning("list_torrents failed on attempt %s: %s", attempt + 1, exc)
                time.sleep(delay)
                continue

            # Exact name match
            for t in torrents:
                if t.get("name") == title and t.get("hash"):
                    return t["hash"]

            # Fuzzy: release title contained in torrent name or vice versa
            for t in torrents:
                name = (t.get("name") or "").lower()
                if not name or not t.get("hash"):
                    continue
                if title_lower and (title_lower in name or name in title_lower):
                    return t["hash"]

            time.sleep(delay)

        log.warning(
            "Could not resolve torrent hash for %r in category %s after %s tries",
            release_title,
            category,
            retries,
        )
        return None

    def delete_torrent(self, torrent_hash: str, delete_files: bool = False):
        """Remove torrent from qB. Optionally delete leftover files on disk."""
        if not torrent_hash:
            return
        self._post_with_reauth(
            "/api/v2/torrents/delete",
            {
                "hashes": torrent_hash,
                "deleteFiles": "true" if delete_files else "false",
            },
        )

    def pause(self, torrent_hash: str) -> None:
        self._post_with_reauth("/api/v2/torrents/pause", {"hashes": torrent_hash})

    def resume(self, torrent_hash: str) -> None:
        self._post_with_reauth("/api/v2/torrents/resume", {"hashes": torrent_hash})

    def recheck(self, torrent_hash: str) -> None:
        self._post_with_reauth("/api/v2/torrents/recheck", {"hashes": torrent_hash})

    def set_priority(self, torrent_hash: str, priority: int) -> None:
        """Queue priority band: 1=top 2=high 3=normal 4=low 5=bottom."""
        if not torrent_hash:
            return
        path = {
            1: "/api/v2/torrents/topPrio",
            2: "/api/v2/torrents/increasePrio",
            3: None,
            4: "/api/v2/torrents/decreasePrio",
            5: "/api/v2/torrents/bottomPrio",
        }.get(int(priority), None)
        if path:
            self._post_with_reauth(path, {"hashes": torrent_hash})

    def set_category(self, torrent_hash: str, category: str) -> None:
        if not torrent_hash:
            return
        self._post_with_reauth(
            "/api/v2/torrents/setCategory",
            {"hashes": torrent_hash, "category": category or ""},
        )

    def set_force_start(self, torrent_hash: str, value: bool = True) -> None:
        if not torrent_hash:
            return
        self._post_with_reauth(
            "/api/v2/torrents/setForceStart",
            {"hashes": torrent_hash, "value": "true" if value else "false"},
        )


qbittorrent_client = QBittorrentClient()
