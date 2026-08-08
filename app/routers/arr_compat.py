"""Partial Sonarr/Radarr v3 API shim for LunaSea and similar clients.

LunaSea and Jellyseerr connect with host + X-Api-Key. Point it at mediaos and use the same
API key as AUTH_API_KEY or ARR_API_KEY. Not full *arr parity — enough for
library, calendar, queue, status, and search triggers.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import Download, Episode, ItemStatus, MediaItem, MediaType
from app.services.grab import grab_episode_release, grab_release
from app.services.search import find_best_episode_release, find_best_movie_release

router = APIRouter(tags=["arr-compat"])


def _arr_key() -> str:
    return (settings.arr_api_key or settings.auth_api_key or "").strip()


def require_arr_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    apikey: str | None = Query(default=None),
):
    expected = _arr_key()
    if not expected:
        # open mode when no key configured
        return True
    got = (x_api_key or apikey or "").strip()
    if got != expected:
        raise HTTPException(401, "Unauthorized")
    return True


def _movie_resource(item: MediaItem) -> dict:
    has_file = bool(item.file_path) and item.status == ItemStatus.downloaded
    tmdb_id = item.external_id if (item.external_source in (None, "tmdb", "") or not item.external_source) else item.external_id
    return {
        "id": item.id,
        "title": item.title,
        "sortTitle": item.title,
        "year": item.year or 0,
        "overview": item.overview,
        "status": "released",
        "monitored": item.monitored,
        "hasFile": has_file,
        "isAvailable": has_file,
        "path": item.file_path or settings.movies_library_path,
        "rootFolderPath": settings.movies_library_path,
        "qualityProfileId": 1,
        "minimumAvailability": "released",
        "tmdbId": tmdb_id or 0,
        "imdbId": None,
        "images": [
            {
                "coverType": "poster",
                "remoteUrl": f"https://image.tmdb.org/t/p/w500{item.poster_path}"
                if item.poster_path and str(item.poster_path).startswith("/")
                else item.poster_path,
            }
        ]
        if item.poster_path
        else [],
        "added": item.added_at.isoformat() if item.added_at else None,
        "sizeOnDisk": 0,
        "movieFile": {"path": item.file_path, "quality": {"quality": {"name": "Unknown"}}}
        if item.file_path
        else None,
    }


def _series_resource(item: MediaItem) -> dict:
    eps = list(item.episodes or [])
    seasons_map: dict[int, dict] = {}
    for e in eps:
        s = seasons_map.setdefault(
            e.season_number,
            {"seasonNumber": e.season_number, "monitored": True, "statistics": {"episodeFileCount": 0, "totalEpisodeCount": 0, "episodeCount": 0}},
        )
        s["statistics"]["totalEpisodeCount"] += 1
        s["statistics"]["episodeCount"] += 1
        if e.file_path:
            s["statistics"]["episodeFileCount"] += 1
    return {
        "id": item.id,
        "title": item.title,
        "sortTitle": item.title,
        "year": item.year or 0,
        "overview": item.overview,
        "status": "continuing",
        "monitored": item.monitored,
        "seasonFolder": True,
        "path": settings.tv_library_path,
        "rootFolderPath": settings.tv_library_path,
        "qualityProfileId": 1,
        "languageProfileId": 1,
        "seriesType": "standard",
        "tvdbId": item.external_id if (item.external_source in (None, "tvdb", "") or not item.external_source) else item.external_id,
        "images": [
            {
                "coverType": "poster",
                "remoteUrl": item.poster_path,
            }
        ]
        if item.poster_path
        else [],
        "seasons": sorted(seasons_map.values(), key=lambda x: x["seasonNumber"]),
        "statistics": {
            "episodeCount": len(eps),
            "episodeFileCount": sum(1 for e in eps if e.file_path),
            "percentOfEpisodes": (
                (100.0 * sum(1 for e in eps if e.file_path) / len(eps)) if eps else 0
            ),
        },
        "added": item.added_at.isoformat() if item.added_at else None,
    }


# ── System ────────────────────────────────────────────────────────────────

@router.get("/api/v3/system/status")
def system_status(_: bool = Depends(require_arr_key)):
    return {
        "appName": "mediaos",
        "instanceName": "mediaos",
        "version": "1.5.0",
        "buildTime": datetime.now(timezone.utc).isoformat(),
        "isDebug": False,
        "isProduction": True,
        "isAdmin": True,
        "isUserInteractive": False,
        "startupPath": "/app",
        "appData": "/config",
        "osName": "linux",
        "isLinux": True,
        "isDocker": True,
        "mode": "console",
        "branch": "main",
        "authentication": "apikey" if _arr_key() else "none",
        "urlBase": "",
        "runtimeVersion": "3.12",
    }


@router.get("/api/v3/health")
def health(_: bool = Depends(require_arr_key)):
    return []


@router.get("/api/v3/diskspace")
def diskspace(_: bool = Depends(require_arr_key)):
    return []


@router.get("/api/v3/rootfolder")
def rootfolder(_: bool = Depends(require_arr_key)):
    return [
        {"id": 1, "path": settings.movies_library_path, "accessible": True, "freeSpace": 0},
        {"id": 2, "path": settings.tv_library_path, "accessible": True, "freeSpace": 0},
    ]


@router.get("/api/v3/qualityprofile")
def qualityprofile(_: bool = Depends(require_arr_key), db: Session = Depends(get_db)):
    from app.models import QualityProfileRecord
    from app.services.quality.store import seed_default_profiles

    seed_default_profiles(db)
    rows = db.query(QualityProfileRecord).all()
    return [
        {"id": r.id, "name": r.name, "upgradeAllowed": True, "cutoff": 1, "items": []}
        for r in rows
    ] or [{"id": 1, "name": "Any", "upgradeAllowed": True, "cutoff": 1, "items": []}]


# ── Radarr-style movies ───────────────────────────────────────────────────

@router.get("/api/v3/movie")
def list_movies(_: bool = Depends(require_arr_key), db: Session = Depends(get_db)):
    items = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.movie)
        .order_by(MediaItem.title)
        .all()
    )
    return [_movie_resource(i) for i in items]


# lookup registered below before int path — see movie_lookup / get_movie_int


@router.post("/api/v3/command")
async def command(request: Request, _: bool = Depends(require_arr_key), db: Session = Depends(get_db)):
    body = await request.json()
    name = (body.get("name") or "").lower()
    # MoviesSearch / SeriesSearch / MissingMovieSearch etc.
    if "movie" in name and "search" in name:
        movie_ids = body.get("movieIds") or body.get("movieId")
        ids = movie_ids if isinstance(movie_ids, list) else ([movie_ids] if movie_ids else [])
        if not ids and "missing" in name:
            # MissingMoviesSearch — all monitored missing
            ids = [
                i.id for i in db.query(MediaItem).filter(
                    MediaItem.media_type == MediaType.movie,
                    MediaItem.monitored.is_(True),
                    MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
                ).limit(50).all()
            ]
        for mid in ids:
            try:
                item = db.get(MediaItem, int(mid))
            except (TypeError, ValueError):
                continue
            if item and item.media_type == MediaType.movie:
                rel = find_best_movie_release(item, db=db)
                if rel:
                    try:
                        grab_release(db, item, rel)
                    except Exception:
                        pass
    if "series" in name and "search" in name:
        series_id = body.get("seriesId") or body.get("seriesIds")
        ids = series_id if isinstance(series_id, list) else ([series_id] if series_id else [])
        for sid in ids:
            item = db.get(MediaItem, int(sid))
            if not item or item.media_type != MediaType.tv:
                continue
            for ep in item.episodes or []:
                if ep.monitored and ep.status in (
                    ItemStatus.wanted,
                    ItemStatus.missing,
                    ItemStatus.failed,
                ):
                    rel = find_best_episode_release(item, ep, db=db)
                    if rel:
                        try:
                            grab_episode_release(db, item, ep, rel)
                        except Exception:
                            pass
    return {
        "id": 1,
        "name": body.get("name"),
        "status": "completed",
        "queued": datetime.now(timezone.utc).isoformat(),
        "started": datetime.now(timezone.utc).isoformat(),
        "ended": datetime.now(timezone.utc).isoformat(),
    }


# ── Sonarr-style series ───────────────────────────────────────────────────

@router.get("/api/v3/series")
def list_series(_: bool = Depends(require_arr_key), db: Session = Depends(get_db)):
    items = (
        db.query(MediaItem)
        .options(joinedload(MediaItem.episodes))
        .filter(MediaItem.media_type == MediaType.tv)
        .order_by(MediaItem.title)
        .all()
    )
    return [_series_resource(i) for i in items]





@router.get("/api/v3/calendar")
def calendar(
    start: str | None = None,
    end: str | None = None,
    _: bool = Depends(require_arr_key),
    db: Session = Depends(get_db),
):
    today = date.today()
    try:
        start_d = date.fromisoformat(start[:10]) if start else today - timedelta(days=7)
    except ValueError:
        start_d = today - timedelta(days=7)
    try:
        end_d = date.fromisoformat(end[:10]) if end else today + timedelta(days=30)
    except ValueError:
        end_d = today + timedelta(days=30)
    eps = (
        db.query(Episode)
        .join(MediaItem)
        .options(joinedload(Episode.series))
        .filter(
            Episode.air_date.isnot(None),
            Episode.air_date >= start_d.isoformat(),
            Episode.air_date <= end_d.isoformat(),
        )
        .all()
    )
    out = []
    for ep in eps:
        s = ep.series
        if not s:
            continue
        out.append(
            {
                "id": ep.id,
                "seriesId": s.id,
                "series": _series_resource(s),
                "episodeNumber": ep.episode_number,
                "seasonNumber": ep.season_number,
                "title": ep.title,
                "airDate": ep.air_date,
                "airDateUtc": ep.air_date,
                "hasFile": bool(ep.file_path),
                "monitored": ep.monitored,
            }
        )
    return out


@router.get("/api/v3/queue")
def queue(_: bool = Depends(require_arr_key), db: Session = Depends(get_db)):
    rows = (
        db.query(Download)
        .options(joinedload(Download.media_item), joinedload(Download.episode))
        .filter(Download.status.in_(["grabbed", "downloading"]))
        .all()
    )
    records = []
    for d in rows:
        item = d.media_item
        records.append(
            {
                "id": d.id,
                "title": d.release_title or (item.title if item else "?"),
                "status": "downloading",
                "trackedDownloadStatus": "ok",
                "trackedDownloadState": "downloading",
                "protocol": "torrent",
                "size": 0,
                "sizeleft": 0,
                "movieId": item.id if item and item.media_type == MediaType.movie else None,
                "seriesId": item.id if item and item.media_type == MediaType.tv else None,
            }
        )
    return {"page": 1, "pageSize": 50, "totalRecords": len(records), "records": records}


@router.get("/api/v3/history")
def history(
    page: int = 1,
    pageSize: int = 20,
    _: bool = Depends(require_arr_key),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Download)
        .options(joinedload(Download.media_item))
        .order_by(Download.added_at.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )
    records = []
    for d in rows:
        item = d.media_item
        records.append(
            {
                "id": d.id,
                "sourceTitle": d.release_title,
                "date": d.added_at.isoformat() if d.added_at else None,
                "eventType": d.status,
                "movieId": item.id if item and item.media_type == MediaType.movie else None,
                "seriesId": item.id if item and item.media_type == MediaType.tv else None,
            }
        )
    return {"page": page, "pageSize": pageSize, "totalRecords": len(records), "records": records}



# ── Jellyseerr: lookup + add ──────────────────────────────────────────────

@router.get("/api/v3/tag")
def tags(_: bool = Depends(require_arr_key)):
    return []


@router.get("/api/v3/languageprofile")
def language_profiles(_: bool = Depends(require_arr_key)):
    return [{"id": 1, "name": "English", "upgradeAllowed": True, "cutoff": 1, "languages": [{"id": 1, "name": "English"}]}]


@router.get("/api/v3/movie/lookup")
def movie_lookup(term: str = "", _: bool = Depends(require_arr_key)):
    from app.clients.tmdb import tmdb_client

    term = (term or "").strip()
    if not term:
        return []
    # tmdb:12345 style
    if term.lower().startswith("tmdb:"):
        try:
            mid = int(term.split(":", 1)[1])
            m = tmdb_client.get_movie(mid)
            return [{
                "title": m["title"],
                "year": m.get("year") or 0,
                "tmdbId": m["external_id"],
                "overview": m.get("overview"),
                "images": [{"coverType": "poster", "remoteUrl": f"https://image.tmdb.org/t/p/w500{m['poster_path']}"}] if m.get("poster_path") else [],
                "qualityProfileId": 1,
                "rootFolderPath": settings.movies_library_path,
                "monitored": True,
                "minimumAvailability": "released",
                "addOptions": {"searchForMovie": True},
            }]
        except Exception:
            return []
    rows = []
    for m in tmdb_client.search_movie(term)[:15]:
        rows.append({
            "title": m["title"],
            "year": m.get("year") or 0,
            "tmdbId": m["external_id"],
            "overview": m.get("overview"),
            "images": [{"coverType": "poster", "remoteUrl": f"https://image.tmdb.org/t/p/w500{m['poster_path']}"}] if m.get("poster_path") else [],
            "qualityProfileId": 1,
            "rootFolderPath": settings.movies_library_path,
            "monitored": True,
            "minimumAvailability": "released",
            "addOptions": {"searchForMovie": True},
        })
    return rows


@router.get("/api/v3/movie/{movie_id}")
def get_movie(movie_id: int, _: bool = Depends(require_arr_key), db: Session = Depends(get_db)):
    item = db.get(MediaItem, movie_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404)
    return _movie_resource(item)


@router.post("/api/v3/movie")
async def add_movie_v3(request: Request, _: bool = Depends(require_arr_key), db: Session = Depends(get_db)):
    """Jellyseerr / Radarr-style add movie."""
    from app.clients.tmdb import tmdb_client

    body = await request.json()
    tmdb_id = body.get("tmdbId") or body.get("tmdb_id")
    if not tmdb_id:
        raise HTTPException(400, "tmdbId required")
    tmdb_id = int(tmdb_id)
    existing = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.movie, MediaItem.external_id == tmdb_id)
        .first()
    )
    if existing:
        return _movie_resource(existing)

    details = tmdb_client.get_movie(tmdb_id)
    item = MediaItem(
        media_type=MediaType.movie,
        external_id=details["external_id"],
        external_source="tmdb",
        title=details["title"],
        year=details.get("year"),
        overview=details.get("overview"),
        poster_path=details.get("poster_path"),
        monitored=bool(body.get("monitored", True)),
        status=ItemStatus.wanted,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    add_opts = body.get("addOptions") or {}
    search = add_opts.get("searchForMovie", True)
    if search and item.monitored:
        try:
            rel = find_best_movie_release(item, db=db)
            if rel:
                grab_release(db, item, rel)
                db.refresh(item)
        except Exception:
            pass
    return _movie_resource(item)


@router.get("/api/v3/series/lookup")
def series_lookup(term: str = "", _: bool = Depends(require_arr_key)):
    from app.clients.tvdb import tvdb_client

    term = (term or "").strip()
    if not term:
        return []
    if term.lower().startswith("tvdb:"):
        try:
            sid = int(term.split(":", 1)[1])
            s = tvdb_client.get_series(sid)
            return [{
                "title": s["title"],
                "year": s.get("year") or 0,
                "tvdbId": s["external_id"],
                "overview": s.get("overview"),
                "images": [{"coverType": "poster", "remoteUrl": s.get("poster_path")}] if s.get("poster_path") else [],
                "qualityProfileId": 1,
                "languageProfileId": 1,
                "rootFolderPath": settings.tv_library_path,
                "monitored": True,
                "seasonFolder": True,
                "seriesType": "standard",
                "seasons": [],
                "addOptions": {"searchForMissingEpisodes": True},
            }]
        except Exception:
            return []
    rows = []
    for s in tvdb_client.search_series(term)[:15]:
        rows.append({
            "title": s["title"],
            "year": s.get("year") or 0,
            "tvdbId": s["external_id"],
            "overview": s.get("overview"),
            "images": [{"coverType": "poster", "remoteUrl": s.get("poster_path")}] if s.get("poster_path") else [],
            "qualityProfileId": 1,
            "languageProfileId": 1,
            "rootFolderPath": settings.tv_library_path,
            "monitored": True,
            "seasonFolder": True,
            "seriesType": "standard",
            "seasons": [],
            "addOptions": {"searchForMissingEpisodes": True},
        })
    return rows


@router.get("/api/v3/series/{series_id}")
def get_series(series_id: int, _: bool = Depends(require_arr_key), db: Session = Depends(get_db)):
    item = db.get(MediaItem, series_id)
    if not item or item.media_type != MediaType.tv:
        raise HTTPException(404)
    return _series_resource(item)


@router.post("/api/v3/series")
async def add_series_v3(request: Request, _: bool = Depends(require_arr_key), db: Session = Depends(get_db)):
    """Jellyseerr / Sonarr-style add series."""
    from app.clients.tvdb import tvdb_client
    from app.services.monitor import apply_monitor_mode

    body = await request.json()
    tvdb_id = body.get("tvdbId") or body.get("tvdb_id")
    if not tvdb_id:
        raise HTTPException(400, "tvdbId required")
    tvdb_id = int(tvdb_id)
    existing = (
        db.query(MediaItem)
        .options(joinedload(MediaItem.episodes))
        .filter(MediaItem.media_type == MediaType.tv, MediaItem.external_id == tvdb_id)
        .first()
    )
    if existing:
        return _series_resource(existing)

    details = tvdb_client.get_series(tvdb_id)
    item = MediaItem(
        media_type=MediaType.tv,
        external_id=details["external_id"],
        external_source="tvdb",
        title=details["title"],
        year=details.get("year"),
        overview=details.get("overview"),
        poster_path=details.get("poster_path"),
        monitored=bool(body.get("monitored", True)),
        status=ItemStatus.wanted,
        monitor_mode="all",
    )
    db.add(item)
    db.flush()

    seasons_body = body.get("seasons") or []
    monitored_seasons = {
        int(s.get("seasonNumber"))
        for s in seasons_body
        if s.get("monitored", True) and s.get("seasonNumber") is not None
    }

    episodes = []
    for ep in tvdb_client.get_episodes(tvdb_id):
        sn = ep["season_number"]
        mon = (not monitored_seasons) or (sn in monitored_seasons) or sn == 0
        e = Episode(
            series_id=item.id,
            season_number=sn,
            episode_number=ep["episode_number"],
            title=ep.get("title"),
            air_date=ep.get("air_date"),
            monitored=mon and item.monitored,
            status=ItemStatus.wanted,
        )
        db.add(e)
        episodes.append(e)
    if not monitored_seasons:
        apply_monitor_mode(episodes, "all")
    db.commit()
    db.refresh(item)
    item = (
        db.query(MediaItem)
        .options(joinedload(MediaItem.episodes))
        .filter(MediaItem.id == item.id)
        .one()
    )

    add_opts = body.get("addOptions") or {}
    if add_opts.get("searchForMissingEpisodes", True) and item.monitored:
        for ep in list(item.episodes or [])[:20]:
            if not ep.monitored:
                continue
            try:
                rel = find_best_episode_release(item, ep, db=db)
                if rel:
                    grab_episode_release(db, item, ep, rel)
            except Exception:
                pass

    return _series_resource(item)



# ── Wanted / missing / cutoff (Sonarr + Radarr style) ─────────────────────

@router.get("/api/v3/wanted/missing")
def wanted_missing(
    page: int = 1,
    pageSize: int = 50,
    _: bool = Depends(require_arr_key),
    db: Session = Depends(get_db),
):
    """Movies + episodes that are monitored and not yet on disk."""
    movies = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.movie,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing]),
        )
        .order_by(MediaItem.title)
        .all()
    )
    episodes = (
        db.query(Episode)
        .options(joinedload(Episode.series))
        .filter(
            Episode.monitored.is_(True),
            Episode.status.in_([ItemStatus.wanted, ItemStatus.missing]),
        )
        .order_by(Episode.air_date.desc().nullslast())
        .all()
    )
    records = []
    for m in movies:
        records.append({"movie": _movie_resource(m), "media_type": "movie"})
    for ep in episodes:
        series = ep.series
        records.append(
            {
                "episode": {
                    "id": ep.id,
                    "seasonNumber": ep.season_number,
                    "episodeNumber": ep.episode_number,
                    "title": ep.title,
                    "airDate": ep.air_date,
                    "hasFile": bool(ep.file_path),
                    "monitored": ep.monitored,
                    "seriesId": ep.series_id,
                },
                "series": _series_resource(series) if series else None,
                "media_type": "episode",
            }
        )
    total = len(records)
    start = (page - 1) * pageSize
    page_records = records[start : start + pageSize]
    return {
        "page": page,
        "pageSize": pageSize,
        "totalRecords": total,
        "records": page_records,
    }


@router.get("/api/v3/wanted/cutoff")
def wanted_cutoff(
    page: int = 1,
    pageSize: int = 50,
    _: bool = Depends(require_arr_key),
    db: Session = Depends(get_db),
):
    """Items that have a file but may still upgrade (simplified: all downloaded monitored)."""
    movies = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.movie,
            MediaItem.monitored.is_(True),
            MediaItem.status == ItemStatus.downloaded,
            MediaItem.file_path.isnot(None),
        )
        .order_by(MediaItem.title)
        .all()
    )
    records = [{"movie": _movie_resource(m)} for m in movies]
    total = len(records)
    start = (page - 1) * pageSize
    return {
        "page": page,
        "pageSize": pageSize,
        "totalRecords": total,
        "records": records[start : start + pageSize],
    }


@router.delete("/api/v3/movie/{movie_id}")
def delete_movie(
    movie_id: int,
    deleteFiles: bool = False,
    _: bool = Depends(require_arr_key),
    db: Session = Depends(get_db),
):
    item = db.get(MediaItem, movie_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404, "Movie not found")
    if deleteFiles and item.file_path:
        from pathlib import Path
        try:
            p = Path(item.file_path)
            if p.is_file():
                p.unlink(missing_ok=True)
        except Exception:
            pass
    db.delete(item)
    db.commit()
    return {}


@router.delete("/api/v3/series/{series_id}")
def delete_series(
    series_id: int,
    deleteFiles: bool = False,
    _: bool = Depends(require_arr_key),
    db: Session = Depends(get_db),
):
    item = (
        db.query(MediaItem)
        .options(joinedload(MediaItem.episodes))
        .filter(MediaItem.id == series_id, MediaItem.media_type == MediaType.tv)
        .first()
    )
    if not item:
        raise HTTPException(404, "Series not found")
    if deleteFiles:
        from pathlib import Path
        for ep in item.episodes or []:
            if ep.file_path:
                try:
                    Path(ep.file_path).unlink(missing_ok=True)
                except Exception:
                    pass
    db.delete(item)
    db.commit()
    return {}


@router.get("/api/v3/episode")
def list_episodes(
    seriesId: int | None = None,
    _: bool = Depends(require_arr_key),
    db: Session = Depends(get_db),
):
    q = db.query(Episode).options(joinedload(Episode.series))
    if seriesId is not None:
        q = q.filter(Episode.series_id == seriesId)
    rows = q.order_by(Episode.season_number, Episode.episode_number).limit(2000).all()
    out = []
    for ep in rows:
        out.append(
            {
                "id": ep.id,
                "seriesId": ep.series_id,
                "seasonNumber": ep.season_number,
                "episodeNumber": ep.episode_number,
                "title": ep.title,
                "airDate": ep.air_date,
                "hasFile": bool(ep.file_path),
                "monitored": ep.monitored,
                "episodeFileId": ep.id if ep.file_path else 0,
            }
        )
    return out
