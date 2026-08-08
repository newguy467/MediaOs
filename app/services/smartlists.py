"""Run smart lists: TMDb / Trakt / IMDb → add missing as wanted (first-class)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.clients.imdb import imdb_client
from app.clients.tmdb import tmdb_client
from app.clients.trakt import trakt_client
from app.models import ItemStatus, MediaItem, MediaType, SmartList
from app.services.activity import log_activity

log = logging.getLogger(__name__)

SUPPORTED_SOURCES = (
    "tmdb_list",
    "tmdb_discover",
    "trakt_list",
    "trakt_trending",
    "trakt_popular",
    "imdb_list",
    "imdb_chart",
)


def _passes_filters(row: dict, sl: SmartList) -> bool:
    year = row.get("year")
    vote = row.get("vote_average")
    if sl.min_year is not None and year is not None and year < sl.min_year:
        return False
    if sl.max_year is not None and year is not None and year > sl.max_year:
        return False
    if sl.min_vote_average is not None and vote is not None and float(vote) < float(sl.min_vote_average):
        return False
    return True


def _add_movie(db: Session, row: dict, sl: SmartList) -> bool:
    ext = row.get("external_id") or row.get("tmdb_id")
    if ext is None:
        return False
    existing = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.movie, MediaItem.external_id == str(ext))
        .first()
    )
    if existing:
        return False
    item = MediaItem(
        media_type=MediaType.movie,
        external_id=str(ext),
        external_source="tmdb",
        title=row.get("title") or "Unknown",
        year=row.get("year"),
        overview=row.get("overview"),
        poster_path=row.get("poster_path"),
        monitored=sl.monitored,
        status=ItemStatus.wanted,
        quality_profile=sl.quality_profile,
    )
    db.add(item)
    return True


def _fetch_rows(sl: SmartList) -> list[dict]:
    src = (sl.source or "").lower()
    ref = (sl.source_ref or "").strip()

    if src == "tmdb_list":
        return tmdb_client.get_list(int(ref))

    if src == "tmdb_discover":
        year = sl.min_year
        return tmdb_client.discover_movies_filtered(
            year_gte=sl.min_year,
            year_lte=sl.max_year,
            vote_average_gte=sl.min_vote_average,
            primary_release_year=year
            if sl.min_year and sl.max_year and sl.min_year == sl.max_year
            else None,
        )

    if src == "trakt_list":
        # source_ref: "username/list-slug-or-id"
        if "/" not in ref:
            raise ValueError("trakt_list source_ref must be username/list-id")
        username, list_id = ref.split("/", 1)
        rows = trakt_client.list_items(username.strip(), list_id.strip())
        return [r for r in rows if (r.get("media_type") or "movie") == "movie"]

    if src == "trakt_trending":
        return trakt_client.trending_movies(limit=int(ref) if ref.isdigit() else 50)

    if src == "trakt_popular":
        return trakt_client.popular_movies(limit=int(ref) if ref.isdigit() else 50)

    if src == "imdb_list":
        rows = imdb_client.list_items(ref)
        return imdb_client.enrich_with_tmdb(rows)

    if src == "imdb_chart":
        chart = ref or "top"
        rows = imdb_client.chart(chart)
        return imdb_client.enrich_with_tmdb(rows)

    raise ValueError(f"Unknown smart list source {sl.source}")


def run_smart_list(db: Session, sl: SmartList) -> int:
    if not sl.enabled:
        return 0
    added = 0
    try:
        rows = _fetch_rows(sl)
    except Exception as exc:
        log.exception("Smart list %s fetch failed: %s", sl.name, exc)
        return 0

    for row in rows:
        if sl.media_type == "movie" and row.get("media_type") not in (None, "movie"):
            continue
        if not _passes_filters(row, sl):
            continue
        # Ensure external_id for TMDb-based add
        if not row.get("external_id") and row.get("tmdb_id"):
            row["external_id"] = row["tmdb_id"]
        try:
            if sl.media_type == "movie" and _add_movie(db, row, sl):
                added += 1
        except Exception as exc:
            log.debug("Skip row: %s", exc)
            db.rollback()

    if added:
        db.commit()
        log_activity(
            db,
            "smartlist",
            f"Smart list '{sl.name}' added {added} item(s)",
            media_type=sl.media_type,
        )
    sl.last_run_at = datetime.now(timezone.utc)
    sl.last_added_count = added
    db.add(sl)
    db.commit()
    return added


def run_all_smart_lists(db: Session) -> dict:
    total = 0
    lists = db.query(SmartList).filter(SmartList.enabled.is_(True)).all()
    for sl in lists:
        try:
            total += run_smart_list(db, sl)
        except Exception as exc:
            log.exception("Smart list %s failed: %s", sl.name, exc)
            db.rollback()
    return {"lists": len(lists), "added": total}
