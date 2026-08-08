"""aria2 JSON-RPC client."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class Aria2Client:
    def enabled(self) -> bool:
        return bool(getattr(settings, "aria2_url", None))

    def _rpc(self, method: str, params: list | None = None) -> Any:
        if not self.enabled():
            raise RuntimeError("aria2 not configured")
        url = (getattr(settings, "aria2_url", None) or "").rstrip("/")
        token = getattr(settings, "aria2_secret", None) or ""
        params = params or []
        if token:
            params = [f"token:{token}", *params]
        payload = {"jsonrpc": "2.0", "id": "mediaos", "method": method, "params": params}
        r = httpx.post(url, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(str(data["error"]))
        return data.get("result")

    def add_torrent(self, url: str, download_dir: str | None = None) -> str:
        opts = {}
        if download_dir:
            opts["dir"] = download_dir
        return self._rpc("aria2.addUri", [[url], opts])

    def list_torrents(self) -> list[dict]:
        active = self._rpc("aria2.tellActive") or []
        waiting = self._rpc("aria2.tellWaiting", [0, 50]) or []
        stopped = self._rpc("aria2.tellStopped", [0, 50]) or []
        return list(active) + list(waiting) + list(stopped)

    def delete_torrent(self, gid: str, delete_files: bool = False) -> None:
        try:
            self._rpc("aria2.remove", [gid])
        except Exception:
            self._rpc("aria2.forceRemove", [gid])
        if delete_files:
            try:
                self._rpc("aria2.removeDownloadResult", [gid])
            except Exception:
                pass



    def pause(self, gid: str) -> None:
        try:
            self._rpc("aria2.pause", [gid])
        except Exception:
            self._rpc("aria2.forcePause", [gid])

    def resume(self, gid: str) -> None:
        self._rpc("aria2.unpause", [gid])

    def recheck(self, gid: str) -> None:
        # aria2 has no direct recheck; re-announce / pause-unpause best-effort
        try:
            self._rpc("aria2.forcePause", [gid])
            self._rpc("aria2.unpause", [gid])
        except Exception:
            pass


aria2_client = Aria2Client()

