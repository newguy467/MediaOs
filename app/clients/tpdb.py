"""ThePornDB (TPDB) metadata client for Adult / Whisparr-class library.

API: https://api.theporndb.net  (Bearer token)
Docs-oriented endpoints used:
  GET /movies?q=...
  GET /movies/{id}
  GET /scenes?q=...   (optional fallback)

When tpdb_api_key is empty, search returns [] and callers fall back to
title-only add (same as before).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("mediaos.tpdb")

BASE_URL = "https://api.theporndb.net"


class TPDBClient:
    def __init__(self) -> None:
        self._client: httpx.Client | None = None

    def _headers(self) -> dict[str, str]:
        key = (settings.tpdb_api_key or "").strip()
        h = {"Accept": "application/json", "User-Agent": "MediaOs/4.7 (TPDB)"}
        if key:
            h["Authorization"] = f"Bearer {key}"
        return h

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=BASE_URL,
                headers=self._headers(),
                timeout=20.0,
            )
        return self._client

    def configured(self) -> bool:
        return bool((settings.tpdb_api_key or "").strip())

    def _year(self, date_str: str | None) -> int | None:
        if not date_str or len(date_str) < 4:
            return None
        try:
            return int(str(date_str)[:4])
        except ValueError:
            return None

    def _poster(self, data: dict) -> str | None:
        # TPDB often nests images under poster / front / url
        for key in ("poster", "image", "thumbnail", "front"):
            val = data.get(key)
            if isinstance(val, str) and val.startswith("http"):
                return val
            if isinstance(val, dict):
                for k in ("full", "large", "medium", "url"):
                    u = val.get(k)
                    if isinstance(u, str) and u.startswith("http"):
                        return u
        imgs = data.get("images") or data.get("posters")
        if isinstance(imgs, list) and imgs:
            first = imgs[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("url") or first.get("full")
        return None

    def _row(self, data: dict, *, kind: str = "movie") -> dict[str, Any]:
        # Support both {data: {...}} envelopes and flat objects
        if "data" in data and isinstance(data["data"], dict):
            data = data["data"]
        title = (
            data.get("title")
            or data.get("name")
            or data.get("scene_name")
            or "Unknown"
        )
        ext_id = data.get("id") or data.get("_id") or data.get("uuid")
        date = data.get("date") or data.get("release_date") or data.get("created")
        site = None
        site_obj = data.get("site") or data.get("studio")
        if isinstance(site_obj, dict):
            site = site_obj.get("name")
        elif isinstance(site_obj, str):
            site = site_obj
        overview = data.get("description") or data.get("overview") or data.get("synopsis") or ""
        if site and overview:
            overview = f"[{site}] {overview}"
        elif site and not overview:
            overview = site
        return {
            "external_id": str(ext_id) if ext_id is not None else None,
            "external_source": "tpdb",
            "title": title,
            "year": self._year(date if isinstance(date, str) else None),
            "overview": overview,
            "poster_path": self._poster(data),
            "kind": kind,
            "site": site,
            "raw_id": ext_id,
        }

    def search_movies(self, query: str, limit: int = 20) -> list[dict]:
        if not self.configured():
            return []
        q = (query or "").strip()
        if not q:
            return []
        results: list[dict] = []
        for path in ("/movies", "/scenes"):
            try:
                # refresh headers in case key changed
                self.client.headers.update(self._headers())
                resp = self.client.get(path, params={"q": q, "per_page": limit})
                if resp.status_code == 401:
                    log.warning("TPDB unauthorized — check TPDB_API_KEY")
                    return []
                if resp.status_code >= 400:
                    log.debug("TPDB %s → %s", path, resp.status_code)
                    continue
                payload = resp.json()
                rows = payload.get("data") if isinstance(payload, dict) else payload
                if not isinstance(rows, list):
                    rows = payload.get("results") or []
                kind = "movie" if "movie" in path else "scene"
                for r in rows or []:
                    if isinstance(r, dict):
                        results.append(self._row(r, kind=kind))
                if results:
                    break
            except Exception as e:
                log.debug("TPDB search %s failed: %s", path, e)
        # dedupe by external_id
        seen = set()
        out = []
        for r in results:
            eid = r.get("external_id")
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            out.append(r)
        return out[:limit]

    def get_movie(self, tpdb_id: str | int) -> dict:
        if not self.configured():
            raise RuntimeError("TPDB API key not configured")
        self.client.headers.update(self._headers())
        for path in (f"/movies/{tpdb_id}", f"/scenes/{tpdb_id}"):
            try:
                resp = self.client.get(path)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                payload = resp.json()
                data = payload.get("data", payload) if isinstance(payload, dict) else payload
                if isinstance(data, dict):
                    kind = "movie" if "movie" in path else "scene"
                    return self._row(data, kind=kind)
            except Exception as e:
                log.debug("TPDB get %s: %s", path, e)
        raise LookupError(f"TPDB id not found: {tpdb_id}")


tpdb_client = TPDBClient()
