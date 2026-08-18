"""NZBGet usenet download client."""
from __future__ import annotations

import logging
from xmlrpc.client import ServerProxy

from app.config import settings

log = logging.getLogger(__name__)


class NzbgetClient:
    def enabled(self) -> bool:
        return bool(getattr(settings, "nzbget_url", "") or "")

    def _proxy(self) -> ServerProxy:
        base = (settings.nzbget_url or "").rstrip("/")
        user = getattr(settings, "nzbget_username", "") or ""
        password = getattr(settings, "nzbget_password", "") or ""
        if user:
            # http://user:pass@host:port/xmlrpc
            if "://" in base:
                scheme, rest = base.split("://", 1)
                url = f"{scheme}://{user}:{password}@{rest}/xmlrpc"
            else:
                url = f"http://{user}:{password}@{base}/xmlrpc"
        else:
            url = f"{base}/xmlrpc"
        return ServerProxy(url, allow_none=True)

    def append(
        self,
        nzb_content_or_url: str,
        *,
        category: str | None = None,
        name: str | None = None,
        priority: int = 0,
    ) -> dict:
        if not self.enabled():
            return {"ok": False, "error": "NZBGet not configured"}
        cat = category or getattr(settings, "nzbget_category", "mediaos") or "mediaos"
        try:
            proxy = self._proxy()
            # Append(NZBFilename, NZBContent, Category, Priority, AddToTop, AddPaused, DupeKey, DupeScore, DupeMode, ...)
            # When content looks like a URL, pass empty content and URL as filename for fetch.
            if nzb_content_or_url.startswith("http://") or nzb_content_or_url.startswith("https://"):
                nzb_id = proxy.append(
                    name or "mediaos",
                    nzb_content_or_url,
                    cat,
                    priority,
                    False,
                    False,
                    "",
                    0,
                    "SCORE",
                )
            else:
                nzb_id = proxy.append(
                    name or "mediaos.nzb",
                    nzb_content_or_url,
                    cat,
                    priority,
                    False,
                    False,
                    "",
                    0,
                    "SCORE",
                )
            return {"ok": True, "id": nzb_id}
        except Exception as e:
            log.warning("NZBGet append failed: %s", e)
            return {"ok": False, "error": str(e)}

    def list_groups(self) -> list[dict]:
        if not self.enabled():
            return []
        try:
            return list(self._proxy().listgroups() or [])
        except Exception as e:
            log.debug("NZBGet listgroups: %s", e)
            return []

    def history(self, limit: int = 30) -> list[dict]:
        if not self.enabled():
            return []
        try:
            rows = list(self._proxy().history() or [])
            return rows[:limit]
        except Exception as e:
            log.debug("NZBGet history: %s", e)
            return []

    def status(self) -> dict:
        if not self.enabled():
            return {"ok": False, "error": "not configured"}
        try:
            s = self._proxy().status()
            return {"ok": True, "status": s}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def test(self) -> dict:
        if not self.enabled():
            return {"ok": False, "error": "not configured"}
        try:
            ver = self._proxy().version()
            return {"ok": True, "version": ver}
        except Exception as e:
            return {"ok": False, "error": str(e)}


nzbget_client = NzbgetClient()
