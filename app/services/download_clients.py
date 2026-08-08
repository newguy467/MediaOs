"""Unified download-client manager (qB / Transmission / Deluge / rTorrent / aria2 / SAB / NZBGet)."""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)


def list_clients() -> list[dict[str, Any]]:
    from app.clients.qbittorrent import qbittorrent_client
    from app.clients.transmission import transmission_client
    from app.clients.deluge import deluge_client
    from app.clients.rtorrent import rtorrent_client
    from app.clients.aria2 import aria2_client

    clients = [
        {
            "id": "qbittorrent",
            "name": "qBittorrent",
            "enabled": bool(getattr(settings, "qbit_url", None)),
            "kind": "torrent",
            "primary": True,
        },
        {
            "id": "transmission",
            "name": "Transmission",
            "enabled": transmission_client.enabled(),
            "kind": "torrent",
        },
        {
            "id": "deluge",
            "name": "Deluge",
            "enabled": deluge_client.enabled(),
            "kind": "torrent",
        },
        {
            "id": "rtorrent",
            "name": "rTorrent",
            "enabled": rtorrent_client.enabled(),
            "kind": "torrent",
        },
        {
            "id": "aria2",
            "name": "aria2",
            "enabled": aria2_client.enabled(),
            "kind": "torrent",
        },
        {
            "id": "sabnzbd",
            "name": "SABnzbd",
            "enabled": bool(getattr(settings, "sabnzbd_url", None)),
            "kind": "usenet",
        },
        {
            "id": "nzbget",
            "name": "NZBGet",
            "enabled": bool(getattr(settings, "nzbget_url", None)),
            "kind": "usenet",
        },
    ]
    return clients


def active_torrent_client_id() -> str:
    preferred = (getattr(settings, "torrent_client", None) or "qbittorrent").lower()
    enabled = {c["id"] for c in list_clients() if c["enabled"] and c["kind"] == "torrent"}
    if preferred in enabled:
        return preferred
    for cid in ("qbittorrent", "transmission", "deluge", "rtorrent", "aria2"):
        if cid in enabled:
            return cid
    return "qbittorrent"


def add_torrent(url: str, *, save_path: str | None = None, category: str | None = None) -> dict[str, Any]:
    """Send a magnet/torrent URL to the configured torrent client."""
    cid = active_torrent_client_id()
    path = save_path or getattr(settings, "downloads_path", "/downloads")
    if cid == "transmission":
        from app.clients.transmission import transmission_client
        return {"client": cid, "result": transmission_client.add_torrent(url, path)}
    if cid == "deluge":
        from app.clients.deluge import deluge_client
        return {"client": cid, "result": deluge_client.add_torrent(url, path)}
    if cid == "rtorrent":
        from app.clients.rtorrent import rtorrent_client
        rtorrent_client.add_torrent(url, path)
        return {"client": cid, "result": "ok"}
    if cid == "aria2":
        from app.clients.aria2 import aria2_client
        gid = aria2_client.add_torrent(url, path)
        return {"client": cid, "result": gid}
    # default qB
    from app.clients.qbittorrent import qbittorrent_client
    qbittorrent_client.add_torrent(url=url, save_path=path, category=category or "mediaos")
    return {"client": "qbittorrent", "result": "ok"}


def list_torrents() -> list[dict[str, Any]]:
    cid = active_torrent_client_id()
    try:
        if cid == "transmission":
            from app.clients.transmission import transmission_client
            return transmission_client.list_torrents()
        if cid == "deluge":
            from app.clients.deluge import deluge_client
            return deluge_client.list_torrents()
        if cid == "rtorrent":
            from app.clients.rtorrent import rtorrent_client
            return rtorrent_client.list_torrents()
        if cid == "aria2":
            from app.clients.aria2 import aria2_client
            return aria2_client.list_torrents()
        from app.clients.qbittorrent import qbittorrent_client
        return qbittorrent_client.list_torrents(category=None)
    except Exception as e:
        log.warning("list_torrents via %s failed: %s", cid, e)
        return []


