"""Wanted / Missing media — list + manual or automatic search."""
from __future__ import annotations

from datetime import datetime, timezone

from app.auth import require_permission
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Episode, ItemStatus, MediaItem, MediaType
from app.services.grab import grab_episode_release, grab_release
from app.services.search import (
    find_best_audiobook_release,
    find_best_book_release,
    find_best_episode_release,
    find_best_movie_release,
    find_best_music_release,
)
from app.services.wanted import search_all_missing

router = APIRouter(prefix="/wanted", tags=["wanted"])

MISSING = [ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]


class SearchResultOut(BaseModel):
    found: bool
    title: str | None = None
    indexer: str | None = None
    score: int | None = None
    error: str | None = None


def _utcnow():
    return datetime.now(timezone.utc)


@router.get("")
def list_wanted(
    media_type: str | None = Query(None, description="movie|tv|music|book|audiobook|all"),
    db: Session = Depends(get_db),
):
    mt = (media_type or "all").lower()
    out: dict = {"movies": [], "episodes": [], "music": [], "books": [], "audiobooks": [], "counts": {}}

    if mt in ("all", "movie", "movies"):
        movies = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.movie, MediaItem.monitored.is_(True), MediaItem.status.in_(MISSING))
            .order_by(MediaItem.title).all()
        )
        out["movies"] = [{"id": m.id, "title": m.title, "year": m.year,
            "status": m.status.value if hasattr(m.status, "value") else str(m.status),
            "poster_path": m.poster_path, "quality_profile": m.quality_profile,
            "last_searched_at": m.last_searched_at} for m in movies]

    if mt in ("all", "tv", "episode", "episodes"):
        episodes = (
            db.query(Episode).join(MediaItem).options(joinedload(Episode.series))
            .filter(MediaItem.media_type == MediaType.tv, MediaItem.monitored.is_(True),
                    Episode.monitored.is_(True), Episode.status.in_(MISSING))
            .order_by(MediaItem.title, Episode.season_number, Episode.episode_number).all()
        )
        out["episodes"] = [{"id": e.id, "series_id": e.series_id,
            "series_title": e.series.title if e.series else "?",
            "season_number": e.season_number, "episode_number": e.episode_number,
            "title": e.title, "air_date": e.air_date,
            "status": e.status.value if hasattr(e.status, "value") else str(e.status),
            "poster_path": e.series.poster_path if e.series else None,
            "last_searched_at": e.last_searched_at} for e in episodes]

    if mt in ("all", "music"):
        music = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.music, MediaItem.monitored.is_(True), MediaItem.status.in_(MISSING))
            .order_by(MediaItem.artist_name, MediaItem.title).all()
        )
        out["music"] = [{"id": m.id, "title": m.title, "artist_name": m.artist_name, "year": m.year,
            "status": m.status.value if hasattr(m.status, "value") else str(m.status),
            "last_searched_at": m.last_searched_at} for m in music]

    if mt in ("all", "book", "books"):
        books = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.book, MediaItem.monitored.is_(True), MediaItem.status.in_(MISSING))
            .order_by(MediaItem.title).all()
        )
        out["books"] = [{"id": b.id, "title": b.title, "year": b.year, "overview": b.overview,
            "status": b.status.value if hasattr(b.status, "value") else str(b.status),
            "poster_path": b.poster_path, "last_searched_at": b.last_searched_at} for b in books]

    if mt in ("all", "audiobook", "audiobooks"):
        abs_ = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.audiobook, MediaItem.monitored.is_(True), MediaItem.status.in_(MISSING))
            .order_by(MediaItem.title).all()
        )
        out["audiobooks"] = [{"id": a.id, "title": a.title, "year": a.year, "overview": a.overview,
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "poster_path": a.poster_path, "last_searched_at": a.last_searched_at} for a in abs_]

    out["counts"] = {
        "movies": len(out["movies"]), "episodes": len(out["episodes"]), "music": len(out["music"]),
        "books": len(out["books"]), "audiobooks": len(out["audiobooks"]),
        "total": len(out["movies"])+len(out["episodes"])+len(out["music"])+len(out["books"])+len(out["audiobooks"]),
    }
    return out


def _search_item(db: Session, item: MediaItem) -> SearchResultOut:
    try:
        if item.media_type == MediaType.movie:
            rel = find_best_movie_release(item, db=db)
        elif item.media_type == MediaType.music:
            rel = find_best_music_release(item, db=db)
        elif item.media_type == MediaType.book:
            rel = find_best_book_release(item, db=db)
        elif item.media_type == MediaType.audiobook:
            rel = find_best_audiobook_release(item, db=db)
        else:
            return SearchResultOut(found=False, error="unsupported type")
        item.last_searched_at = _utcnow()
        db.add(item)
        db.commit()
        if not rel:
            return SearchResultOut(found=False)
        grab_release(db, item, rel)
        return SearchResultOut(found=True, title=rel.get("title"), indexer=rel.get("indexer"), score=rel.get("_score"))
    except Exception as exc:
        db.rollback()
        return SearchResultOut(found=False, error=str(exc))


