"""Notify cross-seed daemon on completed downloads."""
from __future__ import annotations

import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)


def notify_cross_seed(*, info_hash: str | None = None, path: str | None = None) -> bool:
    base = (settings.cross_seed_url or "").rstrip("/")
    if not base:
        return False
    if not info_hash and not path:
        return False
    url = f"{base}/api/webhook"
    headers = {}
    key = (settings.cross_seed_api_key or "").strip()
    if key:
        headers["X-Api-Key"] = key
    data: dict = {}
    if info_hash:
        data["infoHash"] = info_hash
    if path:
        data["path"] = path
    data["includeSingleEpisodes"] = True
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(url, data=data, headers=headers)
            if r.status_code in (200, 204):
                log.info("cross-seed notified hash=%s path=%s", info_hash, path)
                return True
            log.warning("cross-seed response %s: %s", r.status_code, r.text[:200])
    except Exception as exc:
        log.warning("cross-seed notify failed: %s", exc)
    return False
