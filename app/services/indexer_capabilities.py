"""Per-indexer search-type capability matrix.

Documents what each source can do so interactive search can prefer ID queries
when supported and surface a matrix in the UI / system API.
"""
from __future__ import annotations

from typing import Any


# capability flags:
#   text, imdb, tmdb, tvdb, season, episode, movie, tv, music, book
CAPABILITIES: dict[str, dict[str, Any]] = {
    "Prowlarr": {
        "text": True,
        "imdb": True,
        "tmdb": True,
        "tvdb": True,
        "movie": True,
        "tv": True,
        "season": True,
        "episode": True,
        "music": True,
        "book": True,
        "notes": "Aggregates configured indexers; ID search depends on underlying defs",
    },
    "Torznab": {
        "text": True,
        "imdb": True,
        "tmdb": False,
        "tvdb": True,
        "movie": True,
        "tv": True,
        "season": True,
        "episode": True,
        "notes": "Standard Torznab params; imdbid/tvdbid when indexer supports",
    },
    "Cardigann": {
        "text": True,
        "imdb": False,
        "tmdb": False,
        "tvdb": False,
        "movie": True,
        "tv": True,
        "season": True,
        "episode": True,
        "notes": "YAML defs; mostly text search",
    },
    "YTS": {
        "text": True,
        "imdb": True,
        "tmdb": False,
        "movie": True,
        "tv": False,
        "notes": "Movies only",
    },
    "EZTV": {
        "text": True,
        "imdb": True,
        "tv": True,
        "movie": False,
        "season": True,
        "episode": True,
        "notes": "TV-focused",
    },
    "1337x": {
        "text": True,
        "imdb": False,
        "movie": True,
        "tv": True,
        "music": True,
    },
    "ThePirateBay": {
        "text": True,
        "imdb": False,
        "movie": True,
        "tv": True,
    },
    "BitSearch": {
        "text": True,
        "movie": True,
        "tv": True,
    },
    "Nyaa": {
        "text": True,
        "tv": True,
        "movie": True,
        "notes": "Anime-heavy",
    },
    "OpenSubtitles": {
        "text": True,
        "imdb": True,
        "movie": True,
        "tv": True,
        "notes": "Subtitles only — not a torrent indexer",
    },
}


def matrix() -> list[dict[str, Any]]:
    rows = []
    for name, caps in CAPABILITIES.items():
        rows.append({"name": name, **caps})
    return rows


def supports(name: str, capability: str) -> bool:
    c = CAPABILITIES.get(name) or {}
    return bool(c.get(capability))


def prefer_id_search(name: str) -> bool:
    c = CAPABILITIES.get(name) or {}
    return bool(c.get("imdb") or c.get("tmdb") or c.get("tvdb"))
