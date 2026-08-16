from datetime import datetime, timezone

from app.auth import require_permission
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.clients.tvdb import tvdb_client
from app.database import get_db
from app.services.wanted import episode_search_query
from app.models import Episode, ItemStatus, MediaItem, MediaType
from app.schemas import (
    EpisodeOut,
    EpisodeUpdate,
    ReleaseOut,
    SearchResult,
    SeriesCreate,
    SeriesOut,
    SeriesUpdate,
)
from app.services.grab import grab_episode_release
from app.services.monitor import apply_monitor_mode
from app.services.search import find_best_episode_release, find_best_season_pack, search_episode_releases, search_season_releases

router = APIRouter(prefix="/tv", tags=["tv"],
    dependencies=[Depends(require_permission("library.view", "library.manage"))],
)


def _to_series_out(item: MediaItem) -> SeriesOut:
    eps = item.episodes or []
    downloaded = sum(1 for e in eps if e.status == ItemStatus.downloaded)
    missing = sum(
        1
        for e in eps
        if e.monitored and e.status in (ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed)
    )
    return SeriesOut(
        id=item.id,
        external_id=item.external_id,
        title=item.title,
        year=item.year,
        poster_path=item.poster_path,
        monitored=item.monitored,
        quality_profile=item.quality_profile,
        series_status=getattr(item, "series_status", None),
        series_name=getattr(item, "series_name", None),
        status=item.status.value if hasattr(item.status, "value") else str(item.status) if item.status else None,
        file_path=item.file_path,
        added_at=item.added_at,
        episode_count=len(eps),
        downloaded_count=downloaded,
        missing_count=missing,
        monitor=item.monitor_mode,
    )


@router.get("/search", response_model=list[SearchResult])
def search_tvdb(query: str):
    return tvdb_client.search_series(query)


@router.post("", response_model=SeriesOut)
def add_series(payload: SeriesCreate, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage", "download"))):
    existing = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.tv,
            MediaItem.external_id == payload.external_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(409, "Series already in library")

    details = tvdb_client.get_series(payload.external_id)
    import json as _json
    series = MediaItem(
        media_type=MediaType.tv,
        external_id=details["external_id"],
        external_source="tvdb",
        title=details["title"],
        year=details["year"],
        overview=details["overview"],
        poster_path=details["poster_path"],
        monitored=payload.monitored,
        series_type=getattr(payload, "series_type", None) or "standard",
        series_status=details.get("series_status"),
        status=ItemStatus.wanted,
        quality_profile=payload.quality_profile,
        monitor_mode=payload.monitor or "all",
        tvdb_id=int(details["external_id"]) if details.get("external_id") else None,
        imdb_id=details.get("imdb_id"),
        external_ids=_json.dumps({
            "tvdb": details.get("external_id"),
            "imdb": details.get("imdb_id"),
            **(details.get("external_ids") or {}),
        }),
    )
    db.add(series)
    db.flush()

    episodes: list[Episode] = []
    for ep in tvdb_client.get_episodes(payload.external_id):
        e = Episode(
            media_item_id=series.id,
            season_number=ep["season_number"],
            episode_number=ep["episode_number"],
            title=ep["title"],
            air_date=ep["air_date"],
            monitored=True,
            status=ItemStatus.wanted,
        )
        episodes.append(e)
        db.add(e)

    apply_monitor_mode(episodes, payload.monitor or "all")
    db.commit()
    db.refresh(series)

    if payload.search_missing and payload.monitored:
        # Best-effort: search each monitored missing episode (capped)
        _search_missing_for_series(db, series, limit=20)

    return _to_series_out(series)



@router.post("/from-tmdb")
def add_tv_from_tmdb(body: dict, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage", "download"))):
    """Add series using TMDb ID (provider IDs persisted like TVDb path)."""
    from app.clients.tmdb import tmdb_client
    import json as _json
    tmdb_id = body.get("tmdb_id") or body.get("external_id")
    if not tmdb_id:
        raise HTTPException(400, "tmdb_id required")
    details = tmdb_client.get_tv(int(tmdb_id))
    existing = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.tv, MediaItem.external_id == int(details["external_id"]), MediaItem.external_source == "tmdb")
        .first()
    )
    if existing:
        raise HTTPException(409, "Series already in library")
    series = MediaItem(
        media_type=MediaType.tv,
        external_id=int(details["external_id"]),
        external_source="tmdb",
        title=details["title"],
        year=details.get("year"),
        overview=details.get("overview"),
        poster_path=details.get("poster_path"),
        monitored=bool(body.get("monitored", True)),
        status=ItemStatus.wanted,
        quality_profile=body.get("quality_profile"),
        imdb_id=details.get("imdb_id"),
        tvdb_id=details.get("tvdb_id"),
        external_ids=_json.dumps(details.get("external_ids") or {}),
    )
    db.add(series)
    db.commit()
    db.refresh(series)
    return {"ok": True, "id": series.id, "title": series.title, "imdb_id": series.imdb_id, "tvdb_id": series.tvdb_id}

