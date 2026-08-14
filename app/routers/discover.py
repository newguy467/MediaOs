"""Discover / Overseerr-style endpoints — trending, upcoming, now playing."""
from __future__ import annotations

import hashlib

from app.auth import require_permission
from fastapi import Depends, APIRouter, Query

from app.clients.tmdb import tmdb_client
from app.clients.trakt import trakt_client

router = APIRouter(prefix="/discover", tags=["discover"], dependencies=[Depends(require_permission("discover.view", "library.view"))])


def _stable_int_id(key: str) -> int:
    """Deterministic string -> int id, stable across process restarts.

    Python's built-in hash() is salted per-process for str objects
    (PYTHONHASHSEED) unless hash randomization is explicitly disabled, so it
    must not be used here — using it would make external_id matching for the
    same key silently fail after every app restart, creating duplicate rows
    instead of recognizing an already-added item. Same fix pattern as
    app/clients/openlibrary.py, app/clients/audnexus.py, and
    app/services/arr_migrator.py.
    """
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % (10**12)


@router.get("/movies/trending")
def movies_trending(limit: int = Query(20, ge=1, le=50)):
    try:
        results = trakt_client.trending_movies(limit)
        if results:
            return {"results": results}
    except Exception:
        pass
    try:
        return {"results": tmdb_client.trending_movies(limit) if hasattr(tmdb_client, "trending_movies") else []}
    except Exception:
        return {"results": []}


@router.get("/movies/popular")
def movies_popular(page: int = 1):
    try:
        if hasattr(tmdb_client, "popular_movies"):
            return {"results": tmdb_client.popular_movies(page=page)}
    except Exception:
        pass
    return {"results": []}


@router.get("/movies/now-playing")
def movies_now_playing(page: int = 1):
    try:
        if hasattr(tmdb_client, "now_playing"):
            return {"results": tmdb_client.now_playing(page=page)}
    except Exception:
        pass
    return {"results": []}


@router.get("/movies/upcoming")
def movies_upcoming(page: int = 1):
    try:
        if hasattr(tmdb_client, "upcoming"):
            return {"results": tmdb_client.upcoming(page=page)}
    except Exception:
        pass
    return {"results": []}


@router.get("/tv/trending")
def tv_trending(limit: int = Query(20, ge=1, le=50)):
    try:
        return {"results": trakt_client.trending_shows(limit)}
    except Exception:
        return {"results": []}


@router.get("/coming-up")
def coming_up(days: int = Query(14, ge=1, le=60)):
    """Dashboard widget: next N days of monitored movies/episodes (MediaOs-style)."""
    from datetime import datetime, timedelta, timezone
    from app.database import SessionLocal
    from app.models import Episode, ItemStatus, MediaItem, MediaType

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)
        movies = (
            db.query(MediaItem)
            .filter(
                MediaItem.media_type == MediaType.movie,
                MediaItem.monitored.is_(True),
                MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing]),
            )
            .limit(40)
            .all()
        )
        episodes = (
            db.query(Episode)
            .filter(
                Episode.monitored.is_(True),
                Episode.status.in_([ItemStatus.wanted, ItemStatus.missing]),
                Episode.air_date.isnot(None),
            )
            .order_by(Episode.air_date.asc())
            .limit(80)
            .all()
        )
        out_movies = []
        for m in movies:
            out_movies.append({
                "type": "movie",
                "id": m.id,
                "title": m.title,
                "year": m.year,
                "status": m.status.value if hasattr(m.status, "value") else str(m.status),
                "poster_path": m.poster_path,
            })
        out_eps = []
        for e in episodes:
            ad = e.air_date
            if ad and ad.tzinfo is None:
                ad = ad.replace(tzinfo=timezone.utc)
            if ad and not (now - timedelta(days=2) <= ad <= end):
                continue
            series = e.series if hasattr(e, "series") else None
            out_eps.append({
                "type": "episode",
                "id": e.id,
                "series_id": e.media_item_id,
                "series": series.title if series else None,
                "season": e.season_number,
                "episode": e.episode_number,
                "title": e.title,
                "air_date": ad.isoformat() if ad else None,
                "status": e.status.value if hasattr(e.status, "value") else str(e.status),
            })
        return {"movies": out_movies[:20], "episodes": out_eps[:40], "days": days}
    finally:
        db.close()


@router.get("/movies/discover")
def movies_discover(
    page: int = 1,
    with_genres: str | None = Query(None, description="comma TMDb genre ids"),
    with_networks: str | None = Query(None),
    year: int | None = None,
    sort_by: str = "popularity.desc",
    with_original_language: str | None = None,
    vote_average_gte: float | None = None,
):
    """Overseerr-style filtered discover."""
    params = {"page": page, "sort_by": sort_by}
    if with_genres:
        params["with_genres"] = with_genres
    if year:
        params["primary_release_year"] = year
    try:
        return {"results": tmdb_client.discover_movies_filtered(
            page=page,
            sort_by=sort_by,
            with_genres=with_genres,
            primary_release_year=year,
            with_original_language=with_original_language,
            vote_average_gte=vote_average_gte,
        )}
    except Exception:
        return {"results": []}


