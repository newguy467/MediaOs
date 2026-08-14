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
from app.config import settings
from app.models import Blocklist, Episode, MediaItem
from app.services.quality import rank_releases
from app.services.quality.store import get_default_profile, get_profile_by_name
from app.services.release_enrichment import enrich_many
import logging
log = logging.getLogger("mediaos.search")

def _search_builtin_indexers(query: str, category: int | None, db: Session | None) -> list[dict]:
    """Fan-out to configured Torznab indexers when present."""
    if db is None:
        return []
    try:
        from app.clients.torznab import torznab_client
        from app.models import Indexer
    except Exception:
        return []
    rows = (
        db.query(Indexer)
        .filter(Indexer.enabled.is_(True))
        .order_by(Indexer.priority)
        .all()
    )
    results: list[dict] = []
    cat = str(category) if category else None
    for ix in rows:
        try:
            cats = ix.categories or cat
            found = torznab_client.search(
                ix.url,
                query=query,
                api_key=ix.api_key,
                categories=cats,
                limit=40,
                use_flaresolverr=ix.use_flaresolverr,
            )
            for f in found:
                f["indexer"] = ix.name
            results.extend(found)
        except Exception as exc:
            log.warning("Indexer %s failed: %s", ix.name, exc)
    return results




def _search_builtin_public_indexers(query: str, media: str | None) -> list[dict]:
    """Zero-config public trackers (YTS/EZTV/BitSearch) — no Prowlarr, no
    manually-added Torznab indexer required. This is what makes mediaos
    actually able to auto-grab out of the box."""
    try:
        from app.services.builtin_indexers import search_all
        return search_all(query, media=media, limit=30)
    except Exception as exc:
        log.debug("builtin public indexers: %s", exc)
        return []


def _search_cardigann(query: str, db=None) -> list[dict]:
    """Jackett-compatible YAML definitions; inject per-indexer credentials_json."""
    try:
        import json
        from app.services.cardigann import search_all_cardigann
        configs: dict = {}
        if db is not None:
            try:
                from app.models import Indexer
                for ix in db.query(Indexer).filter(Indexer.enabled.is_(True)).all():
                    raw = getattr(ix, "credentials_json", None)
                    if not raw:
                        continue
                    try:
                        creds = json.loads(raw) if isinstance(raw, str) else raw
                    except Exception:
                        continue
                    if not isinstance(creds, dict):
                        continue
                    # map by definition id / name / implementation
                    for key in (
                        getattr(ix, "definition_id", None),
                        getattr(ix, "implementation", None),
                        getattr(ix, "name", None),
                        (ix.name or "").lower().replace(" ", ""),
                    ):
                        if key:
                            configs[str(key)] = {**configs.get(str(key), {}), **creds}
            except Exception as e:
                log.debug("cardigann creds: %s", e)
        return search_all_cardigann(query, configs=configs or None, limit_per=20)
    except Exception as exc:
        log.debug("cardigann: %s", exc)
        return []
        return []


def _blocked_titles(db: Session | None) -> set[str]:
    if db is None:
        return set()
    rows = db.query(Blocklist.release_title).all()
    return {r[0].lower() for r in rows if r[0]}


def _profile_for_item(db: Session | None, media_type: str, profile_name: str | None):
    if db is None:
        from app.services.quality import default_movie_profile, default_tv_profile

        return default_tv_profile() if media_type == "tv" else default_movie_profile()
    if profile_name:
        p = get_profile_by_name(db, profile_name)
        if p:
            return p
    # map music → try "music" profile then movie
    if media_type == "music":
        p = get_default_profile(db, "music")
        if p and p.name:
            return p
        return get_default_profile(db, "movie")
    return get_default_profile(db, media_type)


def _find_best(
    query: str,
    category: int,
    profile,
    db: Session | None = None,
    media: str | None = None,
) -> dict | None:
    releases: list = []
    try:
        releases = list(prowlarr_client.search(query, category=category) or [])
    except Exception as exc:
        log.warning("Prowlarr search failed: %s", exc)
    try:
        releases = enrich_many(releases + _search_builtin_indexers(query, category, db))
    except Exception as exc:
        log.debug("builtin indexers: %s", exc)
    if media in ("movie", "tv"):
        releases = enrich_many(releases + _search_builtin_public_indexers(query, media))
    try:
        releases = releases + _search_cardigann(query, db)
    except Exception as exc:
        log.debug("cardigann fan-out: %s", exc)
    blocked = _blocked_titles(db)

    filtered = []
    for r in releases:
        protocol = (r.get("protocol") or "torrent").lower()
        if protocol == "usenet":
            continue
        title = (r.get("title") or "").lower()
        if title in blocked:
            continue
        if not r.get("download_url"):
            continue
        filtered.append(r)

    ranked = rank_releases(filtered, profile=profile)
    if not ranked:
        return None

    best, result = ranked[0]
    best = dict(best)
    best["_score"] = result.score
    best["_matched_formats"] = result.matched_formats
    best["_parsed"] = {
        "resolution": result.parsed.resolution if result.parsed else None,
        "source": result.parsed.source if result.parsed else None,
        "codec": result.parsed.codec if result.parsed else None,
    }
    return best


