"""SABnzbd usenet download client."""
from __future__ import annotations

import logging
from typing import Any

import requests

from app.config import settings

log = logging.getLogger(__name__)


class SabnzbdClient:
    def enabled(self) -> bool:
        return bool(getattr(settings, "sabnzbd_url", "") and getattr(settings, "sabnzbd_api_key", ""))

    def _url(self, mode: str, **params) -> str:
        base = (settings.sabnzbd_url or "").rstrip("/")
        q = {"mode": mode, "apikey": settings.sabnzbd_api_key, "output": "json", **params}
        from urllib.parse import urlencode
        return f"{base}/api?{urlencode(q)}"

    def add_nzb_url(self, nzb_url: str, *, category: str = "mediaos", name: str | None = None) -> dict:
        if not self.enabled():
            return {"ok": False, "error": "SABnzbd not configured"}
        params: dict[str, Any] = {"name": nzb_url, "cat": category}
        if name:
            params["nzbname"] = name
        r = requests.get(self._url("addurl", **params), timeout=30)
        r.raise_for_status()
        data = r.json()
        return {"ok": bool(data.get("status", True)), "raw": data}

    def history(self, limit: int = 20) -> list:
        if not self.enabled():
            return []
        r = requests.get(self._url("history", limit=limit), timeout=20)
        r.raise_for_status()
        return (r.json().get("history") or {}).get("slots") or []

    def queue(self) -> list:
        if not self.enabled():
            return []
        r = requests.get(self._url("queue"), timeout=20)
        r.raise_for_status()
        return (r.json().get("queue") or {}).get("slots") or []

    def test(self) -> dict:
        if not self.enabled():
            return {"ok": False, "error": "not configured"}
        try:
            r = requests.get(self._url("version"), timeout=10)
            r.raise_for_status()
            return {"ok": True, "version": r.json().get("version")}
        except Exception as e:
            return {"ok": False, "error": str(e)}


sabnzbd_client = SabnzbdClient()