@router.get("/tv/discover")
def tv_discover(
    page: int = 1,
    with_genres: str | None = Query(None),
    with_networks: str | None = Query(None),
    sort_by: str = "popularity.desc",
    with_original_language: str | None = None,
):
    params = {"page": page, "sort_by": sort_by}
    if with_genres:
        params["with_genres"] = with_genres
    if with_networks:
        params["with_networks"] = with_networks
    try:
        return {"results": tmdb_client.discover_tv_filtered(
            page=page,
            sort_by=sort_by,
            with_genres=with_genres,
            with_networks=with_networks,
            with_original_language=with_original_language,
        )}
    except Exception:
        return {"results": []}


@router.get("/genres")
def genres(media: str = Query("movie", pattern="^(movie|tv)$")):
    try:
        return {"genres": tmdb_client.genre_list(media)}
    except Exception:
        return {"genres": []}


def _music_row(r: dict, year_fallback: int | None = None) -> dict:
    key = r.get("external_id") or r.get("id") or r.get("album") or r.get("title")
    return {
        "external_id": r.get("external_id") or _stable_int_id(str(key)),
        "external_mbid": r.get("external_mbid") or r.get("id"),
        "title": r.get("album") or r.get("title"),
        "artist": r.get("artist"),
        "year": r.get("year") or year_fallback,
        "poster_path": r.get("poster_path") or r.get("cover"),
        "media_type": "music",
        "tags": r.get("tags") or [],
    }


@router.get("/music/tags")
def music_tags():
    """Curated genre/tag facets for Discover → Music."""
    return {
        "tags": [
            "rock", "pop", "hip-hop", "electronic", "jazz", "metal",
            "indie", "r&b", "soul", "classical", "country", "folk",
            "punk", "ambient", "house", "techno", "blues", "reggae",
            "k-pop", "latin", "soundtrack", "experimental",
        ]
    }


@router.get("/music/popular")
def music_popular(
    limit: int = Query(24, ge=1, le=50),
    tag: str | None = Query(None, description="MusicBrainz tag facet e.g. rock, jazz"),
    year: int | None = Query(None, ge=1950, le=2100),
    q: str | None = Query(None, description="Free-text album/artist query"),
):
    """Popular release groups via MusicBrainz — filter by tag, year, or query."""
    from app.clients.musicbrainz import musicbrainz_client
    try:
        seen = set()
        out = []
        queries: list[str] = []
        if q and q.strip():
            queries.append(f"({q.strip()}) AND type:album")
        if tag and tag.strip():
            safe = tag.strip().replace('"', "")
            part = f'tag:"{safe}" AND type:album' if " " in safe or "&" in safe else f"tag:{safe} AND type:album"
            if year:
                part += f" AND date:{year}"
            queries.append(part)
        elif year:
            queries.append(f"type:album AND date:{year}")
        if not queries:
            queries = [
                "tag:rock AND type:album",
                "tag:pop AND type:album",
                "tag:hip-hop AND type:album",
                "tag:electronic AND type:album",
                "type:album",
            ]
        per = max(8, limit // max(1, len(queries)) + 4)
        for qq in queries:
            rows = musicbrainz_client.search_release_group(qq, limit=per)
            for r in rows or []:
                key = r.get("external_id") or r.get("id") or r.get("album")
                if key in seen:
                    continue
                seen.add(key)
                out.append(_music_row(r, year))
                if len(out) >= limit:
                    break
            if len(out) >= limit:
                break
        return {"results": out[:limit], "tag": tag, "year": year, "q": q}
    except Exception as e:
        return {"results": [], "error": str(e)}


@router.get("/music/new")
def music_new(
    limit: int = Query(24, ge=1, le=50),
    tag: str | None = Query(None),
    years: int = Query(2, ge=1, le=10, description="Look back N years from now"),
):
    """Newer albums — MusicBrainz date window, optional tag."""
    from datetime import datetime
    from app.clients.musicbrainz import musicbrainz_client
    year = datetime.utcnow().year
    try:
        q = f"type:album AND date:[{year - years} TO {year}]"
        if tag and tag.strip():
            safe = tag.strip().replace('"', "")
            q = f'tag:"{safe}" AND {q}' if " " in safe or "&" in safe else f"tag:{safe} AND {q}"
        rows = musicbrainz_client.search_release_group(q, limit=limit)
        out = [_music_row(r, year) for r in (rows or [])]
        return {"results": out, "tag": tag, "from_year": year - years, "to_year": year}
    except Exception as e:
        return {"results": [], "error": str(e)}


@router.get("/music/search")
def music_search(q: str = Query(..., min_length=1), limit: int = Query(24, ge=1, le=50)):
    """Direct album search for Discover music mode."""
    from app.clients.musicbrainz import musicbrainz_client
    try:
        rows = musicbrainz_client.search_release_group(f"({q}) AND type:album", limit=limit)
        return {"results": [_music_row(r) for r in (rows or [])]}
    except Exception as e:
        return {"results": [], "error": str(e)}


@router.get("/adult/search")
def adult_discover_search(q: str = Query("", min_length=1), limit: int = Query(20, ge=1, le=50)):
    """TPDB-backed adult discovery (requires unlock + TPDB key for results)."""
    from app.clients.tpdb import tpdb_client
    if not tpdb_client.configured():
        return {"results": [], "hint": "Set TPDB_API_KEY in Settings → Adult"}
    try:
        return {"results": tpdb_client.search_movies(q, limit=limit)}
    except Exception as e:
        return {"results": [], "error": str(e)}
