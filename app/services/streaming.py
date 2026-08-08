"""Streaming / .strm providers (MediaOs-style stream-without-download)."""
from __future__ import annotations

import logging
from pathlib import Path

from app.clients.realdebrid import rd_client
from app.config import settings

log = logging.getLogger(__name__)


def write_strm(path: Path, url: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(url.strip() + "\n", encoding="utf-8")
    return path


def movie_strm_path(title: str, year: int | None = None) -> Path:
    root = Path(settings.movies_library_path)
    folder = f"{title} ({year})" if year else title
    return root / folder / f"{folder}.strm"


def create_movie_strm_from_magnet(title: str, magnet: str, year: int | None = None) -> dict:
    """Prefer Real-Debrid unrestricted link; fallback to magnet URI in .strm."""
    url = None
    provider = "magnet"
    if rd_client.enabled():
        url = rd_client.best_stream_link(magnet)
        if url:
            provider = "realdebrid"
    if not url:
        url = magnet
        provider = "magnet"
    dest = movie_strm_path(title, year)
    write_strm(dest, url)
    return {"ok": True, "path": str(dest), "provider": provider, "url": url[:80] + ("…" if len(url) > 80 else "")}


def providers_status() -> list[dict]:
    return [
        {"id": "realdebrid", "name": "Real-Debrid", "enabled": rd_client.enabled(), "test": rd_client.test() if rd_client.enabled() else {}},
        {"id": "magnet_strm", "name": "Magnet/.strm fallback", "enabled": True},
        {"id": "local_download", "name": "qBittorrent download", "enabled": bool(settings.qbit_url)},
        {"id": "usenet", "name": "SABnzbd usenet", "enabled": bool(getattr(settings, "sabnzbd_url", ""))},
        {"id": "usenet_seekable", "name": "NNTP seekable stream", "enabled": bool(getattr(settings, "nntp_host", ""))},
    ]
