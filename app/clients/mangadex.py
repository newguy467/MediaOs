"""MangaDex metadata client — no API key required."""
from __future__ import annotations
import hashlib, logging
from typing import Any
import httpx
log = logging.getLogger(__name__)
BASE = "https://api.mangadex.org"

class MangaDexClient:
    def __init__(self) -> None:
        self.client = httpx.Client(base_url=BASE, timeout=25.0, follow_redirects=True)
    def search_manga(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        resp = self.client.get("/manga", params={
            "title": query, "limit": min(limit, 50),
            "includes[]": ["cover_art", "author", "artist"],
            "order[relevance]": "desc",
            "contentRating[]": ["safe", "suggestive", "erotica"],
        })
        resp.raise_for_status()
        out = []
        for row in resp.json().get("data") or []:
            mid = row.get("id")
            if not mid: continue
            attrs = row.get("attributes") or {}
            title = _pick_title(attrs.get("title") or {})
            desc = _pick_title(attrs.get("description") or {})
            year = attrs.get("year")
            out.append({
                "external_id": _stable_int_id(mid), "external_source": "mangadex",
                "mangadex_uuid": mid, "title": title or "Unknown",
                "year": int(year) if year else None,
                "overview": (desc or "")[:2000] or None,
                "poster_path": _cover_url(row),
                "author": ", ".join(_rel_names(row, "author")) or None,
                "status": attrs.get("status"), "media_kind": "manga",
            })
        return out

    def list_chapters(self, manga_uuid: str, limit: int = 100, translated_lang: str = "en") -> list[dict[str, Any]]:
        """List chapters for a MangaDex manga UUID."""
        resp = self.client.get("/chapter", params={
            "manga": manga_uuid,
            "limit": min(limit, 100),
            "translatedLanguage[]": translated_lang,
            "order[chapter]": "asc",
            "includes[]": ["scanlation_group"],
        })
        resp.raise_for_status()
        out = []
        for row in resp.json().get("data") or []:
            attrs = row.get("attributes") or {}
            cid = row.get("id")
            out.append({
                "external_id": _stable_int_id(cid) if cid else None,
                "external_source": "mangadex",
                "mangadex_uuid": cid,
                "issue_number": str(attrs.get("chapter") or attrs.get("volume") or ""),
                "title": attrs.get("title") or f"Ch. {attrs.get('chapter')}",
                "cover_date": (attrs.get("publishAt") or "")[:10] or None,
                "overview": None,
                "poster_path": None,
            })
        return out

    def resolve_uuid_from_stable_id(self, stable_id: int, title_hint: str | None = None) -> str | None:
        """Best-effort: re-search by title to recover UUID (stable int is hash-only)."""
        if not title_hint:
            return None
        found = self.search_manga(title_hint, limit=5)
        for f in found:
            if f.get("external_id") == stable_id:
                return f.get("mangadex_uuid")
        return found[0].get("mangadex_uuid") if found else None


def _pick_title(mapping):
    if not mapping: return None
    for lang in ("en", "ja-ro", "ja"):
        if mapping.get(lang): return mapping[lang]
    return next(iter(mapping.values()), None)

def _cover_url(row):
    mid = row.get("id")
    for rel in row.get("relationships") or []:
        if rel.get("type") == "cover_art":
            fn = ((rel.get("attributes") or {}).get("fileName"))
            if mid and fn:
                return f"https://uploads.mangadex.org/covers/{mid}/{fn}.256.jpg"
    return None

def _rel_names(row, rel_type):
    names = []
    for rel in row.get("relationships") or []:
        if rel.get("type") == rel_type:
            n = (rel.get("attributes") or {}).get("name")
            if n: names.append(n)
    return names

def _stable_int_id(uuid_str):
    return int(hashlib.sha1(uuid_str.encode()).hexdigest()[:15], 16)


mangadex_client = MangaDexClient()
