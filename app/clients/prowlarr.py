import httpx

from app.config import settings

# Prowlarr / Torznab standard categories
MOVIE_CATEGORY = 2000
TV_CATEGORY = 5000
AUDIO_CATEGORY = 3000  # Music
BOOK_CATEGORY = 7000  # Books / eBooks
AUDIOBOOK_CATEGORY = 3030  # Audiobooks (under Audio)


class ProwlarrClient:
    def __init__(self):
        self.client = httpx.Client(
            base_url=settings.prowlarr_url.rstrip("/"),
            headers={"X-Api-Key": settings.prowlarr_api_key},
            timeout=30.0,
        )

    def search(self, query: str, category: int = MOVIE_CATEGORY) -> list[dict]:
        """
        Hits Prowlarr's aggregate search endpoint, which fans the query out
        to every configured indexer and returns a normalized JSON list.
        """
        resp = self.client.get(
            "/api/v1/search",
            params={
                "query": query,
                "categories": str(category),
                "type": "search",
            },
        )
        resp.raise_for_status()
        releases = resp.json()
        results = []
        for r in releases:
            download_url = r.get("downloadUrl") or r.get("magnetUrl")
            if not download_url:
                continue
            results.append(
                {
                    "title": r.get("title"),
                    "indexer": r.get("indexer"),
                    "size": r.get("size"),
                    "seeders": r.get("seeders"),
                    "download_url": download_url,
                    "protocol": (r.get("protocol") or "torrent").lower(),
                    "info_hash": r.get("infoHash") or r.get("infohash"),
                }
            )
        return results


prowlarr_client = ProwlarrClient()
