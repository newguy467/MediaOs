"""Built-in public indexers (MediaOs-style) — no Prowlarr required for basics.

Thin HTML/JSON adapters for common public sources. Prefer Prowlarr for private
trackers; these cover YTS / EZTV / BitSearch class public discovery.
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote_plus

import httpx

from app.clients.cf_bypass import cf_bypass_client

log = logging.getLogger(__name__)


def _get_text(url: str, *, timeout: float = 25, headers: dict | None = None) -> str:
    """GET via CF bypass chain (curl_cffi → FlareSolverr → httpx)."""
    return cf_bypass_client.get_text(url, timeout=timeout, headers=headers)


def _get_json(url: str, *, timeout: float = 25, headers: dict | None = None) -> Any:
    text = _get_text(url, timeout=timeout, headers=headers)
    import json
    return json.loads(text)

INDEXERS = [
    {"id": "yts", "name": "YTS", "media": ["movie"], "enabled": True},
    {"id": "eztv", "name": "EZTV", "media": ["tv"], "enabled": True},
    {"id": "bitsearch", "name": "BitSearch", "media": ["movie", "tv"], "enabled": True},
    {"id": "1337x", "name": "1337x", "media": ["movie", "tv"], "enabled": True},
    {"id": "tpb", "name": "ThePirateBay", "media": ["movie", "tv"], "enabled": True},
    {"id": "limetorrents", "name": "LimeTorrents", "media": ["movie", "tv", "music"], "enabled": True},
    {"id": "torrentscsv", "name": "Torrents.csv", "media": ["movie", "tv", "music"], "enabled": True},
    {"id": "nyaa", "name": "Nyaa", "media": ["movie", "tv"], "enabled": True},
]


def list_indexers() -> list[dict]:
    return list(INDEXERS)


def search(indexer_id: str, query: str, *, limit: int = 30) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    fn = {
        "yts": _search_yts,
        "eztv": _search_eztv,
        "bitsearch": _search_bitsearch,
        "1337x": _search_1337x,
        "tpb": _search_tpb,
        "limetorrents": _search_limetorrents,
        "torrentscsv": _search_torrentscsv,
        "nyaa": _search_nyaa,
    }.get(indexer_id)
    if not fn:
        return []
    try:
        return fn(q, limit=limit)
    except Exception as e:
        log.warning("builtin indexer %s failed: %s", indexer_id, e)
        return []


def search_all(query: str, *, media: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ix in INDEXERS:
        if media and media not in ix["media"]:
            continue
        rows = search(ix["id"], query, limit=limit)
        for r in rows:
            r.setdefault("indexer", ix["name"])
        out.extend(rows)
    # crude dedupe by title
    seen = set()
    deduped = []
    for r in out:
        key = (r.get("title") or "").lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped[: limit * 2]


def _search_yts(query: str, limit: int = 30) -> list[dict]:
    url = f"https://yts.mx/api/v2/list_movies.json?query_term={quote_plus(query)}&limit={min(limit, 50)}"
    data = _get_json(url, timeout=20)
    movies = ((data.get("data") or {}).get("movies")) or []
    out = []
    for m in movies:
        title = m.get("title_long") or m.get("title") or "Unknown"
        for t in m.get("torrents") or []:
            magnet = None
            th = t.get("hash")
            if th:
                magnet = (
                    f"magnet:?xt=urn:btih:{th}&dn={quote_plus(title)}"
                    "&tr=udp://tracker.opentrackr.org:1337/announce"
                )
            out.append({
                "title": f"{title} [{t.get('quality')}] [{t.get('type')}]",
                "download_url": magnet or t.get("url"),
                "magnet": magnet,
                "size": t.get("size"),
                "seeders": t.get("seeds"),
                "peers": t.get("peers"),
                "protocol": "torrent",
                "indexer": "YTS",
                "info_hash": th,
            })
    return out[:limit]


def _search_eztv(query: str, limit: int = 30) -> list[dict]:
    # EZTV API
    url = f"https://eztv.re/api/get-torrents?limit={min(limit, 50)}&imdb_id="
    # fallback: search page is HTML — try API by name via mirror list endpoint is limited
    # Use get-torrents without imdb and filter client-side is too heavy; use search URL JSON if available
    search_url = f"https://eztvx.to/api/get-torrents?limit={min(limit,100)}"
    try:
        torrents = (_get_json(search_url, timeout=20) or {}).get("torrents") or []
    except Exception:
        torrents = []
    qlow = query.lower()
    out = []
    for t in torrents:
        title = t.get("title") or ""
        if qlow not in title.lower() and not all(w in title.lower() for w in qlow.split()[:2]):
            continue
        out.append({
            "title": title,
            "download_url": t.get("magnet_url") or t.get("torrent_url"),
            "magnet": t.get("magnet_url"),
            "size": t.get("size_bytes"),
            "seeders": t.get("seeds"),
            "peers": t.get("peers"),
            "protocol": "torrent",
            "indexer": "EZTV",
            "info_hash": t.get("hash"),
        })
        if len(out) >= limit:
            break
    return out


def _search_bitsearch(query: str, limit: int = 30) -> list[dict]:
    url = f"https://bitsearch.to/search?q={quote_plus(query)}"
    html = _get_text(url, timeout=25, headers={"User-Agent": "mediaos/2.1"})
    out = []
    # magnet links
    for m in re.finditer(r'href="(magnet:\?xt=urn:btih:[^"]+)"', html):
        magnet = m.group(1).replace("&amp;", "&")
        # title near magnet is hard; use dn=
        dn = re.search(r"dn=([^&]+)", magnet)
        title = dn.group(1).replace("+", " ") if dn else "BitSearch result"
        try:
            from urllib.parse import unquote_plus
            title = unquote_plus(title)
        except Exception:
            pass
        out.append({
            "title": title[:200],
            "download_url": magnet,
            "magnet": magnet,
            "protocol": "torrent",
            "indexer": "BitSearch",
            "seeders": None,
        })
        if len(out) >= limit:
            break
    return out



def _search_1337x(query: str, limit: int = 30) -> list[dict]:
    mirrors = [f"https://www.1377x.to/search/{quote_plus(query)}/1/", f"https://1337x.to/search/{quote_plus(query)}/1/"]
    html = ""
    for url in mirrors:
        try:
            text = _get_text(url, timeout=20, headers={"User-Agent": "mediaos/2.5"})
            if text and "torrent" in text.lower():
                html = text; break
        except Exception:
            continue
    if not html: return []
    out = []
    for m in re.finditer(r'href="(/torrent/\d+/[^"]+)"', html):
        path = m.group(1)
        title = path.split("/")[-2].replace("-", " ")[:200]
        magnet = None
        try:
            dtext = _get_text("https://www.1377x.to" + path, timeout=15, headers={"User-Agent": "mediaos/2.5"})
            mm = re.search(r'href="(magnet:\?xt=urn:btih:[^"]+)"', dtext)
            if mm: magnet = mm.group(1).replace("&amp;", "&")
        except Exception: pass
        if not magnet: continue
        out.append({"title": title, "download_url": magnet, "magnet": magnet, "protocol": "torrent", "indexer": "1337x"})
        if len(out) >= limit: break
    return out

def _search_tpb(query: str, limit: int = 30) -> list[dict]:
    rows = []
    try:
        data = _get_json(f"https://apibay.org/q.php?q={quote_plus(query)}&cat=0", timeout=20, headers={"User-Agent": "mediaos/2.5"})
        if isinstance(data, list) and data and data[0].get("id") != "0":
            rows = data
    except Exception:
        pass
    out = []
    for t in rows[:limit]:
        ih = t.get("info_hash")
        name = t.get("name") or "TPB result"
        if not ih: continue
        magnet = f"magnet:?xt=urn:btih:{ih}&dn={quote_plus(name)}&tr=udp://tracker.opentrackr.org:1337/announce"
        out.append({"title": name[:200], "download_url": magnet, "magnet": magnet, "size": t.get("size"),
            "seeders": int(t["seeders"]) if str(t.get("seeders", "")).isdigit() else None,
            "protocol": "torrent", "indexer": "ThePirateBay", "info_hash": ih})
    return out
