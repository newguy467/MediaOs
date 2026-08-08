"""Cloudflare-aware HTTP for public indexers and scrapers.

Chain (in order):
  1. curl_cffi browser TLS impersonation (built-in, no extra service)
  2. FlareSolverr sidecar when FLARESOLVERR_URL is set (real browser CF solve)
  3. Plain httpx fallback

This is how MediaOs "integrates" FlareSolverr without vendoring Chromium.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)

_IMPERSONATE_CHAIN = (
    "chrome131",
    "chrome124",
    "chrome120",
    "chrome116",
    "safari17_0",
    "safari15_5",
)


def _looks_like_cf_challenge(status: int, text: str) -> bool:
    if status in (403, 503, 429):
        blob = (text or "").lower()[:4000]
        return any(
            x in blob
            for x in (
                "cf-browser-verification",
                "cloudflare",
                "attention required",
                "just a moment",
                "cf-challenge",
                "turnstile",
                "checking your browser",
            )
        )
    return False


class CFBypassClient:
    def enabled(self) -> bool:
        return bool(getattr(settings, "cf_bypass_enabled", True))

    @property
    def flaresolverr_url(self) -> str:
        return (getattr(settings, "flaresolverr_url", None) or "").rstrip("/")

    def flaresolverr_configured(self) -> bool:
        return bool(self.flaresolverr_url)

    def get(
        self,
        url: str,
        *,
        timeout: float = 45,
        headers: dict | None = None,
        prefer_flaresolverr: bool = False,
    ) -> tuple[int, str, dict]:
        hdrs = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            **(headers or {}),
        }

        # Optional: hit FlareSolverr first when caller knows site is hard CF
        if prefer_flaresolverr and self.flaresolverr_configured():
            try:
                return self._via_flaresolverr(url, timeout=timeout)
            except Exception as e:
                log.info("prefer FlareSolverr failed, continuing chain: %s", e)

        if self.enabled():
            try:
                from curl_cffi import requests as creq
            except Exception as e:
                log.info("curl_cffi unavailable: %s", e)
                creq = None
            if creq is not None:
                preferred = getattr(settings, "cf_impersonate", None) or "chrome124"
                chain = [preferred] + [x for x in _IMPERSONATE_CHAIN if x != preferred]
                last_err = None
                for profile in chain:
                    try:
                        r = creq.get(
                            url,
                            impersonate=profile,
                            timeout=timeout,
                            headers=hdrs,
                            allow_redirects=True,
                        )
                        text = r.text or ""
                        if _looks_like_cf_challenge(r.status_code, text):
                            last_err = f"CF challenge {r.status_code} with {profile}"
                            continue
                        return r.status_code, text, dict(r.headers)
                    except Exception as e:
                        last_err = str(e)
                        continue
                log.info("curl_cffi chain exhausted (%s); trying FlareSolverr/httpx", last_err)

        if self.flaresolverr_configured():
            try:
                return self._via_flaresolverr(url, timeout=timeout)
            except Exception as e:
                log.info("FlareSolverr failed: %s", e)

        import httpx
        r = httpx.get(url, timeout=timeout, headers=hdrs, follow_redirects=True)
        return r.status_code, r.text, dict(r.headers)

    def _via_flaresolverr(self, url: str, *, timeout: float = 45) -> tuple[int, str, dict]:
        import httpx
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": int(max(timeout, 60) * 1000),
        }
        r = httpx.post(f"{self.flaresolverr_url}/v1", json=payload, timeout=timeout + 15)
        data = r.json()
        if data.get("status") and data.get("status") != "ok":
            raise RuntimeError(data.get("message") or "FlareSolverr error")
        sol = data.get("solution") or {}
        return int(sol.get("status") or r.status_code), sol.get("response") or "", dict(sol.get("headers") or {})

    def get_text(self, url: str, **kw) -> str:
        code, text, _ = self.get(url, **kw)
        if code >= 400:
            raise RuntimeError(f"CF bypass GET {code} for {url}")
        return text

    def test(self, url: str = "https://www.cloudflare.com/cdn-cgi/trace") -> dict[str, Any]:
        try:
            code, text, _ = self.get(url, timeout=20)
            engine = "curl_cffi"
            if self.flaresolverr_configured():
                engine += "+flaresolverr"
            return {
                "ok": code < 500,
                "status": code,
                "engine": engine if self.enabled() else "httpx",
                "flaresolverr": self.flaresolverr_configured(),
                "snippet": (text or "")[:120],
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "flaresolverr": self.flaresolverr_configured()}

    def status(self) -> dict[str, Any]:
        from app.clients.flaresolverr import flaresolverr_client
        return {
            "cf_bypass_enabled": self.enabled(),
            "curl_cffi": True,  # dependency in requirements
            "flaresolverr": flaresolverr_client.get_status(),
        }


cf_bypass_client = CFBypassClient()