def pause_torrent(torrent_hash: str) -> dict:
    cid = active_torrent_client_id()
    try:
        if cid == "qbittorrent":
            from app.clients.qbittorrent import qbittorrent_client
            qbittorrent_client.pause(torrent_hash)
        elif cid == "transmission":
            from app.clients.transmission import transmission_client
            transmission_client.pause(torrent_hash)
        elif cid == "deluge":
            from app.clients.deluge import deluge_client
            deluge_client.pause(torrent_hash)
        elif cid == "rtorrent":
            from app.clients.rtorrent import rtorrent_client
            rtorrent_client.pause(torrent_hash)
        elif cid == "aria2":
            from app.clients.aria2 import aria2_client
            aria2_client.pause(torrent_hash)
        return {"ok": True, "action": "pause", "client": cid, "hash": torrent_hash}
    except Exception as e:
        return {"ok": False, "error": str(e), "client": cid}


def resume_torrent(torrent_hash: str) -> dict:
    cid = active_torrent_client_id()
    try:
        if cid == "qbittorrent":
            from app.clients.qbittorrent import qbittorrent_client
            qbittorrent_client.resume(torrent_hash)
        elif cid == "transmission":
            from app.clients.transmission import transmission_client
            transmission_client.resume(torrent_hash)
        elif cid == "deluge":
            from app.clients.deluge import deluge_client
            deluge_client.resume(torrent_hash)
        elif cid == "rtorrent":
            from app.clients.rtorrent import rtorrent_client
            rtorrent_client.resume(torrent_hash)
        elif cid == "aria2":
            from app.clients.aria2 import aria2_client
            aria2_client.resume(torrent_hash)
        return {"ok": True, "action": "resume", "client": cid, "hash": torrent_hash}
    except Exception as e:
        return {"ok": False, "error": str(e), "client": cid}


def recheck_torrent(torrent_hash: str) -> dict:
    cid = active_torrent_client_id()
    try:
        if cid == "qbittorrent":
            from app.clients.qbittorrent import qbittorrent_client
            qbittorrent_client.recheck(torrent_hash)
        elif cid == "transmission":
            from app.clients.transmission import transmission_client
            transmission_client.recheck(torrent_hash)
        elif cid == "deluge":
            from app.clients.deluge import deluge_client
            deluge_client.recheck(torrent_hash)
        elif cid == "rtorrent":
            from app.clients.rtorrent import rtorrent_client
            rtorrent_client.recheck(torrent_hash)
        elif cid == "aria2":
            from app.clients.aria2 import aria2_client
            aria2_client.recheck(torrent_hash)
        return {"ok": True, "action": "recheck", "client": cid, "hash": torrent_hash}
    except Exception as e:
        return {"ok": False, "error": str(e), "client": cid}


def set_torrent_priority(torrent_hash: str, priority: int) -> dict:
    """priority: 1=top 2=high 3=normal 4=low 5=bottom (qBittorrent bands)."""
    cid = active_torrent_client_id()
    try:
        if cid == "qbittorrent":
            from app.clients.qbittorrent import qbittorrent_client
            qbittorrent_client.set_priority(torrent_hash, priority)
        else:
            return {"ok": False, "error": f"priority not supported on {cid}", "client": cid}
        return {"ok": True, "action": "priority", "priority": priority, "client": cid, "hash": torrent_hash}
    except Exception as e:
        return {"ok": False, "error": str(e), "client": cid}


def set_torrent_category(torrent_hash: str, category: str) -> dict:
    cid = active_torrent_client_id()
    try:
        if cid == "qbittorrent":
            from app.clients.qbittorrent import qbittorrent_client
            qbittorrent_client.set_category(torrent_hash, category)
        else:
            return {"ok": False, "error": f"category not supported on {cid}", "client": cid}
        return {"ok": True, "action": "category", "category": category, "client": cid, "hash": torrent_hash}
    except Exception as e:
        return {"ok": False, "error": str(e), "client": cid}


def force_start_torrent(torrent_hash: str, value: bool = True) -> dict:
    cid = active_torrent_client_id()
    try:
        if cid == "qbittorrent":
            from app.clients.qbittorrent import qbittorrent_client
            qbittorrent_client.set_force_start(torrent_hash, value)
        else:
            return {"ok": False, "error": f"force-start not supported on {cid}", "client": cid}
        return {"ok": True, "action": "force_start", "value": value, "client": cid, "hash": torrent_hash}
    except Exception as e:
        return {"ok": False, "error": str(e), "client": cid}
