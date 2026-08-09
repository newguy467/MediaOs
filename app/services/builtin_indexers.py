"""Built-in public indexers — no Prowlarr/Jackett required for common publics.

Uses CF bypass chain (curl_cffi → FlareSolverr → httpx) where needed.
Private trackers: use Cardigann defs (full Jackett sync) or optional Prowlarr import.
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote_plus

from app.clients.cf_bypass import cf_bypass_client

log = logging.getLogger(__name__)


def _get_text(url: str, *, timeout: float = 25, headers: dict | None = None) -> str:
    return cf_bypass_client.get_text(url, timeout=timeout, headers=headers)


def _get_json(url: str, *, timeout: float = 25, headers: dict | None = None) -> Any:
    import json
    return json.loads(_get_text(url, timeout=timeout, headers=headers))


INDEXERS = [
    {"id": "yts", "name": "YTS", "media": ["movie"], "enabled": True},
    {"id": "eztv", "name": "EZTV", "media": ["tv"], "enabled": True},
    {"id": "bitsearch", "name": "BitSearch", "media": ["movie", "tv"], "enabled": True},
    {"id": "1337x", "name": "1337x", "media": ["movie", "tv"], "enabled": True},
    {"id": "tpb", "name": "ThePirateBay", "media": ["movie", "tv"], "enabled": True},
    {"id": "limetorrents", "name": "LimeTorrents", "media": ["movie", "tv", "music"], "enabled": True},
    {"id": "torrentscsv", "name": "Torrents.csv", "media": ["movie", "tv", "music"], "enabled": True},
    {"id": "nyaa", "name": "Nyaa", "media": ["movie", "tv"], "enabled": True},
    {"id": "knaben", "name": "Knaben", "media": ["movie", "tv", "music"], "enabled": True},
    {"id": "bt4g", "name": "BT4G", "media": ["movie", "tv"], "enabled": True},
    {"id": "solidtorrents", "name": "SolidTorrents", "media": ["movie", "tv", "music"], "enabled": True},
    {"id": "torrentio_public", "name": "Torrentio (public meta)", "media": ["movie", "tv"], "enabled": False},
]


def list_indexers() -> list[dict]:
    return list(INDEXERS)


def search(indexer_id: str, query: str, *, limit: int = 30) -> list[dict[str, Any]]:
    fn = {
        "yts": _search_yts,
        "eztv": _search_eztv,
        "bitsearch": _search_bitsearch,
        "1337x": _search_1337x,
        "tpb": _search_tpb,
        "limetorrents": _search_limetorrents,
        "torrentscsv": _search_torrentscsv,
        "nyaa": _search_nyaa,
        "knaben": _search_knaben,
        "bt4g": _search_bt4g,
        "solidtorrents": _search_solidtorrents,
    }.get(indexer_id)
    if not fn:
        return []
    try:
        return fn(query, limit=limit)[:limit]
    except Exception as e:
        log.debug("builtin %s: %s", indexer_id, e)
        return []


def search_all(query: str, *, media: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ix in INDEXERS:
        if not ix.get("enabled"):
            continue
        if media and media not in (ix.get("media") or []):
            continue
        out.extend(search(ix["id"], query, limit=limit))
    # de-dupe by title+indexer
    seen = set()
    uniq = []
    for r in out:
        k = (r.get("title"), r.get("indexer"))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq[: limit * 3]


def _rel(title, download_url, *, indexer, size=None, seeders=None, magnet=None):
    return {
        "title": title,
        "indexer": indexer,
        "size": size,
        "seeders": seeders,
        "download_url": download_url or magnet,
        "magnet_url": magnet,
        "protocol": "torrent",
    }


def _search_yts(query: str, limit: int = 30) -> list[dict]:
    data = _get_json(f"https://yts.mx/api/v2/list_movies.json?query_term={quote_plus(query)}&limit={limit}")
    movies = (data.get("data") or {}).get("movies") or []
    out = []
    for m in movies:
        title = m.get("title_long") or m.get("title")
        for t in m.get("torrents") or []:
            url = t.get("url")
            magnet = None
            if t.get("hash"):
                magnet = f"magnet:?xt=urn:btih:{t['hash']}&dn={quote_plus(title or '')}"
            out.append(_rel(f"{title} [{t.get('quality')}]", url, indexer="YTS", size=t.get("size_bytes"), seeders=t.get("seeds"), magnet=magnet))
    return out[:limit]


def _search_eztv(query: str, limit: int = 30) -> list[dict]:
    data = _get_json(f"https://eztv.re/api/get-torrents?limit={limit}&imdb_id=")
    # EZTV text search is weak; filter client-side
    q = query.lower()
    out = []
    for t in (data.get("torrents") or []):
        title = t.get("title") or ""
        if q not in title.lower():
            continue
        out.append(_rel(title, t.get("torrent_url"), indexer="EZTV", size=int(t.get("size_bytes") or 0) or None, seeders=t.get("seeds"), magnet=t.get("magnet_url")))
    return out[:limit]


def _search_bitsearch(query: str, limit: int = 30) -> list[dict]:
    data = _get_json(f"https://bitsearch.to/api/search?q={quote_plus(query)}&limit={limit}")
    out = []
    for t in (data if isinstance(data, list) else (data.get("torrents") or data.get("data") or [])):
        if not isinstance(t, dict):
            continue
        out.append(_rel(t.get("name") or t.get("title"), t.get("magnet") or t.get("torrent"), indexer="BitSearch", size=t.get("size"), seeders=t.get("seeders") or t.get("seeds")))
    return out[:limit]


def _search_1337x(query: str, limit: int = 30) -> list[dict]:
    html = _get_text(f"https://www.1377x.to/search/{quote_plus(query)}/1/")
    out = []
    for m in re.finditer(r'href="(/torrent/\d+/[^"]+)"[^>]*>([^<]+)', html):
        path, title = m.group(1), m.group(2).strip()
        out.append(_rel(title, "https://www.1377x.to" + path, indexer="1337x"))
        if len(out) >= limit:
            break
    return out


def _search_tpb(query: str, limit: int = 30) -> list[dict]:
    # apibay
    data = _get_json(f"https://apibay.org/q.php?q={quote_plus(query)}&cat=0")
    out = []
    if not isinstance(data, list):
        return []
    for t in data[:limit]:
        name = t.get("name")
        ih = t.get("info_hash")
        magnet = f"magnet:?xt=urn:btih:{ih}&dn={quote_plus(name or '')}" if ih else None
        out.append(_rel(name, magnet, indexer="ThePirateBay", size=int(t.get("size") or 0) or None, seeders=int(t.get("seeders") or 0) or None, magnet=magnet))
    return out


def _search_limetorrents(query: str, limit: int = 30) -> list[dict]:
    html = _get_text(f"https://www.limetorrents.lol/search/all/{quote_plus(query)}/")
    out = []
    for m in re.finditer(r'href="([^"]*torrent[^"]*)"[^>]*>([^<]{5,120})', html, re.I):
        out.append(_rel(m.group(2).strip(), m.group(1), indexer="LimeTorrents"))
        if len(out) >= limit:
            break
    return out


def _search_torrentscsv(query: str, limit: int = 30) -> list[dict]:
    data = _get_json(f"https://torrents-csv.com/service/search?q={quote_plus(query)}&size={limit}")
    rows = data if isinstance(data, list) else (data.get("torrents") or data.get("hits") or [])
    out = []
    for t in rows[:limit]:
        if not isinstance(t, dict):
            continue
        name = t.get("name") or t.get("title")
        ih = t.get("infohash") or t.get("info_hash")
        magnet = f"magnet:?xt=urn:btih:{ih}&dn={quote_plus(name or '')}" if ih else None
        out.append(_rel(name, magnet, indexer="Torrents.csv", size=t.get("size"), seeders=t.get("seeders"), magnet=magnet))
    return out


def _search_nyaa(query: str, limit: int = 30) -> list[dict]:
    html = _get_text(f"https://nyaa.si/?f=0&c=0_0&q={quote_plus(query)}")
    out = []
    for m in re.finditer(r'href="(magnet:\?xt=urn:btih:[^"]+)"', html):
        magnet = m.group(1).replace("&amp;", "&")
        out.append(_rel("nyaa result", magnet, indexer="Nyaa", magnet=magnet))
        if len(out) >= limit:
            break
    # titles nearby are hard; keep magnets
    return out


def _search_knaben(query: str, limit: int = 30) -> list[dict]:
    try:
        data = _get_json(f"https://knaben.org/search?q={quote_plus(query)}")
    except Exception:
        return []
    rows = data if isinstance(data, list) else (data.get("hits") or data.get("results") or [])
    out = []
    for t in rows[:limit]:
        if not isinstance(t, dict):
            continue
        out.append(_rel(t.get("title") or t.get("name"), t.get("magnet") or t.get("link"), indexer="Knaben", size=t.get("size"), seeders=t.get("seeders")))
    return out


def _search_bt4g(query: str, limit: int = 30) -> list[dict]:
    html = _get_text(f"https://bt4gprx.com/search?q={quote_plus(query)}")
    out = []
    for m in re.finditer(r'href="(magnet:\?xt=urn:btih:[^"]+)"', html):
        magnet = m.group(1).replace("&amp;", "&")
        out.append(_rel("bt4g", magnet, indexer="BT4G", magnet=magnet))
        if len(out) >= limit:
            break
    return out


def _search_solidtorrents(query: str, limit: int = 30) -> list[dict]:
    try:
        data = _get_json(f"https://solidtorrents.to/api/v1/search?q={quote_plus(query)}&category=all&sort=seeders")
    except Exception:
        return []
    rows = data.get("results") or data.get("hits") or []
    out = []
    for t in rows[:limit]:
        if not isinstance(t, dict):
            continue
        out.append(_rel(t.get("title") or t.get("name"), t.get("magnet") or t.get("url"), indexer="SolidTorrents", size=t.get("size"), seeders=t.get("seeders") or t.get("swarm", {}).get("seeders") if isinstance(t.get("swarm"), dict) else None))
    return out
