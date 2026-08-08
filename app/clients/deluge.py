"""Deluge JSON-RPC client (WebUI)."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class DelugeClient:
    def __init__(self) -> None:
        self._id = 0

    def enabled(self) -> bool:
        return bool(getattr(settings, "deluge_url", None))

    def _url(self) -> str:
        return (getattr(settings, "deluge_url", None) or "").rstrip("/") + "/json"

    def _rpc(self, method: str, params: list | None = None) -> Any:
        if not self.enabled():
            raise RuntimeError("Deluge not configured")
        self._id += 1
        payload = {"method": method, "params": params or [], "id": self._id}
        with httpx.Client(timeout=30) as client:
            # login
            pw = getattr(settings, "deluge_password", "") or ""
            if pw:
                client.post(self._url(), json={"method": "auth.login", "params": [pw], "id": 0})
            r = client.post(self._url(), json=payload)
            r.raise_for_status()
            data = r.json()
            if data.get("error"):
                raise RuntimeError(str(data["error"]))
            return data.get("result")

    def add_torrent(self, url: str, download_dir: str | None = None) -> Any:
        options = {}
        if download_dir:
            options["download_location"] = download_dir
        return self._rpc("core.add_torrent_url", [url, options])

    def list_torrents(self) -> list[dict]:
        keys = ["name", "hash", "state", "progress", "download_payload_rate", "ratio", "total_size", "is_private"]
        result = self._rpc("core.get_torrents_status", [{}, keys]) or {}
        out = []
        for h, row in result.items():
            row = dict(row)
            row["hash"] = h
            out.append(row)
        return out

    def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> None:
        self._rpc("core.remove_torrent", [torrent_hash, bool(delete_files)])



    def pause(self, torrent_hash: str) -> None:
        self._rpc("core.pause_torrent", [[torrent_hash]])

    def resume(self, torrent_hash: str) -> None:
        self._rpc("core.resume_torrent", [[torrent_hash]])

    def recheck(self, torrent_hash: str) -> None:
        self._rpc("core.force_recheck", [[torrent_hash]])


deluge_client = DelugeClient()

