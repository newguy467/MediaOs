"""Global wanted / missing search (Sonarr 'search all' style)."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import Episode, ItemStatus, MediaItem, MediaType
from app.services.grab import grab_episode_release, grab_release
from app.services.search import (
    find_best_audiobook_release,
    find_best_book_release,
    find_best_episode_release,
    find_best_movie_release,
    find_best_music_release,
)

log = logging.getLogger(__name__)


def search_all_missing(db: Session, *, limit: int = 40) -> dict:
    grabs = {"movies": 0, "episodes": 0, "music": 0, "books": 0, "audiobooks": 0}

    movies = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.movie,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .limit(limit)
        .all()
    )
    for item in movies:
        try:
            rel = find_best_movie_release(item, db=db)
            if rel:
                grab_release(db, item, rel)
                grabs["movies"] += 1
        except Exception as exc:
            log.exception("search movie %s: %s", item.title, exc)
            db.rollback()

    episodes = (
        db.query(Episode)
        .join(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.tv,
            MediaItem.monitored.is_(True),
            Episode.monitored.is_(True),
            Episode.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .limit(limit)
        .all()
    )
    for ep in episodes:
        try:
            rel = find_best_episode_release(ep.series, ep, db=db)
            if rel:
                grab_episode_release(db, ep.series, ep, rel)
                grabs["episodes"] += 1
        except Exception as exc:
            log.exception("search ep %s: %s", ep.id, exc)
            db.rollback()

    albums = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.music,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .limit(limit)
        .all()
    )
    for item in albums:
        try:
            rel = find_best_music_release(item, db=db)
            if rel:
                grab_release(db, item, rel)
                grabs["music"] += 1
        except Exception as exc:
            log.exception("search music %s: %s", item.title, exc)
            db.rollback()

    books = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.book,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .limit(limit)
        .all()
    )
    for item in books:
        try:
            rel = find_best_book_release(item, db=db)
            if rel:
                grab_release(db, item, rel)
                grabs["books"] += 1
        except Exception as exc:
            log.exception("search book %s: %s", item.title, exc)
            db.rollback()


    audiobooks = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.audiobook,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .limit(limit)
        .all()
    )
    for item in audiobooks:
        try:
            rel = find_best_audiobook_release(item, db=db)
            if rel:
                grab_release(db, item, rel)
                grabs["audiobooks"] += 1
        except Exception as exc:
            log.exception("search audiobook %s: %s", item.title, exc)
            db.rollback()

    return grabs


def episode_search_query(series_title: str, season: int, episode: int, *, absolute: int | None = None, series_type: str | None = None) -> str:
    """Build release search string; anime prefers absolute numbering when set."""
    if (series_type or "").lower() == "anime" and absolute:
        return f"{series_title} {absolute:02d}"
    if (series_type or "").lower() == "anime" and season == 1 and episode:
        # common anime absolute = episode when single-season style
        return f"{series_title} {episode:02d}"
    return f"{series_title} S{season:02d}E{episode:02d}"
