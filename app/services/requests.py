"""Native request system — users request, an admin approves, mediaos adds
it to the library and kicks off the first search itself.

This is the piece that lets mediaos fully replace Overseerr/Jellyseerr:
no second app, no second database, one approval queue.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import MediaItem, MediaRequest, MediaType, RequestStatus

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def approve_request(db: Session, req: MediaRequest, *, resolved_by: str | None, quality_profile: str | None = None) -> MediaItem:
    """Add the requested title to the library using the same add-paths the
    UI itself uses, then kick off an immediate search."""
    if req.status != RequestStatus.pending.value:
        raise HTTPException(400, f"Request already {req.status}")

    item: MediaItem | None = None

    if req.media_type == "movie":
        from app.routers.movies import add_movie
        from app.schemas import MovieCreate

        existing = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.movie, MediaItem.external_id == req.external_id)
            .first()
        )
        if existing:
            item = existing
        else:
            item = add_movie(MovieCreate(external_id=req.external_id, monitored=True, quality_profile=quality_profile), db)
        from app.services.search import find_best_movie_release
        from app.services.grab import grab_release
        release = find_best_movie_release(item, db=db)
        if release:
            grab_release(db, item, release)

    elif req.media_type == "tv":
        from app.routers.tv import add_series
        from app.schemas import SeriesCreate

        existing = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.tv, MediaItem.external_id == req.external_id)
            .first()
        )
        if existing:
            item = existing
        else:
            add_series(
                SeriesCreate(
                    external_id=req.external_id,
                    monitored=True,
                    quality_profile=quality_profile,
                    monitor="all",
                    search_missing=True,
                ),
                db,
            )
            item = (
                db.query(MediaItem)
                .filter(MediaItem.media_type == MediaType.tv, MediaItem.external_id == req.external_id)
                .first()
            )

    elif req.media_type == "music":
        from app.routers.music import add_album, MusicCreate

        existing = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.music, MediaItem.external_id == req.external_id)
            .first()
        )
        item = existing or add_album(
            MusicCreate(
                external_id=req.external_id,
                title=req.title,
                artist=req.artist_name,
                year=req.year,
                monitored=True,
                quality_profile=quality_profile,
                search_now=True,
            ),
            db,
        )

    elif req.media_type == "book":
        from app.routers.books import add_book, BookCreate

        existing = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.book, MediaItem.external_id == req.external_id)
            .first()
        )
        item = existing or add_book(
            BookCreate(
                external_id=req.external_id,
                title=req.title,
                year=req.year,
                overview=req.overview,
                poster_path=req.poster_path,
            ),
            db,
        )
        from app.services.search import find_best_book_release
        from app.services.grab import grab_release
        release = find_best_book_release(item, db=db)
        if release:
            grab_release(db, item, release)

    elif req.media_type == "audiobook":
        from app.routers.audiobooks import add_audiobook, AudiobookCreate

        existing = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.audiobook, MediaItem.external_id == req.external_id)
            .first()
        )
        item = existing or add_audiobook(
            AudiobookCreate(
                external_id=req.external_id,
                title=req.title,
                year=req.year,
                overview=req.overview,
                poster_path=req.poster_path,
            ),
            db,
        )
        from app.services.search import find_best_audiobook_release
        from app.services.grab import grab_release
        release = find_best_audiobook_release(item, db=db)
        if release:
            grab_release(db, item, release)

    else:
        raise HTTPException(400, f"Unsupported media_type: {req.media_type}")

    req.status = RequestStatus.fulfilled.value
    req.resolved_by = resolved_by
    req.resolved_at = _utcnow()
    req.media_item_id = item.id if item else None
    db.add(req)
    db.commit()
    return item


def deny_request(db: Session, req: MediaRequest, *, resolved_by: str | None, reason: str | None) -> MediaRequest:
    if req.status != RequestStatus.pending.value:
        raise HTTPException(400, f"Request already {req.status}")
    req.status = RequestStatus.denied.value
    req.resolved_by = resolved_by
    req.resolution_note = reason
    req.resolved_at = _utcnow()
    db.add(req)
    db.commit()
    db.refresh(req)
    return req