@router.post("/movies/{item_id}/search", response_model=SearchResultOut)
def search_movie(item_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.movie:
        raise HTTPException(404, "Not found")
    return _search_item(db, item)

@router.post("/music/{item_id}/search", response_model=SearchResultOut)
def search_music(item_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.music:
        raise HTTPException(404, "Not found")
    return _search_item(db, item)

@router.post("/books/{item_id}/search", response_model=SearchResultOut)
def search_book(item_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.book:
        raise HTTPException(404, "Not found")
    return _search_item(db, item)

@router.post("/audiobooks/{item_id}/search", response_model=SearchResultOut)
def search_audiobook(item_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.audiobook:
        raise HTTPException(404, "Not found")
    return _search_item(db, item)

@router.post("/episodes/{episode_id}/search", response_model=SearchResultOut)
def search_episode(episode_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    ep = db.get(Episode, episode_id)
    if not ep:
        raise HTTPException(404, "Not found")
    series = ep.series
    try:
        rel = find_best_episode_release(series, ep, db=db)
        ep.last_searched_at = _utcnow()
        db.add(ep)
        db.commit()
        if not rel:
            return SearchResultOut(found=False)
        grab_episode_release(db, series, ep, rel)
        return SearchResultOut(found=True, title=rel.get("title"), indexer=rel.get("indexer"), score=rel.get("_score"))
    except Exception as exc:
        db.rollback()
        return SearchResultOut(found=False, error=str(exc))


@router.post("/search-all")
def search_all(
    media_type: str | None = Query(None),
    limit: int = Query(40, ge=1, le=200),
    db: Session = Depends(get_db),
    _perm: list = Depends(require_permission("download", "library.manage"))):
    mt = (media_type or "all").lower()
    if mt in ("all", None, ""):
        return search_all_missing(db, limit=limit)

    grabs = {"movies": 0, "episodes": 0, "music": 0, "books": 0, "audiobooks": 0, "errors": []}

    def _run_items(q, finder, key):
        for item in q.limit(limit).all():
            try:
                rel = finder(item, db=db)
                item.last_searched_at = _utcnow()
                db.add(item)
                db.commit()
                if rel:
                    grab_release(db, item, rel)
                    grabs[key] += 1
            except Exception as exc:
                db.rollback()
                grabs["errors"].append(f"{key}:{item.id}:{exc}")

    if mt in ("movie", "movies"):
        _run_items(db.query(MediaItem).filter(MediaItem.media_type==MediaType.movie, MediaItem.monitored.is_(True), MediaItem.status.in_(MISSING)), find_best_movie_release, "movies")
    elif mt in ("tv", "episode", "episodes"):
        eps = (db.query(Episode).join(MediaItem).options(joinedload(Episode.series))
            .filter(MediaItem.media_type==MediaType.tv, MediaItem.monitored.is_(True), Episode.monitored.is_(True), Episode.status.in_(MISSING))
            .limit(limit).all())
        for ep in eps:
            try:
                rel = find_best_episode_release(ep.series, ep, db=db)
                ep.last_searched_at = _utcnow()
                db.add(ep); db.commit()
                if rel:
                    grab_episode_release(db, ep.series, ep, rel)
                    grabs["episodes"] += 1
            except Exception as exc:
                db.rollback()
                grabs["errors"].append(f"episodes:{ep.id}:{exc}")
    elif mt == "music":
        _run_items(db.query(MediaItem).filter(MediaItem.media_type==MediaType.music, MediaItem.monitored.is_(True), MediaItem.status.in_(MISSING)), find_best_music_release, "music")
    elif mt in ("book", "books"):
        _run_items(db.query(MediaItem).filter(MediaItem.media_type==MediaType.book, MediaItem.monitored.is_(True), MediaItem.status.in_(MISSING)), find_best_book_release, "books")
    elif mt in ("audiobook", "audiobooks"):
        _run_items(db.query(MediaItem).filter(MediaItem.media_type==MediaType.audiobook, MediaItem.monitored.is_(True), MediaItem.status.in_(MISSING)), find_best_audiobook_release, "audiobooks")
    else:
        raise HTTPException(400, "media_type must be movie|tv|music|book|audiobook|all")
    return grabs
