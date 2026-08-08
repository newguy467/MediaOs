import httpx


class OpenLibraryClient:
    def __init__(self):
        self.client = httpx.Client(
            base_url="https://openlibrary.org",
            timeout=20.0,
            headers={"User-Agent": "mediaos/0.7"},
        )

    def search_books(self, query: str, limit: int = 20) -> list[dict]:
        resp = self.client.get(
            "/search.json",
            params={"q": query, "limit": limit},
        )
        resp.raise_for_status()
        rows = []
        for r in resp.json().get("docs", []):
            key = r.get("key") or ""
            # /works/OL...W → hash to int
            ext = abs(hash(key)) % (10**12)
            authors = r.get("author_name") or []
            cover = r.get("cover_i")
            # series may be list of strings
            series = r.get("series") or r.get("series_name") or []
            if isinstance(series, list):
                series_name = series[0] if series else None
            else:
                series_name = str(series) if series else None
            rows.append(
                {
                    "external_id": ext,
                    "external_key": key,
                    "title": r.get("title"),
                    "year": (r.get("first_publish_year")),
                    "series_name": series_name,
                    "author_name": (authors[0] if authors else None),
                    "overview": ", ".join(authors[:3]),
                    "poster_path": f"https://covers.openlibrary.org/b/id/{cover}-M.jpg" if cover else None,
                    "media_type": "book",
                }
            )
        return rows



    def search_authors(self, query: str, limit: int = 10) -> list[dict]:
        resp = self.client.get(
            "/search/authors.json",
            params={"q": query, "limit": limit},
        )
        resp.raise_for_status()
        rows = []
        for d in resp.json().get("docs", []):
            key = d.get("key") or ""
            rows.append(
                {
                    "key": key,
                    "name": d.get("name"),
                    "work_count": d.get("work_count"),
                    "top_work": d.get("top_work"),
                }
            )
        return rows

    def author_works(self, author_key: str, limit: int = 50) -> list[dict]:
        key = author_key if author_key.startswith("/authors/") else f"/authors/{author_key}"
        resp = self.client.get(f"{key}/works.json", params={"limit": limit})
        resp.raise_for_status()
        rows = []
        for e in resp.json().get("entries", []):
            wkey = e.get("key") or ""
            ext = abs(hash(wkey)) % (10**12)
            rows.append(
                {
                    "external_id": ext,
                    "external_key": wkey,
                    "title": e.get("title"),
                    "year": None,
                    "overview": None,
                    "poster_path": None,
                    "media_type": "book",
                }
            )
        return rows

    def work_editions(self, work_key: str, limit: int = 20) -> list[dict]:
        key = work_key if work_key.startswith("/works/") else f"/works/{work_key}"
        resp = self.client.get(f"{key}/editions.json", params={"limit": limit})
        resp.raise_for_status()
        rows = []
        for e in resp.json().get("entries", []):
            pubs = e.get("publish_date") or ""
            year = None
            if pubs:
                for tok in str(pubs).split():
                    if tok.isdigit() and len(tok) == 4:
                        year = int(tok)
                        break
            rows.append(
                {
                    "key": e.get("key"),
                    "title": e.get("title"),
                    "year": year,
                    "publishers": e.get("publishers") or [],
                    "isbn_13": (e.get("isbn_13") or [None])[0],
                    "isbn_10": (e.get("isbn_10") or [None])[0],
                    "covers": e.get("covers") or [],
                }
            )
        return rows


openlibrary_client = OpenLibraryClient()