@router.get("", response_model=list[SeriesOut])
def list_series(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.view"))):
    items = db.query(MediaItem).filter(MediaItem.media_type == MediaType.tv).all()
    return [_to_series_out(i) for i in items]


@router.get("/{series_id}", response_model=SeriesOut)
def get_series(series_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, series_id)
    if not item or item.media_type != MediaType.tv:
        raise HTTPException(404, "Not found")
    return _to_series_out(item)


@router.patch("/{series_id}", response_model=SeriesOut)
def update_series(series_id: int, payload: SeriesUpdate, db: Session = Depends(get_db)):
    item = db.get(MediaItem, series_id)
    if not item or item.media_type != MediaType.tv:
        raise HTTPException(404, "Not found")
    if payload.monitored is not None:
        item.monitored = payload.monitored
    if payload.quality_profile is not None:
        item.quality_profile = payload.quality_profile or None
    if payload.monitor is not None:
        item.monitor_mode = payload.monitor
        apply_monitor_mode(list(item.episodes), payload.monitor)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_series_out(item)


@router.delete("/{series_id}", status_code=204)
def delete_series(series_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, series_id)
    if not item or item.media_type != MediaType.tv:
        raise HTTPException(404, "Not found")
    db.delete(item)
    db.commit()


@router.get("/{series_id}/episodes", response_model=list[EpisodeOut])
def list_episodes(series_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, series_id)
    if not item or item.media_type != MediaType.tv:
        raise HTTPException(404, "Not found")
    return sorted(item.episodes, key=lambda e: (e.season_number, e.episode_number))


@router.patch("/episodes/{episode_id}", response_model=EpisodeOut)
def update_episode(
    episode_id: int, payload: EpisodeUpdate, db: Session = Depends(get_db)
):
    episode = db.get(Episode, episode_id)
    if not episode:
        raise HTTPException(404, "Not found")
    if payload.monitored is not None:
        episode.monitored = payload.monitored
    db.add(episode)
    db.commit()
    db.refresh(episode)
    return episode


@router.post("/episodes/{episode_id}/search", response_model=ReleaseOut | None)
def search_and_grab_episode(episode_id: int, db: Session = Depends(get_db)):
    episode = db.get(Episode, episode_id)
    if not episode:
        raise HTTPException(404, "Not found")
    series = episode.series
    release = find_best_episode_release(series, episode, db=db)
    episode.last_searched_at = datetime.now(timezone.utc)
    db.add(episode)
    db.commit()
    if not release:
        return None
    grab_episode_release(db, series, episode, release)
    return ReleaseOut(
        title=release.get("title") or "",
        indexer=release.get("indexer"),
        size=release.get("size"),
        seeders=release.get("seeders"),
        download_url=release.get("download_url") or "",
        score=release.get("_score"),
    )


@router.post("/{series_id}/search-missing")
def search_missing(series_id: int, db: Session = Depends(get_db)):
    """Sonarr-style: search all monitored missing episodes (and try season packs)."""
    item = db.get(MediaItem, series_id)
    if not item or item.media_type != MediaType.tv:
        raise HTTPException(404, "Not found")
    results = _search_missing_for_series(db, item, limit=50)
    return {"searched": len(results), "grabs": results}


@router.post("/{series_id}/search-season/{season}")
def search_season(series_id: int, season: int, db: Session = Depends(get_db)):
    """Prefer a season pack; fall back to per-episode for that season."""
    item = db.get(MediaItem, series_id)
    if not item or item.media_type != MediaType.tv:
        raise HTTPException(404, "Not found")

    pack = find_best_season_pack(item, season, db=db)
    grabs = []
    if pack:
        # Attach pack to first missing monitored episode in season as anchor
        anchor = next(
            (
                e
                for e in item.episodes
                if e.season_number == season
                and e.monitored
                and e.status != ItemStatus.downloaded
            ),
            None,
        )
        if anchor:
            grab_episode_release(db, item, anchor, pack)
            grabs.append({"type": "season_pack", "title": pack.get("title"), "score": pack.get("_score")})
            return {"grabs": grabs}

    for ep in item.episodes:
        if ep.season_number != season:
            continue
        if not ep.monitored or ep.status == ItemStatus.downloaded:
            continue
        rel = find_best_episode_release(item, ep, db=db)
        ep.last_searched_at = datetime.now(timezone.utc)
        db.add(ep)
        if rel:
            grab_episode_release(db, item, ep, rel)
            grabs.append({"type": "episode", "ep": f"S{season:02d}E{ep.episode_number:02d}", "title": rel.get("title")})
    db.commit()
    return {"grabs": grabs}


@router.post("/{series_id}/refresh")
def refresh_series(series_id: int, db: Session = Depends(get_db)):
    """Re-pull episodes from TVDb; keep existing file_path/status where numbers match."""
    item = db.get(MediaItem, series_id)
    if not item or item.media_type != MediaType.tv:
        raise HTTPException(404, "Not found")

    details = tvdb_client.get_series(item.external_id)
    item.title = details["title"] or item.title
    item.year = details.get("year") or item.year
    item.overview = details.get("overview") or item.overview
    item.poster_path = details.get("poster_path") or item.poster_path
    if details.get("series_status"):
        item.series_status = details.get("series_status")

    existing = {(e.season_number, e.episode_number): e for e in item.episodes}
    remote = tvdb_client.get_episodes(item.external_id)
    seen = set()
    for ep in remote:
        key = (ep["season_number"], ep["episode_number"])
        seen.add(key)
        if key in existing:
            e = existing[key]
            e.title = ep.get("title") or e.title
            e.air_date = ep.get("air_date") or e.air_date
            db.add(e)
        else:
            e = Episode(
                media_item_id=item.id,
                season_number=ep["season_number"],
                episode_number=ep["episode_number"],
                title=ep.get("title"),
                air_date=ep.get("air_date"),
                monitored=item.monitored,
                status=ItemStatus.wanted,
            )
            db.add(e)

    apply_monitor_mode(list(item.episodes), item.monitor_mode or "all")
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_series_out(item)


def _search_missing_for_series(
    db: Session, series: MediaItem, limit: int = 30
) -> list[dict]:
    grabs = []
    # Group missing by season — try pack first when many missing
    from collections import defaultdict

    missing_by_season: dict[int, list[Episode]] = defaultdict(list)
    for ep in series.episodes:
        if (
            ep.monitored
            and ep.status in (ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed)
        ):
            missing_by_season[ep.season_number].append(ep)

    for season, eps in sorted(missing_by_season.items()):
        if len(eps) >= 3:
            pack = find_best_season_pack(series, season, db=db)
            if pack:
                grab_episode_release(db, series, eps[0], pack)
                grabs.append(
                    {
                        "type": "season_pack",
                        "season": season,
                        "title": pack.get("title"),
                        "score": pack.get("_score"),
                    }
                )
                if len(grabs) >= limit:
                    break
                continue

        for ep in eps:
            if len(grabs) >= limit:
                break
            rel = find_best_episode_release(series, ep, db=db)
            ep.last_searched_at = datetime.now(timezone.utc)
            db.add(ep)
            if rel:
                grab_episode_release(db, series, ep, rel)
                grabs.append(
                    {
                        "type": "episode",
                        "ep": f"S{ep.season_number:02d}E{ep.episode_number:02d}",
                        "title": rel.get("title"),
                        "score": rel.get("_score"),
                    }
                )
    db.commit()
    return grabs



@router.post("/episodes/{episode_id}/subtitles")
def fetch_episode_subtitles(episode_id: int, db: Session = Depends(get_db), profile_id: int | None = None):
    from pathlib import Path
    from app.services.subtitles import fetch_subtitles
    from app.services.subtitle_profiles import resolve_languages

    ep = db.get(Episode, episode_id)
    if not ep:
        raise HTTPException(404, "Not found")
    series = ep.series
    if not ep.file_path:
        raise HTTPException(400, "No video file on disk")
    path = Path(ep.file_path)
    if not path.exists():
        raise HTTPException(400, "File missing on disk")
    prof = resolve_languages(profile_id)
    return fetch_subtitles(
        path,
        item=series,
        episode=ep,
        languages=prof["languages_csv"],
        hearing_impaired=prof["hearing_impaired"],
    )


class BulkTvIn(BaseModel):
    ids: list[int]
    quality_profile: str | None = None
    monitored: bool | None = None
    series_type: str | None = None


@router.post("/bulk")
def bulk_update_tv(payload: BulkTvIn, db: Session = Depends(get_db)):
    n = 0
    for i in payload.ids:
        item = db.get(MediaItem, i)
        if not item or item.media_type != MediaType.tv:
            continue
        if payload.quality_profile is not None:
            item.quality_profile = payload.quality_profile
        if payload.monitored is not None:
            item.monitored = payload.monitored
        if payload.series_type is not None:
            item.series_type = payload.series_type
        db.add(item)
        n += 1
    db.commit()
    return {"ok": True, "updated": n}


class InteractiveRelease(BaseModel):
    title: str
    indexer: str | None = None
    size: int | None = None
    seeders: int | None = None
    download_url: str = ""
    score: int | None = None
    matched_formats: list[str] = Field(default_factory=list)
    protocol: str | None = None
    age_hours: float | None = None
    rejected: bool = False
    rejections: list[str] = Field(default_factory=list)
    is_season_pack: bool = False
    is_multi_season_pack: bool = False
    parsed_resolution: str | None = None
    parsed_codec: str | None = None
    parsed_source: str | None = None
    parsed_group: str | None = None


class InteractiveSearchResponse(BaseModel):
    media_type: str = "tv"
    scope: str | None = None
    season: int | None = None
    episode: int | None = None
    packs_only: bool | None = None
    queries: list[str] = Field(default_factory=list)
    results: list[InteractiveRelease] = Field(default_factory=list)
    rejected: list[InteractiveRelease] = Field(default_factory=list)
    indexer_results: list[dict] = Field(default_factory=list)
    total_raw: int = 0
    search_time_ms: int = 0
    rejection_breakdown: dict = Field(default_factory=dict)
    accepted_count: int = 0
    rejected_count: int = 0
    rate_limit: dict | None = None



class GrabReleaseIn(BaseModel):
    title: str
    download_url: str
    indexer: str | None = None
    size: int | None = None
    seeders: int | None = None
    score: int | None = None
    protocol: str | None = "torrent"


class EpisodeFileIn(BaseModel):
    file_path: str | None = None
    clear: bool = False
    delete_file: bool = False


@router.get("/episodes/{episode_id}/interactive-search", response_model=InteractiveSearchResponse)
def interactive_search_episode(episode_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """Episode interactive search with rejects + indexer stats."""
    from app.services.interactive_search import interactive_episode_search
    episode = db.get(Episode, episode_id)
    if not episode:
        raise HTTPException(404, "Not found")
    series = episode.series
    if not series:
        raise HTTPException(404, "Series not found")
    episode.last_searched_at = datetime.now(timezone.utc)
    db.add(episode)
    db.commit()
    data = interactive_episode_search(series, episode, db=db, limit=limit)

    def _map(rows):
        return [
            InteractiveRelease(
                title=r.get("title") or "",
                indexer=r.get("indexer"),
                size=r.get("size"),
                seeders=r.get("seeders"),
                download_url=r.get("download_url") or r.get("magnet") or "",
                score=r.get("_score"),
                matched_formats=list(r.get("_matched_formats") or []),
                protocol=r.get("protocol"),
                age_hours=r.get("age_hours") or r.get("age"),
                rejected=bool(r.get("rejected")),
                rejections=list(r.get("rejections") or []),
                is_season_pack=bool(r.get("is_season_pack")),
                is_multi_season_pack=bool(r.get("is_multi_season_pack")),
                parsed_resolution=(r.get("_parsed") or {}).get("resolution"),
                parsed_codec=(r.get("_parsed") or {}).get("codec"),
                parsed_source=(r.get("_parsed") or {}).get("source"),
                parsed_group=(r.get("_parsed") or {}).get("group"),
            )
            for r in rows
        ]

    return InteractiveSearchResponse(
        media_type="tv",
        scope="episode",
        season=data.get("season"),
        episode=data.get("episode"),
        queries=data.get("queries") or [],
        results=_map(data.get("results") or []),
        rejected=_map(data.get("rejected") or []),
        indexer_results=data.get("indexer_results") or [],
        total_raw=data.get("total_raw") or 0,
        search_time_ms=data.get("search_time_ms") or 0,
        rejection_breakdown=data.get("rejection_breakdown") or {},
        accepted_count=data.get("accepted_count") or 0,
        rejected_count=data.get("rejected_count") or 0,
        rate_limit=data.get("rate_limit"),
    )
@router.get("/{series_id}/seasons/{season}/interactive-search", response_model=InteractiveSearchResponse)
def interactive_search_season(
    series_id: int,
    season: int,
    limit: int = 50,
    packs_only: bool = True,
    db: Session = Depends(get_db),
):
    """Season pack interactive search (packs_only=true by default)."""
    from app.services.interactive_search import interactive_season_search
    item = db.get(MediaItem, series_id)
    if not item or item.media_type != MediaType.tv:
        raise HTTPException(404, "Not found")
    data = interactive_season_search(item, season, db=db, limit=limit, packs_only=packs_only)

    def _map(rows):
        return [
            InteractiveRelease(
                title=r.get("title") or "",
                indexer=r.get("indexer"),
                size=r.get("size"),
                seeders=r.get("seeders"),
                download_url=r.get("download_url") or r.get("magnet") or "",
                score=r.get("_score"),
                matched_formats=list(r.get("_matched_formats") or []),
                protocol=r.get("protocol"),
                age_hours=r.get("age_hours") or r.get("age"),
                rejected=bool(r.get("rejected")),
                rejections=list(r.get("rejections") or []),
                is_season_pack=bool(r.get("is_season_pack")),
                is_multi_season_pack=bool(r.get("is_multi_season_pack")),
                parsed_resolution=(r.get("_parsed") or {}).get("resolution"),
                parsed_codec=(r.get("_parsed") or {}).get("codec"),
                parsed_source=(r.get("_parsed") or {}).get("source"),
                parsed_group=(r.get("_parsed") or {}).get("group"),
            )
            for r in rows
        ]

    return InteractiveSearchResponse(
        media_type="tv",
        scope="season",
        season=season,
        packs_only=packs_only,
        queries=data.get("queries") or [],
        results=_map(data.get("results") or []),
        rejected=_map(data.get("rejected") or []),
        indexer_results=data.get("indexer_results") or [],
        total_raw=data.get("total_raw") or 0,
        search_time_ms=data.get("search_time_ms") or 0,
        rejection_breakdown=data.get("rejection_breakdown") or {},
        accepted_count=data.get("accepted_count") or 0,
        rejected_count=data.get("rejected_count") or 0,
        rate_limit=data.get("rate_limit"),
    )


@router.get("/{series_id}/interactive-search/series-pack", response_model=InteractiveSearchResponse)
def interactive_search_series_pack(series_id: int, limit: int = 40, db: Session = Depends(get_db)):
    """Complete-series / multi-season pack search."""
    from app.services.interactive_search import interactive_series_pack_search
    item = db.get(MediaItem, series_id)
    if not item or item.media_type != MediaType.tv:
        raise HTTPException(404, "Not found")
    data = interactive_series_pack_search(item, db=db, limit=limit)

    def _map(rows):
        return [
            InteractiveRelease(
                title=r.get("title") or "",
                indexer=r.get("indexer"),
                size=r.get("size"),
                seeders=r.get("seeders"),
                download_url=r.get("download_url") or r.get("magnet") or "",
                score=r.get("_score"),
                matched_formats=list(r.get("_matched_formats") or []),
                protocol=r.get("protocol"),
                age_hours=r.get("age_hours") or r.get("age"),
                rejected=bool(r.get("rejected")),
                rejections=list(r.get("rejections") or []),
                is_season_pack=bool(r.get("is_season_pack")),
                is_multi_season_pack=bool(r.get("is_multi_season_pack")),
                parsed_resolution=(r.get("_parsed") or {}).get("resolution"),
                parsed_codec=(r.get("_parsed") or {}).get("codec"),
                parsed_source=(r.get("_parsed") or {}).get("source"),
                parsed_group=(r.get("_parsed") or {}).get("group"),
            )
            for r in rows
        ]

    return InteractiveSearchResponse(
        media_type="tv",
        scope="seriesPack",
        queries=data.get("queries") or [],
        results=_map(data.get("results") or []),
        rejected=_map(data.get("rejected") or []),
        indexer_results=data.get("indexer_results") or [],
        total_raw=data.get("total_raw") or 0,
        search_time_ms=data.get("search_time_ms") or 0,
        rejection_breakdown=data.get("rejection_breakdown") or {},
        accepted_count=data.get("accepted_count") or 0,
        rejected_count=data.get("rejected_count") or 0,
        rate_limit=data.get("rate_limit"),
    )
@router.post("/episodes/{episode_id}/grab")
def grab_selected_release(episode_id: int, payload: GrabReleaseIn, db: Session = Depends(get_db)):
    """Grab a user-selected release from interactive search."""
    episode = db.get(Episode, episode_id)
    if not episode:
        raise HTTPException(404, "Not found")
    series = episode.series
    if not series:
        raise HTTPException(404, "Series not found")
    release = {
        "title": payload.title,
        "download_url": payload.download_url,
        "indexer": payload.indexer,
        "size": payload.size,
        "seeders": payload.seeders,
        "_score": payload.score,
        "protocol": payload.protocol or "torrent",
    }
    grab_episode_release(db, series, episode, release)
    return {"ok": True, "title": payload.title, "episode_id": episode_id}


@router.post("/episodes/{episode_id}/file")
def manage_episode_file(episode_id: int, payload: EpisodeFileIn, db: Session = Depends(get_db)):
    """Season/episode file management: set path, clear, or delete from disk."""
    from pathlib import Path as P
    episode = db.get(Episode, episode_id)
    if not episode:
        raise HTTPException(404, "Not found")
    if payload.delete_file and episode.file_path:
        path = P(episode.file_path)
        try:
            if path.is_file():
                path.unlink()
        except Exception as e:
            raise HTTPException(400, f"Could not delete file: {e}") from e
        episode.file_path = None
        episode.status = ItemStatus.missing
    elif payload.clear:
        episode.file_path = None
        if episode.status == ItemStatus.downloaded:
            episode.status = ItemStatus.missing
    elif payload.file_path is not None:
        episode.file_path = payload.file_path
        if payload.file_path:
            episode.status = ItemStatus.downloaded
    db.add(episode)
    db.commit()
    db.refresh(episode)
    return {
        "id": episode.id,
        "file_path": episode.file_path,
        "status": episode.status.value if episode.status else None,
    }


@router.post("/episodes/{episode_id}/unmonitor")
def unmonitor_episode(episode_id: int, db: Session = Depends(get_db)):
    episode = db.get(Episode, episode_id)
    if not episode:
        raise HTTPException(404)
    episode.monitored = False
    db.add(episode)
    db.commit()
    return {"ok": True, "monitored": False}


@router.post("/refresh-series-status")
def refresh_all_series_status(
    limit: int = 200,
    db: Session = Depends(get_db),
    _: list = Depends(require_permission("library.manage", "settings")),
):
    """Backfill series_status (continuing/ended) from TVDb for existing library rows."""
    rows = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.tv)
        .order_by(MediaItem.id.asc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    updated = failed = skipped = 0
    for item in rows:
        try:
            details = tvdb_client.get_series(int(item.external_id))
            st = details.get("series_status")
            if not st:
                skipped += 1
                continue
            if item.series_status == st:
                skipped += 1
                continue
            item.series_status = st
            if details.get("poster_path"):
                item.poster_path = details.get("poster_path") or item.poster_path
            db.add(item)
            updated += 1
        except Exception:
            failed += 1
    db.commit()
    return {"ok": True, "updated": updated, "skipped": skipped, "failed": failed, "scanned": len(rows)}

