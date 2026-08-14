"""Interactive search orchestrator — deeper *arr-style path.

Pipeline:
  queries → rate-limited gather → enrich → parse → dedupe → score/split → envelope

Envelope includes accepted, rejected, rejection breakdown, indexer stats,
search method hints, and timing.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from sqlalchemy.orm import Session

from app.clients.prowlarr import (
    AUDIO_CATEGORY,
    AUDIOBOOK_CATEGORY,
    BOOK_CATEGORY,
    MOVIE_CATEGORY,
    TV_CATEGORY,
    XXX_CATEGORY,
    prowlarr_client,
)
from app.models import Episode, MediaItem
from app.services import rate_limit
from app.services.quality import rank_releases
from app.services.quality.parser import parse_release_title
from app.services.quality.profiles import resolution_rank
from app.services.release_enrichment import enrich_many
from app.services.search import (
    _blocked_titles,
    _profile_for_item,
    _search_builtin_indexers,
    _search_builtin_public_indexers,
    _search_cardigann,
)

log = logging.getLogger("mediaos.interactive")

_PACK_RE = re.compile(
    r"\b(s\d{1,2}|season\s*\d{1,2}).{0,12}(complete|pack|full)\b|"
    r"\bcomplete\s+season\b|\bseason\s+pack\b|\bS\d{1,2}\s*[-–]\s*S\d{1,2}\b",
    re.I,
)
_MULTI_SEASON_RE = re.compile(
    r"\bS(\d{1,2})\s*[-–to]+\s*S?(\d{1,2})\b|\bseasons?\s*\d+\s*[-–to]+\s*\d+\b|\bcomplete\s+series\b",
    re.I,
)


def _is_season_pack(title: str, season: int | None = None) -> bool:
    t = title or ""
    if _PACK_RE.search(t):
        return True
    if season is not None and re.search(rf"\bS{int(season):02d}\b(?!E\d)", t, re.I):
        if re.search(r"\b(complete|pack|FULL)\b", t, re.I):
            return True
    return False


def _is_multi_season_pack(title: str) -> bool:
    return bool(_MULTI_SEASON_RE.search(title or ""))


def _dedupe_key(r: dict) -> str:
    """Prefer infohash / download URL; fall back to normalized title."""
    ih = (r.get("info_hash") or r.get("infoHash") or "").lower().strip()
    if ih and len(ih) >= 16:
        return f"hash:{ih}"
    url = (r.get("download_url") or r.get("magnet") or "")[:280]
    if url:
        # strip tracker query noise for magnet
        if url.startswith("magnet:"):
            m = re.search(r"btih:([a-fA-F0-9]+)", url)
            if m:
                return f"hash:{m.group(1).lower()}"
        return f"url:{url}"
    title = re.sub(r"[\s._]+", " ", (r.get("title") or "").lower()).strip()
    return f"title:{title[:160]}"


def _gather_source(
    name: str,
    fn,
    *,
    search_method: str = "text",
) -> tuple[list[dict], dict[str, Any]]:
    """Run one source with rate-limit + backoff bookkeeping."""
    key = name.lower().replace(" ", "_")
    stat: dict[str, Any] = {
        "name": name,
        "count": 0,
        "durationMs": 0,
        "error": None,
        "searchMethod": search_method,
        "skipped": False,
    }
    if rate_limit.is_in_backoff(key):
        stat["skipped"] = True
        stat["error"] = f"backoff {rate_limit.remaining_backoff(key):.0f}s"
        return [], stat

    rate_limit.wait(key, 0.4)
    t0 = time.perf_counter()
    try:
        rows = list(fn() or [])
        for r in rows:
            r.setdefault("indexer", name)
            r.setdefault("_search_method", search_method)
        stat["count"] = len(rows)
        stat["durationMs"] = int((time.perf_counter() - t0) * 1000)
        rate_limit.record_success(key)
        return rows, stat
    except Exception as e:
        msg = str(e)[:160]
        stat["error"] = msg
        stat["durationMs"] = int((time.perf_counter() - t0) * 1000)
        rate_limit.record_failure(key, msg)
        log.info("interactive source %s failed: %s", name, msg)
        return [], stat


def _gather_releases(
    queries: list[str],
    category: int,
    media: str,
    db: Session | None,
) -> tuple[list[dict], list[dict]]:
    seen: set[str] = set()
    out: list[dict] = []
    stats_map: dict[str, dict[str, Any]] = {}

    def _merge_stat(st: dict) -> None:
        name = st["name"]
        cur = stats_map.get(name) or {
            "name": name,
            "count": 0,
            "durationMs": 0,
            "error": None,
            "searchMethod": st.get("searchMethod"),
            "skipped": False,
        }
        cur["count"] += int(st.get("count") or 0)
        cur["durationMs"] += int(st.get("durationMs") or 0)
        if st.get("error"):
            cur["error"] = st["error"]
        if st.get("skipped"):
            cur["skipped"] = True
        stats_map[name] = cur

    for qi, query in enumerate(queries):
        q = (query or "").strip()
        if not q:
            continue
        # First query preferred as "id-ish" when it looks like imdb
        method = "id" if re.match(r"^tt\d+$", q) or "{tmdb-" in q else "text"

        def prowlarr_fn(qq=q):
            return list(prowlarr_client.search(qq, category=category) or [])

        rows, st = _gather_source("Prowlarr", prowlarr_fn, search_method=method)
        _merge_stat(st)
        for r in rows:
            k = _dedupe_key(r)
            if k not in seen:
                seen.add(k)
                out.append(r)

        def torznab_fn(qq=q):
            return _search_builtin_indexers(qq, category, db)

        rows, st = _gather_source("Torznab", torznab_fn, search_method=method)
        # split counts per real indexer name when possible
        by_ix: dict[str, int] = {}
        for r in rows:
            n = r.get("indexer") or "Torznab"
            by_ix[n] = by_ix.get(n, 0) + 1
            k = _dedupe_key(r)
            if k not in seen:
                seen.add(k)
                out.append(r)
        if by_ix:
            for n, c in by_ix.items():
                _merge_stat({
                    "name": n,
                    "count": c,
                    "durationMs": st.get("durationMs") or 0,
                    "error": st.get("error"),
                    "searchMethod": method,
                    "skipped": st.get("skipped"),
                })
        else:
            _merge_stat(st)

        def public_fn(qq=q):
            return _search_builtin_public_indexers(qq, media)

        rows, st = _gather_source("Public", public_fn, search_method="text")
        by_ix = {}
        for r in rows:
            n = r.get("indexer") or "Public"
            by_ix[n] = by_ix.get(n, 0) + 1
            k = _dedupe_key(r)
            if k not in seen:
                seen.add(k)
                out.append(r)
        for n, c in by_ix.items():
            _merge_stat({
                "name": n,
                "count": c,
                "durationMs": st.get("durationMs") or 0,
                "error": st.get("error"),
                "searchMethod": "text",
                "skipped": st.get("skipped"),
            })

        def card_fn(qq=q):
            return _search_cardigann(qq, db)

        rows, st = _gather_source("Cardigann", card_fn, search_method="text")
        by_ix = {}
        for r in rows:
            n = r.get("indexer") or "Cardigann"
            by_ix[n] = by_ix.get(n, 0) + 1
            k = _dedupe_key(r)
            if k not in seen:
                seen.add(k)
                out.append(r)
        for n, c in by_ix.items():
            _merge_stat({
                "name": n,
                "count": c,
                "durationMs": st.get("durationMs") or 0,
                "error": st.get("error"),
                "searchMethod": "text",
                "skipped": st.get("skipped"),
            })

        # Only run full multi-source on first 2 queries to keep latency sane
        if qi >= 1:
            break

    return out, list(stats_map.values())


def _parse_enrich(releases: list[dict]) -> list[dict]:
    releases = enrich_many(releases)
    for r in releases:
        title = r.get("title") or ""
        try:
            parsed = parse_release_title(title)
            r["_parsed"] = {
                "resolution": parsed.resolution,
                "source": parsed.source,
                "codec": parsed.codec,
                "hdr": list(parsed.hdr or []),
                "audio": list(parsed.audio or []),
                "group": parsed.release_group,
                "season": parsed.season,
                "episode": parsed.episode,
                "season_pack": parsed.season_pack,
                "languages": list(parsed.languages or []),
            }
            r["is_season_pack"] = bool(parsed.season_pack or r.get("season_pack") or _is_season_pack(title))
            r["is_multi_season_pack"] = _is_multi_season_pack(title)
            # soft boost from enrichment already in enrichment_boost
            if r.get("enrichment_boost") and r.get("_score") is None:
                pass
        except Exception:
            r["is_season_pack"] = _is_season_pack(title)
            r["is_multi_season_pack"] = _is_multi_season_pack(title)
    return releases


def _score_and_split(
    releases: list[dict],
    profile,
    db: Session | None,
    *,
    mode: str = "all",
    season: int | None = None,
    desired_qualities: list[str] | None = None,
) -> tuple[list[dict], list[dict], dict[str, int]]:
    blocked = _blocked_titles(db)
    accepted: list[dict] = []
    rejected: list[dict] = []
    breakdown: dict[str, int] = {}

    def _rej(row: dict, reason: str) -> None:
        row = dict(row)
        row["rejected"] = True
        row["rejections"] = [reason]
        row.setdefault("_score", None)
        row.setdefault("_matched_formats", [])
        rejected.append(row)
        breakdown[reason] = breakdown.get(reason, 0) + 1

    for r in releases:
        title = r.get("title") or ""
        tlow = title.lower()

        if not (r.get("download_url") or r.get("magnet")):
            _rej(r, "No download URL")
            continue
        if tlow in blocked:
            _rej(r, "Blocklisted")
            continue
        if mode == "seasonPack" and not (r.get("is_season_pack") or _is_season_pack(title, season)):
            _rej(r, "Not a season pack")
            continue
        if mode == "multiSeasonPack" and not (r.get("is_multi_season_pack") or _is_multi_season_pack(title)):
            _rej(r, "Not a multi-season pack")
            continue
        if mode == "episode" and _is_multi_season_pack(title):
            _rej(r, "Multi-season pack (episode search)")
            continue

        if desired_qualities:
            ranks = [resolution_rank(q) for q in desired_qualities]
            positive = [x for x in ranks if x > 0]
            got = resolution_rank(title)
            if positive and got > 0 and got < min(positive):
                _rej(r, f"Below desired quality ({', '.join(desired_qualities)})")
                continue

        ranked = rank_releases([r], profile=profile)
        if not ranked:
            _rej(r, "Failed quality profile")
            continue
        best, result = ranked[0]
        row = dict(r)
        row["_score"] = int(result.score or 0) + int(r.get("enrichment_boost") or 0)
        row["_matched_formats"] = list(result.matched_formats or [])
        if not result.accepted:
            row["rejected"] = True
            row["rejections"] = [result.rejection_reason or "Rejected by quality profile"]
            rejected.append(row)
            reason = result.rejection_reason or "Rejected by quality profile"
            breakdown[reason] = breakdown.get(reason, 0) + 1
            continue

        row["rejected"] = False
        row["rejections"] = []
        accepted.append(row)

    accepted.sort(key=lambda x: (x.get("_score") or 0, x.get("seeders") or 0), reverse=True)
    rejected.sort(key=lambda x: (x.get("_score") or 0), reverse=True)
    return accepted, rejected, breakdown


def _desired(item: MediaItem) -> list[str] | None:
    raw = getattr(item, "desired_qualities", None)
    if not raw:
        return None
    try:
        import json
        if isinstance(raw, str):
            return list(json.loads(raw))
        return list(raw)
    except Exception:
        return None


def _envelope(
    *,
    media_type: str,
    queries: list[str],
    accepted: list[dict],
    rejected: list[dict],
    indexer_stats: list[dict],
    total_raw: int,
    t0: float,
    breakdown: dict[str, int],
    scope: str | None = None,
    season: int | None = None,
    episode: int | None = None,
    packs_only: bool | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    return {
        "media_type": media_type,
        "scope": scope,
        "season": season,
        "episode": episode,
        "packs_only": packs_only,
        "queries": queries,
        "results": accepted[:limit],
        "rejected": rejected[:limit],
        "indexer_results": indexer_stats,
        "rejection_breakdown": breakdown,
        "total_raw": total_raw,
        "after_dedup": total_raw,  # dedupe happens during gather
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "search_time_ms": int((time.perf_counter() - t0) * 1000),
        "rate_limit": rate_limit.snapshot(),
    }


def interactive_movie_search(item: MediaItem, db: Session | None = None, *, limit: int = 50) -> dict[str, Any]:
    t0 = time.perf_counter()
    profile = _profile_for_item(db, "movie", item.quality_profile)
    title = (item.title or "").strip()
    queries = [title]
    if item.year:
        queries.append(f"{title} {item.year}")
    src = (item.external_source or "").lower()
    if item.external_id and src == "imdb":
        try:
            queries.insert(0, f"tt{int(item.external_id):07d}")
        except Exception:
            pass
    raw, stats = _gather_releases(queries, MOVIE_CATEGORY, "movie", db)
    raw = _parse_enrich(raw)
    accepted, rejected, breakdown = _score_and_split(
        raw, profile, db, mode="all", desired_qualities=_desired(item)
    )
    return _envelope(
        media_type="movie",
        queries=queries,
        accepted=accepted,
        rejected=rejected,
        indexer_stats=stats,
        total_raw=len(raw),
        t0=t0,
        breakdown=breakdown,
        limit=limit,
    )


def interactive_episode_search(
    series: MediaItem, episode: Episode, db: Session | None = None, *, limit: int = 50
) -> dict[str, Any]:
    t0 = time.perf_counter()
    profile = _profile_for_item(db, "tv", series.quality_profile)
    title = (series.title or "").strip()
    s, e = episode.season_number, episode.episode_number
    queries = [f"{title} S{s:02d}E{e:02d}", f"{title} {s}x{e:02d}"]
    abs_n = getattr(episode, "absolute_episode_number", None)
    if (getattr(series, "series_type", None) or "").lower() == "anime" and abs_n:
        queries.insert(0, f"{title} {int(abs_n):02d}")
    raw, stats = _gather_releases(queries, TV_CATEGORY, "tv", db)
    raw = _parse_enrich(raw)
    accepted, rejected, breakdown = _score_and_split(
        raw, profile, db, mode="episode", season=s
    )
    return _envelope(
        media_type="tv",
        scope="episode",
        season=s,
        episode=e,
        queries=queries,
        accepted=accepted,
        rejected=rejected,
        indexer_stats=stats,
        total_raw=len(raw),
        t0=t0,
        breakdown=breakdown,
        limit=limit,
    )


def interactive_season_search(
    series: MediaItem,
    season: int,
    db: Session | None = None,
    *,
    limit: int = 50,
    packs_only: bool = True,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    profile = _profile_for_item(db, "tv", series.quality_profile)
    title = (series.title or "").strip()
    queries = [
        f"{title} S{season:02d} COMPLETE",
        f"{title} Season {season} Pack",
        f"{title} Season {season}",
        f"{title} S{season:02d}",
    ]
    raw, stats = _gather_releases(queries, TV_CATEGORY, "tv", db)
    raw = _parse_enrich(raw)
    mode = "seasonPack" if packs_only else "all"
    accepted, rejected, breakdown = _score_and_split(raw, profile, db, mode=mode, season=season)
    return _envelope(
        media_type="tv",
        scope="season",
        season=season,
        packs_only=packs_only,
        queries=queries,
        accepted=accepted,
        rejected=rejected,
        indexer_stats=stats,
        total_raw=len(raw),
        t0=t0,
        breakdown=breakdown,
        limit=limit,
    )


def interactive_series_pack_search(
    series: MediaItem, db: Session | None = None, *, limit: int = 40
) -> dict[str, Any]:
    t0 = time.perf_counter()
    profile = _profile_for_item(db, "tv", series.quality_profile)
    title = (series.title or "").strip()
    queries = [f"{title} Complete Series", f"{title} S01-S", f"{title} Seasons"]
    if series.year:
        queries.append(f"{title} {series.year} Complete")
    raw, stats = _gather_releases(queries, TV_CATEGORY, "tv", db)
    raw = _parse_enrich(raw)
    accepted, rejected, breakdown = _score_and_split(raw, profile, db, mode="multiSeasonPack")
    return _envelope(
        media_type="tv",
        scope="seriesPack",
        queries=queries,
        accepted=accepted,
        rejected=rejected,
        indexer_stats=stats,
        total_raw=len(raw),
        t0=t0,
        breakdown=breakdown,
        limit=limit,
    )


def interactive_adult_search(item: MediaItem, db: Session | None = None, *, limit: int = 50) -> dict[str, Any]:
    """Whisparr-style interactive search — same envelope as movies, XXX category."""
    t0 = time.perf_counter()
    profile = _profile_for_item(db, "adult", item.quality_profile)
    title = (item.title or "").strip()
    queries = [title]
    if item.year:
        queries.append(f"{title} {item.year}")
    raw, stats = _gather_releases(queries, XXX_CATEGORY, "movie", db)
    raw = _parse_enrich(raw)
    accepted, rejected, breakdown = _score_and_split(
        raw, profile, db, mode="all", desired_qualities=_desired(item)
    )
    return _envelope(
        media_type="adult",
        queries=queries,
        accepted=accepted,
        rejected=rejected,
        indexer_stats=stats,
        total_raw=len(raw),
        t0=t0,
        breakdown=breakdown,
        limit=limit,
    )


# Categories not always re-exported from prowlarr client
_COMIC_CATEGORY = 7030
_MANGA_CATEGORY = 7010


def _map_rows(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        out.append({
            "title": r.get("title") or "",
            "indexer": r.get("indexer"),
            "size": r.get("size"),
            "seeders": r.get("seeders"),
            "download_url": r.get("download_url") or r.get("magnet") or "",
            "score": r.get("_score") or r.get("score"),
            "matched_formats": list(r.get("_matched_formats") or []),
            "protocol": r.get("protocol"),
            "age_hours": r.get("age_hours") or r.get("age"),
            "rejected": bool(r.get("rejected")),
            "rejections": list(r.get("rejections") or []),
            "info_hash": r.get("info_hash"),
            "parsed_resolution": (r.get("_parsed") or {}).get("resolution"),
            "parsed_codec": (r.get("_parsed") or {}).get("codec"),
            "parsed_source": (r.get("_parsed") or {}).get("source"),
            "parsed_group": (r.get("_parsed") or {}).get("group"),
        })
    return out


def interactive_generic_search(
    item: MediaItem,
    *,
    category: int,
    media_type: str,
    profile_media: str,
    queries: list[str] | None = None,
    db: Session | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Full interactive envelope for any media type / Torznab category."""
    t0 = time.perf_counter()
    profile = _profile_for_item(db, profile_media, getattr(item, "quality_profile", None))
    title = (item.title or "").strip()
    qs = list(queries or [])
    if not qs:
        qs = [title]
        if getattr(item, "year", None):
            qs.append(f"{title} {item.year}")
        if getattr(item, "artist_name", None):
            qs.insert(0, f"{item.artist_name} {title}")
    raw, stats = _gather_releases(qs, category, media_type if media_type in ("movie", "tv", "music") else "movie", db)
    raw = _parse_enrich(raw)
    accepted, rejected, breakdown = _score_and_split(
        raw, profile, db, mode="all", desired_qualities=_desired(item)
    )
    env = _envelope(
        media_type=media_type,
        queries=qs,
        accepted=accepted,
        rejected=rejected,
        indexer_stats=stats,
        total_raw=len(raw),
        t0=t0,
        breakdown=breakdown,
        limit=limit,
    )
    # Normalize keys for UI
    env["results"] = _map_rows(env.get("results") or env.get("accepted") or accepted[:limit])
    env["rejected"] = _map_rows(env.get("rejected") or rejected)
    env["accepted_count"] = len(env["results"])
    env["rejected_count"] = len(env["rejected"])
    return env


