"""Jackett API client — list indexers and build Torznab URLs for sync."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class JackettClient:
    def enabled(self) -> bool:
        return bool(getattr(settings, "jackett_url", None))

    def _base(self) -> str:
        return (getattr(settings, "jackett_url", None) or "").rstrip("/") + "/"

    def _key(self) -> str:
        return getattr(settings, "jackett_api_key", None) or ""

    def _get(self, path: str, params: dict | None = None) -> Any:
        if not self.enabled():
            raise RuntimeError("Jackett not configured (set JACKETT_URL + JACKETT_API_KEY)")
        params = dict(params or {})
        params.setdefault("apikey", self._key())
        url = urljoin(self._base(), path.lstrip("/"))
        r = httpx.get(url, params=params, timeout=45.0)
        r.raise_for_status()
        if "application/json" in (r.headers.get("content-type") or ""):
            return r.json()
        return r.text

    def list_indexers(self) -> list[dict[str, Any]]:
        """
        Jackett: GET /api/v2.0/indexers?configured=true
        Returns configured indexers with id, name, status, protocols, etc.
        """
        data = self._get("/api/v2.0/indexers", {"configured": "true"})
        if not isinstance(data, list):
            return []
        return data

    def torznab_url(self, indexer_id: str) -> str:
        """Standard Jackett Torznab results endpoint for one indexer."""
        return urljoin(
            self._base(),
            f"api/v2.0/indexers/{indexer_id}/results/torznab/",
        )

    def test(self) -> dict[str, Any]:
        try:
            idx = self.list_indexers()
            return {"ok": True, "count": len(idx), "url": self._base()}
        except Exception as e:
            return {"ok": False, "error": str(e)}



    def list_indexers_detailed(self) -> list[dict[str, Any]]:
        """UI-friendly list with Torznab URL and tags."""
        rows = self.list_indexers()
        base = self._base().rstrip("/")
        key = self._key()
        out = []
        for ix in rows:
            # Jackett indexers API shapes vary
            name = ix.get("name") or ix.get("Name") or "unknown"
            iid = ix.get("id") or ix.get("ID") or name
            configured = ix.get("configured", ix.get("Configured", True))
            caps = ix.get("caps") or ix.get("Caps") or {}
            torznab = f"{base}/api/v2.0/indexers/{iid}/results/torznab/"
            out.append({
                "id": str(iid),
                "name": name,
                "configured": bool(configured),
                "torznab_url": torznab,
                "api_key": key,
                "type": ix.get("type") or ix.get("Type") or "public",
                "needs_flaresolverr": bool(ix.get("flaresolverr") or "flare" in str(ix).lower()),
                "tags": [],
            })
        return out


jackett_client = JackettClient()