def find_best_movie_release(
    media_item: MediaItem, db: Session | None = None
) -> dict | None:
    year = media_item.year or ""
    query = f"{media_item.title} {year}".strip()
    profile = _profile_for_item(db, "movie", media_item.quality_profile)
    return _find_best(query, MOVIE_CATEGORY, profile, db=db, media="movie")



def search_movie_releases(
    media_item: MediaItem, db: Session | None = None, limit: int = 40
) -> list[dict]:
    """Ranked movie releases for interactive search (no auto-grab)."""
    query = media_item.title
    if media_item.year:
        query = f"{query} {media_item.year}"
    profile = _profile_for_item(db, "movie", media_item.quality_profile)
    releases: list = []
    try:
        releases = list(prowlarr_client.search(query, category=MOVIE_CATEGORY) or [])
    except Exception as exc:
        log.warning("Prowlarr search failed: %s", exc)
    try:
        releases = enrich_many(releases + _search_builtin_indexers(query, MOVIE_CATEGORY, db))
    except Exception as exc:
        log.debug("builtin indexers: %s", exc)
    try:
        releases = enrich_many(releases + _search_builtin_public_indexers(query, "movie"))
    except Exception as exc:
        log.debug("public indexers: %s", exc)
    try:
        releases = releases + _search_cardigann(query, db)
    except Exception as exc:
        log.debug("cardigann: %s", exc)
    blocked = _blocked_titles(db)
    filtered = []
    for r in releases:
        protocol = (r.get("protocol") or "torrent").lower()
        if protocol == "usenet":
            continue
        title = (r.get("title") or "").lower()
        if title in blocked:
            continue
        if not r.get("download_url"):
            continue
        filtered.append(r)
    ranked = rank_releases(filtered, profile=profile)
    out = []
    for best, result in ranked[:limit]:
        row = dict(best)
        row["_score"] = result.score
        row["_matched_formats"] = result.matched_formats
        out.append(row)
    return out


def find_best_episode_release(
    series: MediaItem, episode: Episode, db: Session | None = None
) -> dict | None:
    """Single-episode search; optional pack-first when many missing in season."""
    from app.config import settings as cfg

    profile = _profile_for_item(db, "tv", series.quality_profile)
    season = episode.season_number

    if getattr(cfg, "tv_prefer_season_packs", True) and series.episodes:
        missing_in_season = [
            e for e in series.episodes
            if e.season_number == season and e.monitored
            and e.status.value in ("wanted", "missing", "failed")
        ]
        if len(missing_in_season) >= 3:
            pack = find_best_season_pack(series, season, db=db)
            if pack:
                return pack

    abs_n = getattr(episode, "absolute_episode_number", None)
    series_type = (getattr(series, "series_type", None) or "").lower()
    if series_type == "anime" and abs_n:
        query = f"{series.title} {int(abs_n):02d}"
    elif series_type == "anime":
        query = f"{series.title} {episode.episode_number:02d}"
    else:
        query = f"{series.title} S{season:02d}E{episode.episode_number:02d}"
    return _find_best(query, TV_CATEGORY, profile, db=db, media="tv")


def find_best_season_pack(
    series: MediaItem, season: int, db: Session | None = None
) -> dict | None:
    """Search for a full season pack (Sonarr-style)."""
    query = f"{series.title} S{season:02d}"
    # avoid matching S01E if possible — still relies on score/title
    profile = _profile_for_item(db, "tv", series.quality_profile)
    best = _find_best(query, TV_CATEGORY, profile, db=db, media="tv")
    if not best:
        return None
    title = (best.get("title") or "").lower()
    # Prefer titles that look like packs (no E01) or explicitly "season"
    return best


