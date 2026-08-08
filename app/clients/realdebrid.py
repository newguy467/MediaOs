"""Real-Debrid integration for torrent→link and .strm streaming."""
from __future__ import annotations

import logging
from typing import Any

import requests

from app.config import settings

log = logging.getLogger(__name__)
API = "https://api.real-debrid.com/rest/1.0"


class RealDebridClient:
    def enabled(self) -> bool:
        return bool(getattr(settings, "real_debrid_token", "") or "")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {settings.real_debrid_token}"}

    def user(self) -> dict:
        if not self.enabled():
            return {}
        r = requests.get(f"{API}/user", headers=self._headers(), timeout=15)
        r.raise_for_status()
        return r.json()

    def add_magnet(self, magnet: str) -> dict:
        r = requests.post(f"{API}/torrents/addMagnet", headers=self._headers(), data={"magnet": magnet}, timeout=30)
        r.raise_for_status()
        return r.json()

    def select_files(self, torrent_id: str, files: str = "all") -> None:
        requests.post(
            f"{API}/torrents/selectFiles/{torrent_id}",
            headers=self._headers(),
            data={"files": files},
            timeout=30,
        ).raise_for_status()

    def torrent_info(self, torrent_id: str) -> dict:
        r = requests.get(f"{API}/torrents/info/{torrent_id}", headers=self._headers(), timeout=20)
        r.raise_for_status()
        return r.json()

    def unrestrict(self, link: str) -> dict:
        r = requests.post(f"{API}/unrestrict/link", headers=self._headers(), data={"link": link}, timeout=30)
        r.raise_for_status()
        return r.json()

    def best_stream_link(self, magnet: str) -> str | None:
        """Add magnet, select all, wait briefly, return unrestricted download link."""
        if not self.enabled():
            return None
        try:
            added = self.add_magnet(magnet)
            tid = added.get("id")
            if not tid:
                return None
            self.select_files(tid, "all")
            info = self.torrent_info(tid)
            links = info.get("links") or []
            if not links:
                return None
            unrestricted = self.unrestrict(links[0])
            return unrestricted.get("download") or unrestricted.get("link")
        except Exception as e:
            log.warning("RD stream: %s", e)
            return None

    def test(self) -> dict:
        if not self.enabled():
            return {"ok": False, "error": "not configured"}
        try:
            u = self.user()
            return {"ok": True, "username": u.get("username"), "premium": u.get("type")}
        except Exception as e:
            return {"ok": False, "error": str(e)}


rd_client = RealDebridClient()
