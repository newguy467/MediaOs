"""Transmission RPC client (download client parity)."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class TransmissionClient:
    def __init__(self) -> None:
        self._session_id: str | None = None

    def _url(self) -> str:
        base = (getattr(settings, "transmission_url", None) or "").rstrip("/")
        return f"{base}/transmission/rpc"

    def enabled(self) -> bool:
        return bool(getattr(settings, "transmission_url", None))

    def _rpc(self, method: str, arguments: dict | None = None) -> dict:
        if not self.enabled():
            raise RuntimeError("Transmission not configured")
        headers = {}
        if self._session_id:
            headers["X-Transmission-Session-Id"] = self._session_id
        payload = {"method": method, "arguments": arguments or {}}
        auth = None
        user = getattr(settings, "transmission_username", "") or ""
        pw = getattr(settings, "transmission_password", "") or ""
        if user:
            auth = (user, pw)
        with httpx.Client(timeout=30, auth=auth) as client:
            r = client.post(self._url(), json=payload, headers=headers)
            if r.status_code == 409:
                self._session_id = r.headers.get("X-Transmission-Session-Id")
                headers["X-Transmission-Session-Id"] = self._session_id or ""
                r = client.post(self._url(), json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            if data.get("result") != "success":
                raise RuntimeError(data.get("result") or "Transmission RPC error")
            return data.get("arguments") or {}

    def add_torrent(self, url: str, download_dir: str | None = None) -> dict:
        args: dict[str, Any] = {"filename": url}
        if download_dir:
            args["download-dir"] = download_dir
        return self._rpc("torrent-add", args)

    def list_torrents(self) -> list[dict]:
        args = self._rpc("torrent-get", {"fields": ["id", "name", "hashString", "status", "percentDone", "rateDownload", "uploadRatio", "isPrivate", "totalSize"]})
        return args.get("torrents") or []

    def delete_torrent(self, torrent_id: int | str, delete_files: bool = False) -> None:
        self._rpc("torrent-remove", {"ids": [torrent_id], "delete-local-data": bool(delete_files)})

    def pause(self, torrent_id) -> None:
        self._rpc("torrent-stop", {"ids": [torrent_id]})

    def resume(self, torrent_id) -> None:
        self._rpc("torrent-start", {"ids": [torrent_id]})

    def recheck(self, torrent_id) -> None:
        self._rpc("torrent-verify", {"ids": [torrent_id]})


transmission_client = TransmissionClient()
