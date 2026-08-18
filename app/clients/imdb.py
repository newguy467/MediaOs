"""IMDb list/chart import helpers for smart lists.

Resolves IMDb list IDs (ls...) and chart shortcuts (top, boxoffice) into
rows with imdb_id + title + year. TMDb find is used when available to
attach tmdb external_id for library adds.
"""
from __future__ import annotations

import logging
import re

import requests

from app.config import settings

log = logging.getLogger(__name__)


class ImdbClient:
    def enabled(self) -> bool:
        return True  # public endpoints; no key required

    def _headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (compatible; mediaos/2.1)",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def chart(self, name: str = "top", limit: int = 100) -> list[dict]:
        """Supported: top | toptv | boxoffice | moviemeter"""
        urls = {
            "top": "https://www.imdb.com/chart/top/",
            "toptv": "https://www.imdb.com/chart/toptv/",
            "boxoffice": "https://www.imdb.com/chart/boxoffice/",
            "moviemeter": "https://www.imdb.com/chart/moviemeter/",
        }
        url = urls.get((name or "top").lower())
        if not url:
            return []
        try:
            r = requests.get(url, headers=self._headers(), timeout=25)
            r.raise_for_status()
            return self._parse_chart_html(r.text, limit=limit)
        except Exception as e:
            log.warning("IMDb chart fetch failed: %s", e)
            return []

    def list_items(self, list_id: str, limit: int = 250) -> list[dict]:
        """Fetch public IMDb list lsXXXXXXXX."""
        lid = list_id.strip()
        if lid.startswith("http"):
            m = re.search(r"(ls\d+)", lid)
            lid = m.group(1) if m else lid
        if not lid.startswith("ls"):
            # treat as chart name
            return self.chart(lid, limit=limit)
        url = f"https://www.imdb.com/list/{lid}/"
        try:
            r = requests.get(url, headers=self._headers(), timeout=30)
            r.raise_for_status()
            return self._parse_list_html(r.text, limit=limit)
        except Exception as e:
            log.warning("IMDb list fetch failed: %s", e)
            return []

    def _parse_chart_html(self, html: str, limit: int = 100) -> list[dict]:
        rows: list[dict] = []
        # title + year + const patterns common across chart pages
        for m in re.finditer(
            r'href="/title/(tt\d+)/[^"]*"[^>]*>\s*([^<]+)</a>.*?(\d{4})',
            html,
            re.DOTALL,
        ):
            imdb_id, title, year = m.group(1), m.group(2).strip(), int(m.group(3))
            rows.append({
                "title": title,
                "year": year,
                "imdb_id": imdb_id,
                "external_id": None,
                "media_type": "movie",
            })
            if len(rows) >= limit:
                break
        if not rows:
            # alternate: JSON-LD
            for m in re.finditer(r'"url":"https://www\.imdb\.com/title/(tt\d+)/".*?"name":"([^"]+)".*?"datePublished":"(\d{4})', html):
                rows.append({
                    "title": m.group(2),
                    "year": int(m.group(3)),
                    "imdb_id": m.group(1),
                    "external_id": None,
                    "media_type": "movie",
                })
                if len(rows) >= limit:
                    break
        return rows

    def _parse_list_html(self, html: str, limit: int = 250) -> list[dict]:
        return self._parse_chart_html(html, limit=limit)

    def enrich_with_tmdb(self, rows: list[dict]) -> list[dict]:
        """Attach tmdb external_id via TMDb find when API key present."""
        key = getattr(settings, "tmdb_api_key", "") or ""
        if not key:
            return rows
        out = []
        for row in rows:
            imdb_id = row.get("imdb_id")
            if not imdb_id:
                out.append(row)
                continue
            try:
                r = requests.get(
                    f"https://api.themoviedb.org/3/find/{imdb_id}",
                    params={"api_key": key, "external_source": "imdb_id"},
                    timeout=15,
                )
                r.raise_for_status()
                data = r.json()
                movie_results = data.get("movie_results") or []
                tv_results = data.get("tv_results") or []
                if movie_results:
                    m = movie_results[0]
                    row = {
                        **row,
                        "external_id": m.get("id"),
                        "tmdb_id": m.get("id"),
                        "title": m.get("title") or row.get("title"),
                        "year": int((m.get("release_date") or "0000")[:4]) or row.get("year"),
                        "overview": m.get("overview"),
                        "poster_path": m.get("poster_path"),
                        "vote_average": m.get("vote_average"),
                        "media_type": "movie",
                    }
                elif tv_results:
                    s = tv_results[0]
                    row = {
                        **row,
                        "external_id": s.get("id"),
                        "tmdb_id": s.get("id"),
                        "title": s.get("name") or row.get("title"),
                        "year": int((s.get("first_air_date") or "0000")[:4]) or row.get("year"),
                        "overview": s.get("overview"),
                        "poster_path": s.get("poster_path"),
                        "vote_average": s.get("vote_average"),
                        "media_type": "tv",
                    }
            except Exception as e:
                log.debug("TMDb find %s failed: %s", imdb_id, e)
            out.append(row)
        return out

    def test(self) -> dict:
        try:
            rows = self.chart("top", limit=3)
            return {"ok": bool(rows), "sample": len(rows)}
        except Exception as e:
            return {"ok": False, "error": str(e)}


imdb_client = ImdbClient()
