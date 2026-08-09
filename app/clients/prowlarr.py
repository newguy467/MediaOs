import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

# Prowlarr / Torznab standard categories
MOVIE_CATEGORY = 2000
TV_CATEGORY = 5000
AUDIO_CATEGORY = 3000
BOOK_CATEGORY = 7000
AUDIOBOOK_CATEGORY = 3030
XXX_CATEGORY = 6000


class ProwlarrClient:
    def enabled(self) -> bool:
        return bool((getattr(settings, "prowlarr_url", None) or "").strip() and (getattr(settings, "prowlarr_api_key", None) or "").strip())

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=(settings.prowlarr_url or "").rstrip("/"),
            headers={"X-Api-Key": settings.prowlarr_api_key or ""},
            timeout=30.0,
        )

    def test_connection(self) -> dict[str, Any]:
        if not self.enabled():
            return {"ok": False, "error": "not configured"}
        try:
            with self._client() as c:
                r = c.get("/api/v1/system/status")
                r.raise_for_status()
                data = r.json()
                return {"ok": True, "version": data.get("version"), "appName": data.get("appName")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def list_tags(self) -> list[dict[str, Any]]:
        if not self.enabled():
            return []
        try:
            with self._client() as c:
                r = c.get("/api/v1/tag")
                r.raise_for_status()
                return r.json() or []
        except Exception as e:
            log.warning("prowlarr tags: %s", e)
            return []

    def list_indexers(self) -> list[dict[str, Any]]:
        """Prowlarr indexer definitions currently configured (enabled or not)."""
        if not self.enabled():
            return []
        tags = {t.get("id"): t.get("label") for t in self.list_tags()}
        with self._client() as c:
            r = c.get("/api/v1/indexer")
            r.raise_for_status()
            rows = r.json() or []
        out = []
        for ix in rows:
            tag_ids = ix.get("tags") or []
            tag_labels = [tags.get(tid, str(tid)) for tid in tag_ids]
            # Prefer FlareSolverr / cardigann-ish tags
            needs_flare = any(
                "flare" in (t or "").lower() or "cloudflare" in (t or "").lower() or "cf" == (t or "").lower()
                for t in tag_labels
            )
            # Protocol + fields
            protocol = (ix.get("protocol") or "torrent").lower()
            fields = {f.get("name"): f.get("value") for f in (ix.get("fields") or []) if isinstance(f, dict)}
            base_url = fields.get("baseUrl") or fields.get("baseurl") or ""
            api_path = fields.get("apiPath") or "/api"
            # Prowlarr exposes per-indexer Torznab via its own proxy
            pid = ix.get("id")
            prowlarr_base = (settings.prowlarr_url or "").rstrip("/")
            torznab_url = f"{prowlarr_base}/{pid}/api" if pid is not None else ""
            out.append({
                "id": pid,
                "name": ix.get("name"),
                "definition_name": ix.get("definitionName") or ix.get("name"),
                "enable": bool(ix.get("enable")),
                "priority": ix.get("priority", 25),
                "protocol": protocol,
                "privacy": ix.get("privacy") or fields.get("privacy"),
                "tags": tag_labels,
                "tag_ids": tag_ids,
                "needs_flaresolverr": needs_flare,
                "base_url": base_url,
                "torznab_url": torznab_url,
                "categories": [c.get("id") or c for c in (ix.get("capabilities", {}) or {}).get("categories", [])] if isinstance(ix.get("capabilities"), dict) else [],
                "app_profile_id": ix.get("appProfileId"),
            })
        return out

    def test_indexer(self, indexer_id: int) -> dict[str, Any]:
        if not self.enabled():
            return {"ok": False, "error": "not configured"}
        try:
            with self._client() as c:
                # Fetch full resource then POST test
                r = c.get(f"/api/v1/indexer/{indexer_id}")
                r.raise_for_status()
                body = r.json()
                tr = c.post("/api/v1/indexer/test", json=body)
                if tr.status_code >= 400:
                    return {"ok": False, "error": tr.text[:300], "status": tr.status_code}
                return {"ok": True, "id": indexer_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def search(self, query: str, category: int = MOVIE_CATEGORY) -> list[dict]:
        if not self.enabled():
            return []
        with self._client() as c:
            resp = c.get(
                "/api/v1/search",
                params={"query": query, "categories": str(category), "type": "search"},
            )
            resp.raise_for_status()
            releases = resp.json()
        results = []
        for r in releases:
            download_url = r.get("downloadUrl") or r.get("magnetUrl")
            if not download_url:
                continue
            results.append({
                "title": r.get("title"),
                "indexer": r.get("indexer"),
                "size": r.get("size"),
                "seeders": r.get("seeders"),
                "download_url": download_url,
                "protocol": (r.get("protocol") or "torrent").lower(),
                "info_hash": r.get("infoHash") or r.get("infohash"),
            })
        return results


prowlarr_client = ProwlarrClient()