def find_best_music_release(
    media_item: MediaItem, db: Session | None = None
) -> dict | None:
    # Prefer "Artist Album" query
    if media_item.artist_name:
        query = f"{media_item.artist_name} {media_item.title.replace(media_item.artist_name + ' - ', '', 1)}"
    else:
        query = media_item.title
    year = media_item.year or ""
    if year:
        query = f"{query} {year}"
    profile = _profile_for_item(db, "music", media_item.quality_profile)
    return _find_best(query.strip(), AUDIO_CATEGORY, profile, db=db)


def find_best_book_release(
    media_item: MediaItem, db: Session | None = None
) -> dict | None:
    """Search eBook releases via Prowlarr books category."""
    query = media_item.title
    year = media_item.year or ""
    if year:
        query = f"{query} {year}"
    # reuse movie profile scoring as a generic default
    profile = _profile_for_item(db, "movie", media_item.quality_profile)
    return _find_best(query.strip(), BOOK_CATEGORY, profile, db=db)


def find_best_audiobook_release(
    media_item: MediaItem, db: Session | None = None
) -> dict | None:
    """Search audiobook releases via Prowlarr audiobook category."""
    query = media_item.title
    year = media_item.year or ""
    if year:
        query = f"{query} {year}"
    profile = _profile_for_item(db, "movie", media_item.quality_profile)
    return _find_best(query.strip(), AUDIOBOOK_CATEGORY, profile, db=db)




def search_music_releases(media_item: MediaItem, db: Session | None = None, limit: int = 40) -> list[dict]:
    if media_item.artist_name:
        query = f"{media_item.artist_name} {media_item.title.replace(media_item.artist_name + ' - ', '', 1)}"
    else:
        query = media_item.title
    if media_item.year:
        query = f"{query} {media_item.year}"
    profile = _profile_for_item(db, "music", media_item.quality_profile)
    return _search_ranked_list(query.strip(), AUDIO_CATEGORY, profile, db=db, media="music", limit=limit)


def search_audiobook_releases(media_item: MediaItem, db: Session | None = None, limit: int = 40) -> list[dict]:
    query = media_item.title
    if media_item.year:
        query = f"{query} {media_item.year}"
    if getattr(media_item, "artist_name", None):
        query = f"{media_item.artist_name} {query}"
    profile = _profile_for_item(db, "movie", media_item.quality_profile)
    return _search_ranked_list(query.strip(), AUDIOBOOK_CATEGORY, profile, db=db, media="audiobook", limit=limit)


def search_book_releases(media_item: MediaItem, db: Session | None = None, limit: int = 40) -> list[dict]:
    query = media_item.title
    if media_item.year:
        query = f"{query} {media_item.year}"
    profile = _profile_for_item(db, "movie", media_item.quality_profile)
    return _search_ranked_list(query.strip(), BOOK_CATEGORY, profile, db=db, media="book", limit=limit)

COMIC_CATEGORY = 7030
MANGA_CATEGORY = 7010