def interactive_music_search(item: MediaItem, db: Session | None = None, *, limit: int = 50) -> dict[str, Any]:
    qs = []
    title = (item.title or "").strip()
    if item.artist_name:
        qs.append(f"{item.artist_name} {title.replace(item.artist_name + ' - ', '', 1)}")
    qs.append(title)
    if item.year:
        qs.append(f"{qs[0]} {item.year}")
    return interactive_generic_search(
        item, category=AUDIO_CATEGORY, media_type="music", profile_media="music",
        queries=qs, db=db, limit=limit,
    )


def interactive_book_search(item: MediaItem, db: Session | None = None, *, limit: int = 50) -> dict[str, Any]:
    return interactive_generic_search(
        item, category=BOOK_CATEGORY, media_type="book", profile_media="book",
        db=db, limit=limit,
    )


def interactive_audiobook_search(item: MediaItem, db: Session | None = None, *, limit: int = 50) -> dict[str, Any]:
    return interactive_generic_search(
        item, category=AUDIOBOOK_CATEGORY, media_type="audiobook", profile_media="audiobook",
        db=db, limit=limit,
    )


def interactive_comic_search(item: MediaItem, db: Session | None = None, *, limit: int = 50) -> dict[str, Any]:
    return interactive_generic_search(
        item, category=_COMIC_CATEGORY, media_type="comic", profile_media="comic",
        db=db, limit=limit,
    )


