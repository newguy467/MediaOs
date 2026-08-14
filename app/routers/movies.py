from datetime import datetime, timezone

from app.auth import require_permission
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.clients.tmdb import tmdb_client
from app.database import get_db
from app.models import ItemStatus, MediaItem, MediaType
from app.schemas import MovieCreate, MovieOut, MovieUpdate, ReleaseOut, SearchResult
from app.services.grab import grab_release
from app.services.search import find_best_movie_release, search_movie_releases

router = APIRouter(prefix="/movies", tags=["movies"],
    dependencies=[Depends(require_permission("library.view", "library.manage"))],
)


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
    media_type: str = "movie"
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
    protocol: str | None = "torrent"
    quality_score: int | None = None


class MovieFileIn(BaseModel):
    file_path: str | None = None
    clear: bool = False


class BulkProfileIn(BaseModel):
    ids: list[int]
    quality_profile: str | None = None
    monitored: bool | None = None


@router.get("/search", response_model=list[SearchResult])
def search_tmdb(query: str):
    return tmdb_client.search_movie(query)


@router.post("", response_model=MovieOut)
def add_movie(payload: MovieCreate, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage", "download"))):
    existing = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.movie,
            MediaItem.external_id == payload.external_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(409, "Movie already in library")

    details = tmdb_client.get_movie(payload.external_id)
    import json as _json
    item = MediaItem(
        media_type=MediaType.movie,
        external_id=details["external_id"],
        external_source="tmdb",
        title=details["title"],
        year=details["year"],
        overview=details["overview"],
        poster_path=details["poster_path"],
        monitored=payload.monitored,
        status=ItemStatus.wanted,
        quality_profile=payload.quality_profile,
        imdb_id=details.get("imdb_id"),
        tvdb_id=details.get("tvdb_id"),
        external_ids=_json.dumps(details.get("external_ids") or {}) if details.get("external_ids") else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    if getattr(payload, "search_missing", True) or getattr(payload, "search", False):
        try:
            release = find_best_movie_release(item, db=db)
            if release:
                grab_release(db, item, release)
        except Exception:
            pass
        db.refresh(item)
    return item


@router.get("", response_model=list[MovieOut])
def list_movies(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.view"))):
    return (
        db.query(MediaItem).filter(MediaItem.media_type == MediaType.movie).order_by(MediaItem.title).all()
    )


@router.post("/search-missing")
def search_all_missing_movies(limit: int = 40, db: Session = Depends(get_db)):
    """Radarr-style search for all monitored missing movies."""
    rows = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.movie,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .limit(limit)
        .all()
    )
    grabbed = 0
    searched = 0
    for item in rows:
        searched += 1
        item.last_searched_at = datetime.now(timezone.utc)
        db.add(item)
        try:
            release = find_best_movie_release(item, db=db)
            if release:
                grab_release(db, item, release)
                grabbed += 1
        except Exception:
            continue
    db.commit()
    return {"searched": searched, "grabbed": grabbed}


@router.get("/{item_id}", response_model=MovieOut)
def get_movie(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404, "Not found")
    return item


@router.post("/{item_id}/search", response_model=ReleaseOut | None)
def search_and_grab(item_id: int, db: Session = Depends(get_db), _: list = Depends(require_permission("download"))):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404, "Not found")

    release = find_best_movie_release(item, db=db)
    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()

    if not release:
        return None

    grab_release(db, item, release)
    return release


@router.get("/{item_id}/interactive-search", response_model=InteractiveSearchResponse)
def interactive_search_movie(item_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """Radarr-style interactive search — accepted + rejected + indexer stats."""
    from app.services.interactive_search import interactive_movie_search
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404, "Not found")
    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    data = interactive_movie_search(item, db=db, limit=limit)

    def _map(rows):
        out = []
        for r in rows:
            out.append(InteractiveRelease(
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
            ))
        return out

    return InteractiveSearchResponse(
        media_type="movie",
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
@router.post("/{item_id}/grab")
def grab_selected_release(item_id: int, payload: GrabReleaseIn, db: Session = Depends(get_db)):
    """Grab a user-selected release from interactive search."""
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404, "Not found")
    release = {
        "title": payload.title,
        "download_url": payload.download_url,
        "indexer": payload.indexer,
        "size": payload.size,
        "seeders": payload.seeders,
        "protocol": payload.protocol or "torrent",
        "quality_score": payload.quality_score,
    }
    grab_release(db, item, release)
    return {"ok": True, "title": payload.title}


@router.post("/{item_id}/refresh")
def refresh_movie(item_id: int, db: Session = Depends(get_db)):
    """Refresh metadata from TMDb."""
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404, "Not found")
    try:
        details = tmdb_client.get_movie(item.external_id)
        item.title = details.get("title") or item.title
        item.year = details.get("year") or item.year
        item.overview = details.get("overview") or item.overview
        item.poster_path = details.get("poster_path") or item.poster_path
        db.add(item)
        db.commit()
        db.refresh(item)
    except Exception as e:
        raise HTTPException(502, f"TMDb refresh failed: {e}")
    return item


@router.post("/{item_id}/file")
def manage_movie_file(item_id: int, payload: MovieFileIn, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404, "Not found")
    if payload.clear:
        item.file_path = None
        item.status = ItemStatus.missing if item.monitored else ItemStatus.wanted
    elif payload.file_path:
        item.file_path = payload.file_path
        item.status = ItemStatus.downloaded
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=MovieOut)
def update_movie(item_id: int, payload: MovieUpdate, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404, "Not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(item, k, v)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_movie(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404, "Not found")
    db.delete(item)
    db.commit()


@router.post("/{item_id}/subtitles")
def fetch_movie_subtitles(item_id: int, db: Session = Depends(get_db)):
    from pathlib import Path

    from app.services.subtitles import fetch_subtitles
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404, "Not found")
    if not item.file_path:
        raise HTTPException(400, "File missing on disk")
    video = Path(item.file_path)
    if not video.is_file():
        raise HTTPException(400, "File missing on disk")
    return fetch_subtitles(video, item=item)


@router.post("/bulk")
def bulk_update_movies(payload: BulkProfileIn, db: Session = Depends(get_db)):
    updated = 0
    for iid in payload.ids:
        item = db.get(MediaItem, iid)
        if not item or item.media_type != MediaType.movie:
            continue
        if payload.quality_profile is not None:
            item.quality_profile = payload.quality_profile
        if payload.monitored is not None:
            item.monitored = payload.monitored
        db.add(item)
        updated += 1
    db.commit()
    return {"updated": updated}


@router.patch("/{item_id}/desired-qualities")
def set_desired_qualities(item_id: int, body: dict, db: Session = Depends(get_db)):
    """Set preferred resolutions for interactive search e.g. ["1080p","2160p"]."""
    import json
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404, "Not found")
    quals = body.get("desired_qualities") or body.get("qualities") or []
    if isinstance(quals, str):
        quals = [q.strip() for q in quals.split(",") if q.strip()]
    item.desired_qualities = json.dumps(list(quals))
    db.add(item)
    db.commit()
    return {"ok": True, "desired_qualities": quals}

