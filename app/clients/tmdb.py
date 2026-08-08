import httpx

from app.config import settings

BASE_URL = "https://api.themoviedb.org/3"


class TMDbClient:
    def __init__(self):
        self.client = httpx.Client(
            base_url=BASE_URL,
            params={"api_key": settings.tmdb_api_key},
            timeout=15.0,
        )

    @staticmethod
    def _year(release_date: str | None) -> int | None:
        if not release_date or len(release_date) < 4:
            return None
        try:
            return int(release_date[:4])
        except ValueError:
            return None

    def search_movie(self, query: str) -> list[dict]:
        resp = self.client.get("/search/movie", params={"query": query})
        resp.raise_for_status()
        return [self._movie_row(r) for r in resp.json().get("results", [])]

    def get_movie(self, tmdb_id: int) -> dict:
        resp = self.client.get(f"/movie/{tmdb_id}")
        resp.raise_for_status()
        return self._movie_row(resp.json())

    def search_tv(self, query: str) -> list[dict]:
        resp = self.client.get("/search/tv", params={"query": query})
        resp.raise_for_status()
        return [self._tv_row(r) for r in resp.json().get("results", [])]

    def discover_movies(self, kind: str = "popular", page: int = 1) -> list[dict]:
        """kind: popular | top_rated | now_playing | upcoming | trending"""
        if kind == "trending":
            resp = self.client.get("/trending/movie/week", params={"page": page})
        else:
            path = {
                "popular": "/movie/popular",
                "top_rated": "/movie/top_rated",
                "now_playing": "/movie/now_playing",
                "upcoming": "/movie/upcoming",
            }.get(kind, "/movie/popular")
            resp = self.client.get(path, params={"page": page})
        resp.raise_for_status()
        return [self._movie_row(r) for r in resp.json().get("results", [])]

    def discover_tv(self, kind: str = "popular", page: int = 1) -> list[dict]:
        if kind == "trending":
            resp = self.client.get("/trending/tv/week", params={"page": page})
        else:
            path = {
                "popular": "/tv/popular",
                "top_rated": "/tv/top_rated",
                "on_the_air": "/tv/on_the_air",
            }.get(kind, "/tv/popular")
            resp = self.client.get(path, params={"page": page})
        resp.raise_for_status()
        return [self._tv_row(r) for r in resp.json().get("results", [])]

    def _movie_row(self, r: dict) -> dict:
        return {
            "external_id": r["id"],
            "media_type": "movie",
            "title": r.get("title") or r.get("name"),
            "year": self._year(r.get("release_date")),
            "overview": r.get("overview"),
            "poster_path": r.get("poster_path"),
            "vote_average": r.get("vote_average"),
        }

    def _tv_row(self, r: dict) -> dict:
        return {
            "external_id": r["id"],
            "media_type": "tv",
            "title": r.get("name") or r.get("title"),
            "year": self._year(r.get("first_air_date")),
            "overview": r.get("overview"),
            "poster_path": r.get("poster_path"),
            "vote_average": r.get("vote_average"),
        }

    def get_list(self, list_id: int, page: int = 1) -> list[dict]:
        """Fetch items from a TMDb list (v3). Mix of movie/TV."""
        resp = self.client.get(f"/list/{list_id}", params={"page": page})
        resp.raise_for_status()
        items = []
        for r in resp.json().get("items", []):
            mt = r.get("media_type") or ("movie" if r.get("title") else "tv")
            if mt == "movie":
                items.append(self._movie_row(r))
            else:
                items.append(self._tv_row(r))
        return items

    def discover_movies_filtered(
        self,
        *,
        primary_release_year: int | None = None,
        year_gte: int | None = None,
        year_lte: int | None = None,
        vote_average_gte: float | None = None,
        with_genres: str | None = None,
        sort_by: str = "popularity.desc",
        page: int = 1,
        **extra,
    ) -> list[dict]:
        params: dict = {"page": page, "sort_by": sort_by}
        if primary_release_year:
            params["primary_release_year"] = primary_release_year
        if year_gte:
            params["primary_release_date.gte"] = f"{year_gte}-01-01"
        if year_lte:
            params["primary_release_date.lte"] = f"{year_lte}-12-31"
        if vote_average_gte is not None:
            params["vote_average.gte"] = vote_average_gte
        if with_genres:
            params["with_genres"] = with_genres
        params.update({k: v for k, v in extra.items() if v is not None})
        resp = self.client.get("/discover/movie", params=params)
        resp.raise_for_status()
        return [self._movie_row(r) for r in resp.json().get("results", [])]

    def discover_tv_filtered(
        self,
        *,
        with_genres: str | None = None,
        with_networks: str | None = None,
        sort_by: str = "popularity.desc",
        page: int = 1,
        **extra,
    ) -> list[dict]:
        params: dict = {"page": page, "sort_by": sort_by}
        if with_genres:
            params["with_genres"] = with_genres
        if with_networks:
            params["with_networks"] = with_networks
        params.update({k: v for k, v in extra.items() if v is not None})
        resp = self.client.get("/discover/tv", params=params)
        resp.raise_for_status()
        return [self._tv_row(r) for r in resp.json().get("results", [])]

    def genre_list(self, media: str = "movie") -> list[dict]:
        path = "/genre/tv/list" if media == "tv" else "/genre/movie/list"
        resp = self.client.get(path)
        resp.raise_for_status()
        return resp.json().get("genres") or []



    def trending_movies(self, limit: int = 20) -> list[dict]:
        resp = self.client.get("/trending/movie/week")
        resp.raise_for_status()
        rows = [self._movie_row(r) for r in resp.json().get("results", [])]
        return rows[:limit]

    def popular_movies(self, page: int = 1) -> list[dict]:
        return self.discover_movies("popular", page=page)

    def now_playing(self, page: int = 1) -> list[dict]:
        resp = self.client.get("/movie/now_playing", params={"page": page})
        resp.raise_for_status()
        return [self._movie_row(r) for r in resp.json().get("results", [])]

    def upcoming(self, page: int = 1) -> list[dict]:
        resp = self.client.get("/movie/upcoming", params={"page": page})
        resp.raise_for_status()
        return [self._movie_row(r) for r in resp.json().get("results", [])]

    def search_collections(self, query: str) -> list[dict]:
        resp = self.client.get("/search/collection", params={"query": query})
        resp.raise_for_status()
        return [
            {
                "tmdb_id": r["id"],
                "name": r.get("name"),
                "overview": r.get("overview"),
                "poster_path": r.get("poster_path"),
            }
            for r in resp.json().get("results", [])
        ]

    def get_collection(self, collection_id: int) -> dict:
        resp = self.client.get(f"/collection/{collection_id}")
        resp.raise_for_status()
        data = resp.json()
        return {
            "tmdb_id": data["id"],
            "name": data.get("name"),
            "overview": data.get("overview"),
            "poster_path": data.get("poster_path"),
            "parts": [self._movie_row(r) for r in data.get("parts", [])],
        }

    def trending_tv(self, limit: int = 20) -> list[dict]:
        resp = self.client.get("/trending/tv/week")
        resp.raise_for_status()
        rows = [self._tv_row(r) for r in resp.json().get("results", [])]
        return rows[:limit]


tmdb_client = TMDbClient()