def interactive_manga_search(item: MediaItem, db: Session | None = None, *, limit: int = 50) -> dict[str, Any]:
    return interactive_generic_search(
        item, category=_MANGA_CATEGORY, media_type="manga", profile_media="manga",
        db=db, limit=limit,
    )



def interactive_game_search(title: str, db: Session | None = None, *, limit: int = 50) -> dict[str, Any]:
    """Shared indexer search for games (integration B)."""
    import time as _time
    t0 = _time.perf_counter()
    q = (title or "").strip()
    if not q:
        return _envelope(
            media_type="game",
            queries=[],
            accepted=[],
            rejected=[],
            indexer_stats=[],
            total_raw=0,
            t0=t0,
            breakdown={},
            limit=limit,
        )
    queries = [q]
    # Reuse movie category gather — indexers still return scene releases by title
    try:
        cat = MOVIE_CATEGORY
    except NameError:
        cat = 2000
    raw, stats = _gather_releases(queries, cat, "game", db)
    raw = _parse_enrich(raw)
    # No quality profile — rank by seeders then existing score
    def _key(r: dict):
        return (int(r.get("seeders") or 0), int(r.get("_score") or r.get("score") or 0))
    accepted = sorted(raw, key=_key, reverse=True)
    for r in accepted:
        r.setdefault("score", r.get("_score") or 0)
        r.setdefault("matched_formats", r.get("_matched_formats") or [])
    return _envelope(
        media_type="game",
        queries=queries,
        accepted=accepted,
        rejected=[],
        indexer_stats=stats if isinstance(stats, list) else list((stats or {}).values()) if isinstance(stats, dict) else [],
        total_raw=len(raw),
        t0=t0,
        breakdown={},
        limit=limit,
    )
