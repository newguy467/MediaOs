"""
Upgrade-on-better: for monitored items that are already downloaded, search
again and grab if a release scores significantly higher than the on-disk copy.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Episode, ItemStatus, MediaItem, MediaType
from app.services.activity import log_activity
from app.services.grab import grab_episode_release, grab_release
from app.services.search import find_best_episode_release, find_best_movie_release
from app.services.quality.parser import parse_release_title
from app.services.quality.profiles import is_resolution_downgrade

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _should_search(last: datetime | None) -> bool:
    if last is None:
        return True
    # normalize naive
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    gap = timedelta(hours=settings.upgrade_search_interval_hours)
    return _utcnow() - last >= gap


def _is_upgrade(current_score: int | None, new_score: int | None) -> bool:
    if new_score is None:
        return False
    if current_score is None:
        # Have a file but no recorded score — only upgrade if new is solid
        return new_score >= 200 + settings.upgrade_min_score_gap
    return new_score >= current_score + settings.upgrade_min_score_gap


def process_movie_upgrades(db: Session) -> int:
    if not settings.upgrade_enabled:
        return 0

    items = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.movie,
            MediaItem.monitored.is_(True),
            MediaItem.status == ItemStatus.downloaded,
            MediaItem.file_path.isnot(None),
        )
        .all()
    )

    upgraded = 0
    for item in items:
        if not _should_search(item.last_searched_at):
            continue
        try:
            release = find_best_movie_release(item, db=db)
            item.last_searched_at = _utcnow()
            db.add(item)
            db.commit()

            if not release:
                continue
            new_score = release.get("_score")
            if not _is_upgrade(item.quality_score, new_score):
                log.debug(
                    "No upgrade for %s (have %s, best %s)",
                    item.title,
                    item.quality_score,
                    new_score,
                )
                continue

            if getattr(settings, "upgrade_prevent_resolution_downgrade", True):
                try:
                    from pathlib import Path as _P
                    cur_parsed = parse_release_title(_P(item.file_path).name if item.file_path else "")
                    new_parsed = parse_release_title(release.get("title") or "")
                    if is_resolution_downgrade(cur_parsed.resolution, new_parsed.resolution):
                        log.info(
                            "Skip upgrade %s: resolution downgrade %s → %s",
                            item.title, cur_parsed.resolution, new_parsed.resolution,
                        )
                        continue
                except Exception:
                    pass

            # Grab better release; status → downloading; old file left until
            # organize overwrites / user cleans (safe default).
            grab_release(db, item, release)
            log_activity(
                db,
                "upgrade",
                f"Upgrade movie {item.title}: score {item.quality_score} → {new_score} ({release.get('title')})",
                media_type="movie",
                media_item_id=item.id,
                release_title=release.get("title"),
            )
            log.info(
                "Upgrade grabbed for %s: %s → %s",
                item.title,
                item.quality_score,
                new_score,
            )
            upgraded += 1
        except Exception as exc:
            log.exception("Upgrade failed for movie %s: %s", item.title, exc)
            db.rollback()

    return upgraded


def process_episode_upgrades(db: Session) -> int:
    if not settings.upgrade_enabled:
        return 0

    episodes = (
        db.query(Episode)
        .join(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.tv,
            MediaItem.monitored.is_(True),
            Episode.monitored.is_(True),
            Episode.status == ItemStatus.downloaded,
            Episode.file_path.isnot(None),
        )
        .all()
    )

    upgraded = 0
    for ep in episodes:
        if not _should_search(ep.last_searched_at):
            continue
        series = ep.series
        try:
            release = find_best_episode_release(series, ep, db=db)
            ep.last_searched_at = _utcnow()
            db.add(ep)
            db.commit()

            if not release:
                continue
            new_score = release.get("_score")
            if not _is_upgrade(ep.quality_score, new_score):
                continue

            grab_episode_release(db, series, ep, release)
            log_activity(
                db,
                "upgrade",
                f"Upgrade {series.title} S{ep.season_number:02d}E{ep.episode_number:02d}: "
                f"{ep.quality_score} → {new_score}",
                media_type="tv",
                media_item_id=series.id,
                release_title=release.get("title"),
            )
            upgraded += 1
        except Exception as exc:
            log.exception("Upgrade failed for episode %s: %s", ep.id, exc)
            db.rollback()

    return upgraded
