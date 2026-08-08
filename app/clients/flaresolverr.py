"""FlareSolverr client — Cloudflare / anti-bot bypass for HTTP fetches."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class FlareSolverrClient:
    def __init__(self) -> None:
        self._client = httpx.Client(timeout=120.0)

    @property
    def enabled(self) -> bool:
        return bool((settings.flaresolverr_url or "").strip())

    def _endpoint(self) -> str:
        return settings.flaresolverr_url.rstrip("/") + "/v1"

    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        post_data: str | None = None,
        max_timeout_ms: int = 60000,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("FlareSolverr not configured (FLARESOLVERR_URL)")

        payload: dict[str, Any] = {
            "cmd": "request.get" if method.upper() == "GET" else "request.post",
            "url": url,
            "maxTimeout": max_timeout_ms,
        }
        if headers:
            payload["headers"] = headers
        if method.upper() == "POST" and post_data is not None:
            payload["postData"] = post_data

        r = self._client.post(self._endpoint(), json=payload)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "ok":
            raise RuntimeError(data.get("message") or "FlareSolverr error")
        return data.get("solution") or {}

    def get_text(self, url: str, **kwargs) -> str:
        sol = self.request(url, method="GET", **kwargs)
        return sol.get("response") or ""

    def get_text_auto(self, url: str, **kwargs) -> str:
        """Prefer FlareSolverr; fall back to direct GET."""
        if self.enabled:
            try:
                return self.get_text(url, **kwargs)
            except Exception as exc:
                log.warning("FlareSolverr failed, direct fallback: %s", exc)
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.text

    def get_status(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False}
        try:
            r = self._client.get(settings.flaresolverr_url.rstrip("/") + "/")
            return {
                "enabled": True,
                "url": settings.flaresolverr_url,
                "reachable": r.status_code < 500,
                "status_code": r.status_code,
            }
        except Exception as exc:
            return {
                "enabled": True,
                "url": settings.flaresolverr_url,
                "reachable": False,
                "error": str(exc),
            }


flaresolverr_client = FlareSolverrClient()
