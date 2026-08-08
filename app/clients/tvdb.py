import httpx

from app.config import settings

BASE_URL = "https://api4.thetvdb.com/v4"


class TVDbClient:
    """
    TVDb v4 requires a login step (apikey [+ pin for subscriber keys]) that
    returns a bearer token, unlike TMDb's simple query-param key. The token
    is cached in memory and refreshed on a 401, the same pattern used for
    qBittorrent's session cookie.
    """

    def __init__(self):
        self.client = httpx.Client(base_url=BASE_URL, timeout=15.0)
        self._token: str | None = None

    def _login(self):
        payload = {"apikey": settings.tvdb_api_key}
        if settings.tvdb_pin:
            payload["pin"] = settings.tvdb_pin
        resp = self.client.post("/login", json=payload)
        resp.raise_for_status()
        self._token = resp.json()["data"]["token"]
        self.client.headers["Authorization"] = f"Bearer {self._token}"

    def _ensure_login(self):
        if not self._token:
            self._login()

    def _get(self, path: str, params: dict | None = None) -> dict:
        self._ensure_login()
        resp = self.client.get(path, params=params)
        if resp.status_code == 401:
            self._token = None
            self._ensure_login()
            resp = self.client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _series_id(raw: dict) -> int:
        # TVDb search results use "tvdb_id" (sometimes as a string);
        # the /series endpoints use plain "id". Handle both defensively.
        raw_id = raw.get("tvdb_id") or raw.get("id")
        return int(raw_id)

    def search_series(self, query: str) -> list[dict]:
        data = self._get("/search", params={"query": query, "type": "series"})
        results = data.get("data", [])
        return [
            {
                "external_id": self._series_id(r),
                "title": r.get("name") or r.get("translations", {}).get("eng", ""),
                "year": int(r["year"]) if r.get("year") else None,
                "overview": r.get("overview"),
                "poster_path": r.get("image_url") or r.get("image"),
            }
            for r in results
        ]

    def get_series(self, tvdb_id: int) -> dict:
        data = self._get(f"/series/{tvdb_id}/extended")
        r = data["data"]
        first_aired = r.get("firstAired") or ""
        # status: { id, name, recordType, keepUpdated } — name like Continuing / Ended
        raw_status = r.get("status") or {}
        if isinstance(raw_status, dict):
            st_name = (raw_status.get("name") or "").strip().lower()
        else:
            st_name = str(raw_status or "").strip().lower()
        series_status = None
        if "continu" in st_name or st_name == "continuing":
            series_status = "continuing"
        elif "end" in st_name or st_name in ("ended", "ended series"):
            series_status = "ended"
        elif "upcom" in st_name:
            series_status = "upcoming"
        elif "cancel" in st_name:
            series_status = "canceled"
        elif st_name:
            series_status = st_name.replace(" ", "_")[:32]
        return {
            "external_id": r["id"],
            "title": r.get("name"),
            "year": int(first_aired[:4]) if first_aired[:4].isdigit() else None,
            "overview": r.get("overview"),
            "poster_path": r.get("image"),
            "series_status": series_status,
        }

    def get_episodes(self, tvdb_id: int) -> list[dict]:
        """Returns the show's default episode order, flattened across pages."""
        episodes = []
        page = 0
        while True:
            data = self._get(f"/series/{tvdb_id}/episodes/default", params={"page": page})
            batch = data.get("data", {}).get("episodes", [])
            episodes.extend(batch)
            links = data.get("links", {})
            if not links.get("next"):
                break
            page += 1
        return [
            {
                "season_number": e.get("seasonNumber", 0),
                "episode_number": e.get("number", 0),
                "title": e.get("name"),
                "air_date": e.get("aired"),
            }
            for e in episodes
            # season 0 is TVDb's convention for specials; skip by default
            if e.get("seasonNumber", 0) > 0
        ]


tvdb_client = TVDbClient()
