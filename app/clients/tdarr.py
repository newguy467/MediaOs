"""Optional external Tdarr server client (classic Tdarr UI/nodes).

MediaOS runs a native Tdarr-class converter (queue, presets, watch folders,
health checks, retries). When TDARR_URL is set, this client can report status
and optionally mirror library roots into Tdarr for operators who still want
the classic Tdarr UI alongside MediaOS.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class TdarrClient:
    def __init__(self) -> None:
        self.base = (getattr(settings, "tdarr_url", None) or "").rstrip("/")
        self.api_key = (getattr(settings, "tdarr_api_key", None) or "").strip()

    @property
    def enabled(self) -> bool:
        return bool(getattr(settings, "tdarr_enabled", False) and self.base)

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
            h["x-api-key"] = self.api_key
        return h

    def status(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "reachable": False}
        try:
            with httpx.Client(base_url=self.base, timeout=8.0, headers=self._headers()) as c:
                # Tdarr API varies by version; try common endpoints
                for path in ("/api/v2/status", "/api/v2/stats", "/api/status", "/"):
                    try:
                        r = c.get(path)
                        if r.status_code < 500:
                            return {
                                "enabled": True,
                                "reachable": r.status_code < 400,
                                "status_code": r.status_code,
                                "path": path,
                                "body": (r.json() if "json" in r.headers.get("content-type", "") else r.text[:500]),
                            }
                    except Exception:
                        continue
            return {"enabled": True, "reachable": False, "error": "no responding endpoint"}
        except Exception as e:
            return {"enabled": True, "reachable": False, "error": str(e)[:200]}


tdarr_client = TdarrClient()
