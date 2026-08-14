"""ComicVine metadata client for comics/graphic novels."""
from __future__ import annotations
import logging
from typing import Any
import httpx
from app.config import settings
log = logging.getLogger(__name__)
BASE = "https://comicvine.gamespot.com/api"

class ComicVineClient:
    def __init__(self) -> None:
        self._key = (settings.comicvine_api_key or "").strip()
    @property
    def configured(self) -> bool:
        return bool(self._key)
    def _get(self, path: str, params: dict | None = None) -> dict:
        if not self._key:
            return {}
        p = dict(params or {})
        p["api_key"] = self._key
        p["format"] = "json"
        with httpx.Client(timeout=25.0, follow_redirects=True) as client:
            r = client.get(f"{BASE}/{path.lstrip('/')}", params=p)
            r.raise_for_status()
            data = r.json()
            if data.get("error") and data.get("error") != "OK":
                log.warning("ComicVine error: %s", data.get("error"))
                return {}
            return data
    def search_volumes(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        data = self._get("search/", {"query": query, "resources": "volume", "limit": min(limit, 50)})
        results = []
        for row in data.get("results") or []:
            vid = row.get("id")
            if not vid: continue
            results.append({
                "external_id": int(vid), "external_source": "comicvine",
                "title": row.get("name") or "Unknown", "year": _year(row.get("start_year")),
                "overview": row.get("deck") or row.get("description"),
                "poster_path": (row.get("image") or {}).get("medium_url") or (row.get("image") or {}).get("thumb_url"),
                "publisher": (row.get("publisher") or {}).get("name"),
                "count_of_issues": row.get("count_of_issues"), "media_kind": "comic", "series_name": row.get("name"),
            })
        return results
    def search_issues(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        data = self._get("search/", {"query": query, "resources": "issue", "limit": min(limit, 50)})
        results = []
        for row in data.get("results") or []:
            iid = row.get("id")
            if not iid: continue
            vol = row.get("volume") or {}
            results.append({
                "external_id": int(iid), "external_source": "comicvine",
                "title": row.get("name") or vol.get("name") or "Unknown",
                "issue_number": row.get("issue_number"), "year": _year((row.get("cover_date") or "")[:4]),
                "overview": row.get("deck"), "poster_path": (row.get("image") or {}).get("medium_url"),
                "volume_name": vol.get("name"), "media_kind": "comic_issue",
            })
        return results

    def volume_issues(self, volume_id: int, limit: int = 500) -> list[dict[str, Any]]:
        """List issues for a ComicVine volume id with pagination.

        ComicVine volume payloads only embed issue stubs (id/name). We always
        re-query the issues endpoint with filter=volume:ID and page through
        results so covers, deck, and cover_date are populated.
        """
        out: list[dict[str, Any]] = []
        offset = 0
        page_size = 100
        field_list = "id,issue_number,name,cover_date,deck,image,volume"
        while len(out) < limit:
            filtered = self._get(
                "issues/",
                {
                    "filter": f"volume:{int(volume_id)}",
                    "limit": page_size,
                    "offset": offset,
                    "sort": "cover_date:asc",
                    "field_list": field_list,
                },
            )
            rows = filtered.get("results") or []
            if not rows:
                break
            for row in rows:
                iid = row.get("id")
                if not iid:
                    continue
                img = row.get("image") or {}
                out.append({
                    "external_id": int(iid),
                    "external_source": "comicvine",
                    "issue_number": str(row.get("issue_number") or ""),
                    "title": row.get("name") or f"Issue {row.get('issue_number')}",
                    "cover_date": row.get("cover_date"),
                    "overview": row.get("deck"),
                    "poster_path": img.get("medium_url") or img.get("small_url") or img.get("thumb_url"),
                })
                if len(out) >= limit:
                    break
            # API total
            total = int(filtered.get("number_of_total_results") or 0)
            offset += len(rows)
            if offset >= total or len(rows) < page_size:
                break
        return out[:limit]


def _year(val):
    if val is None: return None
    try: return int(str(val)[:4])
    except Exception: return None


comicvine_client = ComicVineClient()
