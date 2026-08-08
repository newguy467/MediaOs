"""Audnexus audiobook metadata (Readarr/audiobook enhancement)."""
from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)
BASE = "https://api.audnex.us"


class AudnexusClient:
    def __init__(self) -> None:
        self.client = httpx.Client(base_url=BASE, timeout=20.0, headers={"User-Agent": "mediaos/1.4"})

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Best-effort search via books endpoint patterns."""
        try:
            # Audnexus primarily resolves by ASIN; use Open Library-ish fallback via query on /books is limited
            # Public community often uses: GET /books/{asin}
            # For search we hit a simple scrape-free path: try query as ASIN first
            q = query.strip()
            if len(q) == 10 and q.isalnum():
                book = self.get_book(q)
                return [book] if book else []
            # Fallback: no free text API — return empty and let Open Library drive search
            return []
        except Exception as exc:
            log.debug("Audnexus search: %s", exc)
            return []

    def get_book(self, asin: str) -> dict | None:
        try:
            r = self.client.get(f"/books/{asin}")
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json()
            authors = data.get("authors") or []
            author = ", ".join(
                a.get("name") if isinstance(a, dict) else str(a) for a in authors[:3]
            )
            return {
                "external_id": abs(hash(asin)) % (10**12),
                "asin": asin,
                "title": data.get("title") or data.get("name"),
                "year": None,
                "overview": author or data.get("description"),
                "poster_path": data.get("image") or data.get("cover"),
                "media_type": "audiobook",
                "runtime_mins": data.get("runtimeLengthMin"),
                "narrator": ", ".join(
                    n.get("name") if isinstance(n, dict) else str(n)
                    for n in (data.get("narrators") or [])[:2]
                ),
            }
        except Exception as exc:
            log.warning("Audnexus get_book %s: %s", asin, exc)
            return None


audnexus_client = AudnexusClient()