def _search_ranked_list(
    query: str,
    category: int,
    profile,
    db: Session | None = None,
    media: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """Like _find_best but returns the full ranked list for manual pickers."""
    releases: list = []
    try:
        releases = list(prowlarr_client.search(query, category=category) or [])
    except Exception as exc:
        log.warning("Prowlarr search failed: %s", exc)
    try:
        releases = enrich_many(releases + _search_builtin_indexers(query, category, db))
    except Exception:
        pass
    if media in ("movie", "tv"):
        try:
            releases = enrich_many(releases + _search_builtin_public_indexers(query, media))
        except Exception:
            pass
    try:
        releases = releases + _search_cardigann(query, db)
    except Exception:
        pass
    blocked = _blocked_titles(db)
    filtered = []
    for r in releases:
        protocol = (r.get("protocol") or "torrent").lower()
        if protocol == "usenet":
            continue
        title = (r.get("title") or "").lower()
        if title in blocked or not r.get("download_url"):
            continue
        filtered.append(r)
    ranked = rank_releases(filtered, profile=profile)
    out = []
    for rel, result in ranked[:limit]:
        row = dict(rel)
        row["_score"] = result.score
        row["_matched_formats"] = result.matched_formats
        out.append(row)
    return out


def search_comic_releases(media_item: MediaItem, db: Session | None = None, limit: int = 30) -> list[dict]:
    query = media_item.title
    if media_item.year:
        query = f"{query} {media_item.year}"
    if media_item.artist_name:
        query = f"{query} {media_item.artist_name}"
    profile = _profile_for_item(db, "comic", getattr(media_item, "quality_profile", None))
    return _search_ranked_list(query.strip(), COMIC_CATEGORY, profile, db=db, limit=limit) or \
           _search_ranked_list(query.strip(), BOOK_CATEGORY, profile, db=db, limit=limit)


def search_manga_releases(media_item: MediaItem, db: Session | None = None, limit: int = 30) -> list[dict]:
    query = media_item.title
    if media_item.artist_name:
        query = f"{query} {media_item.artist_name}"
    profile = _profile_for_item(db, "manga", getattr(media_item, "quality_profile", None))
    return _search_ranked_list(query.strip(), MANGA_CATEGORY, profile, db=db, limit=limit) or \
           _search_ranked_list(query.strip(), BOOK_CATEGORY, profile, db=db, limit=limit)


def find_best_comic_release(media_item: MediaItem, db: Session | None = None) -> dict | None:
    query = media_item.title
    if media_item.year: query = f"{query} {media_item.year}"
    if media_item.artist_name: query = f"{query} {media_item.artist_name}"
    profile = _profile_for_item(db, "comic", media_item.quality_profile)
    return _find_best(query.strip(), COMIC_CATEGORY, profile, db=db) or _find_best(query.strip(), BOOK_CATEGORY, profile, db=db)

def find_best_manga_release(media_item: MediaItem, db: Session | None = None) -> dict | None:
    query = media_item.title
    if media_item.artist_name: query = f"{query} {media_item.artist_name}"
    profile = _profile_for_item(db, "manga", media_item.quality_profile)
    return _find_best(query.strip(), MANGA_CATEGORY, profile, db=db) or _find_best(query.strip(), BOOK_CATEGORY, profile, db=db)


def search_episode_releases(
    series: MediaItem, episode: Episode, db: Session | None = None, limit: int = 40
) -> list[dict]:
    """Interactive search: ranked releases for one episode (no grab)."""
    abs_n = getattr(episode, "absolute_episode_number", None)
    series_type = (getattr(series, "series_type", None) or "").lower()
    season = episode.season_number
    if series_type == "anime" and abs_n:
        query = f"{series.title} {int(abs_n):02d}"
    elif series_type == "anime":
        query = f"{series.title} {episode.episode_number:02d}"
    else:
        query = f"{series.title} S{season:02d}E{episode.episode_number:02d}"
    profile = _profile_for_item(db, "tv", series.quality_profile)
    return _search_ranked_list(query, TV_CATEGORY, profile, db=db, media="tv", limit=limit)


def search_season_releases(
    series: MediaItem, season: int, db: Session | None = None, limit: int = 40
) -> list[dict]:
    """Interactive search: ranked season packs / season-ish releases."""
    query = f"{series.title} S{season:02d}"
    profile = _profile_for_item(db, "tv", series.quality_profile)
    rows = _search_ranked_list(query, TV_CATEGORY, profile, db=db, media="tv", limit=limit)
    # Prefer pack-looking titles in order (already scored)
    return rows


def find_best_adult_release(
    media_item, db=None
):
    """Best adult/XXX release for auto-grab."""
    query = media_item.title
    if getattr(media_item, "year", None):
        query = f"{query} {media_item.year}"
    profile = _profile_for_item(db, "adult", getattr(media_item, "quality_profile", None))
    return _find_best(query, XXX_CATEGORY, profile, db=db, media="movie")


def search_adult_releases(media_item, db=None, limit: int = 40) -> list[dict]:
    """Ranked adult releases for interactive search (Torznab cat 6000)."""
    query = media_item.title
    if getattr(media_item, "year", None):
        query = f"{query} {media_item.year}"
    profile = _profile_for_item(db, "adult", getattr(media_item, "quality_profile", None))
    releases: list = []
    try:
        from app.clients.prowlarr import prowlarr_client
        releases = list(prowlarr_client.search(query, category=XXX_CATEGORY) or [])
    except Exception as exc:
        log.warning("Prowlarr adult search failed: %s", exc)
    try:
        releases = enrich_many(releases + _search_builtin_indexers(query, XXX_CATEGORY, db))
    except Exception as exc:
        log.debug("builtin adult indexers: %s", exc)
    try:
        releases = enrich_many(releases + _search_builtin_public_indexers(query, "movie"))
    except Exception as exc:
        log.debug("public adult indexers: %s", exc)
    blocked = _blocked_titles(db)
    filtered = []
    for r in releases:
        title = (r.get("title") or "").lower()
        if any(b in title for b in blocked):
            continue
        if not r.get("download_url"):
            continue
        filtered.append(r)
    # score/rank similar to movies
    ranked = rank_releases(filtered, profile=profile)
    out = []
    for best, result in ranked[:limit]:
        row = dict(best)
        row["_score"] = result.score
        row["_matched_formats"] = result.matched_formats
        out.append(row)
    return out
