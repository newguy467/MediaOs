"""rTorrent XML-RPC client (ruTorrent / SCGI gateway HTTP)."""
from __future__ import annotations

import logging
import xmlrpc.client

from app.config import settings

log = logging.getLogger(__name__)


class RTorrentClient:
    def enabled(self) -> bool:
        return bool(getattr(settings, "rtorrent_url", None))

    def _proxy(self) -> xmlrpc.client.ServerProxy:
        url = (getattr(settings, "rtorrent_url", None) or "").rstrip("/")
        return xmlrpc.client.ServerProxy(url)

    def add_torrent(self, url: str, download_dir: str | None = None) -> None:
        if not self.enabled():
            raise RuntimeError("rTorrent not configured")
        proxy = self._proxy()
        if download_dir:
            proxy.load.start_verbose("", url, f"d.directory.set={download_dir}")
        else:
            proxy.load.start("", url)

    def list_torrents(self) -> list[dict]:
        if not self.enabled():
            return []
        proxy = self._proxy()
        # multicall common fields
        rows = proxy.d.multicall2(
            "",
            "main",
            "d.name=",
            "d.hash=",
            "d.complete=",
            "d.bytes_done=",
            "d.size_bytes=",
            "d.down.rate=",
            "d.ratio=",
            "d.is_private=",
        )
        out = []
        for r in rows or []:
            out.append({
                "name": r[0],
                "hash": r[1],
                "complete": r[2],
                "bytes_done": r[3],
                "size": r[4],
                "down_rate": r[5],
                "ratio": (r[6] or 0) / 1000.0,
                "is_private": bool(r[7]),
            })
        return out

    def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> None:
        proxy = self._proxy()
        if delete_files:
            proxy.d.custom5.set(torrent_hash, "1")  # hint; erase still needed
        proxy.d.erase(torrent_hash)



    def pause(self, torrent_hash: str) -> None:
        self._proxy().d.stop(torrent_hash)

    def resume(self, torrent_hash: str) -> None:
        self._proxy().d.start(torrent_hash)

    def recheck(self, torrent_hash: str) -> None:
        # rTorrent: hash check
        try:
            self._proxy().d.check_hash(torrent_hash)
        except Exception:
            self._proxy().d.hashing_start(torrent_hash)


rtorrent_client = RTorrentClient()

