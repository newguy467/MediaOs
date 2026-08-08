import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Download, Episode, ItemStatus, MediaItem, MediaType
from app.services.grab import grab_episode_release, grab_release
from app.services.organize import (
    process_completed_audiobook_downloads,
    process_completed_book_downloads,
    process_completed_comic_downloads,
    process_completed_movie_downloads,
    process_completed_music_downloads,
    process_completed_tv_downloads,
)
from app.services.youtube import check_and_download_all as _check_youtube
from app.services.search import (
    find_best_book_release,
    find_best_episode_release,
    find_best_movie_release,
    find_best_music_release,
)
from app.services.upgrade import process_episode_upgrades, process_movie_upgrades
from app.services.failures import process_failed_downloads
from app.services.cleanup import run_cleanup_cycle
from app.services.smartlists import run_all_smart_lists
from app.services.podcasts import check_and_download_all as _check_podcasts
from app.services.converter import process_queue_batch as _convert_tick, watch_folder_scan as _convert_watch, within_convert_schedule

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _expire_stale_downloads(db: Session) -> int:
    """Mark old grabbed downloads as failed and reset parent status to wanted
    so the search loop can try again."""
    cutoff = _utcnow() - timedelta(hours=settings.download_timeout_hours)
    stale = (
        db.query(Download)
        .filter(
            Download.status == "grabbed",
            Download.added_at < cutoff,
        )
        .all()
    )
    count = 0
    for d in stale:
        d.status = "failed"
        db.add(d)
        count += 1

        if d.episode_id and d.episode:
            if d.episode.status == ItemStatus.downloading:
                d.episode.status = ItemStatus.wanted
                d.episode.last_searched_at = None
                db.add(d.episode)
        elif d.media_item and d.media_item.media_type in (
            MediaType.movie,
            MediaType.music,
            MediaType.book,
            MediaType.audiobook,
        ):
            if d.media_item.status == ItemStatus.downloading:
                d.media_item.status = ItemStatus.wanted
                d.media_item.last_searched_at = None
                db.add(d.media_item)

    if count:
        db.commit()
        log.info("Expired %s stale download(s) older than %sh", count, settings.download_timeout_hours)
    return count



def _search_wanted_music(db: Session) -> None:
    items = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.music,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .all()
    )
    for item in items:
        try:
            release = find_best_music_release(item, db=db)
            item.last_searched_at = _utcnow()
            db.add(item)
            db.commit()
            if not release:
                continue
            grab_release(db, item, release)
            log.info("Grabbed music %s → %s", item.title, release.get("title"))
        except Exception as exc:
            log.exception("Music search/grab failed for %s: %s", item.title, exc)
            db.rollback()


def _search_wanted_books(db: Session) -> None:
    items = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.book,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .all()
    )
    for item in items:
        try:
            release = find_best_book_release(item, db=db)
            item.last_searched_at = _utcnow()
            db.add(item)
            db.commit()
            if not release:
                continue
            grab_release(db, item, release)
            log.info("Grabbed book %s → %s", item.title, release.get("title"))
        except Exception as exc:
            log.exception("Book search/grab failed for %s: %s", item.title, exc)
            db.rollback()



def _search_wanted_audiobooks(db: Session) -> None:
    from app.services.search import find_best_audiobook_release
    items = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.audiobook,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .all()
    )
    for item in items:
        try:
            release = find_best_audiobook_release(item, db=db)
            item.last_searched_at = _utcnow()
            db.add(item)
            db.commit()
            if not release:
                continue
            grab_release(db, item, release)
            log.info("Grabbed audiobook %s → %s", item.title, release.get("title"))
        except Exception as exc:
            log.exception("Audiobook search/grab failed for %s: %s", item.title, exc)
            db.rollback()


def _search_wanted_comics(db: Session) -> None:
    """Auto-search monitored comic/manga volumes still wanted."""
    from app.services.search import find_best_comic_release, find_best_manga_release
    items = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type.in_([MediaType.comic, MediaType.manga]),
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .limit(40)
        .all()
    )
    for item in items:
        try:
            if item.media_type == MediaType.manga:
                release = find_best_manga_release(item, db=db)
            else:
                release = find_best_comic_release(item, db=db)
            item.last_searched_at = _utcnow()
            db.add(item)
            if release:
                grab_release(db, item, release)
                log.info("Comic auto-grab: %s → %s", item.title, release.get("title"))
        except Exception as exc:
            log.warning("Comic search %s: %s", item.id, exc)
    db.commit()


def _search_wanted_comic_issues(db: Session) -> None:
    """Auto-search monitored individual issues/chapters in wanted status."""
    from app.models import ComicIssue
    from app.services.search import search_comic_releases, search_manga_releases
    issues = (
        db.query(ComicIssue)
        .filter(
            ComicIssue.monitored.is_(True),
            ComicIssue.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .limit(50)
        .all()
    )
    for issue in issues:
        try:
            item = db.get(MediaItem, issue.media_item_id)
            if not item or not item.monitored:
                continue
            orig = item.title
            item.title = f"{orig} {issue.issue_number or ''} {issue.title or ''}".strip()
            try:
                if item.media_type == MediaType.manga:
                    releases = search_manga_releases(item, db=db, limit=5)
                else:
                    releases = search_comic_releases(item, db=db, limit=5)
            finally:
                item.title = orig
            if releases:
                grab_release(db, item, releases[0])
                issue.status = ItemStatus.downloading
                db.add(issue)
                log.info("Issue auto-grab: %s #%s → %s", item.title, issue.issue_number, releases[0].get("title"))
        except Exception as exc:
            log.warning("Issue search %s: %s", issue.id, exc)
    db.commit()

def _search_wanted_movies(db: Session) -> None:
    items = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.movie,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .all()
    )
    for item in items:
        try:
            release = find_best_movie_release(item, db=db)
            item.last_searched_at = _utcnow()
            db.add(item)
            db.commit()
            if not release:
                log.info("No release for movie %s (%s)", item.title, item.year)
                continue
            grab_release(db, item, release)
            log.info("Grabbed movie %s → %s", item.title, release.get("title"))
        except Exception as exc:
            log.exception("Movie search/grab failed for %s: %s", item.title, exc)
            db.rollback()


def _search_wanted_episodes(db: Session) -> None:
    """RSS-style continuous search: prioritize recently aired, then older missing."""
    from datetime import date, timedelta
    from app.config import settings as cfg

    episodes = (
        db.query(Episode)
        .join(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.tv,
            MediaItem.monitored.is_(True),
            Episode.monitored.is_(True),
            Episode.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .all()
    )
    lookback = getattr(cfg, "tv_rss_lookback_days", 14) or 14
    cutoff = (date.today() - timedelta(days=lookback)).isoformat()

    def _sort_key(ep: Episode):
        ad = ep.air_date or ""
        recent = 0 if ad >= cutoff else 1
        # never-searched first within bucket
        searched = 0 if ep.last_searched_at is None else 1
        return (recent, searched, ad or "9999", ep.season_number, ep.episode_number)

    episodes = sorted(episodes, key=_sort_key)
    for ep in episodes:
        try:
            series = ep.series
            release = find_best_episode_release(series, ep, db=db)
            ep.last_searched_at = _utcnow()
            db.add(ep)
            db.commit()
            if not release:
                log.info(
                    "No release for %s S%02dE%02d",
                    series.title,
                    ep.season_number,
                    ep.episode_number,
                )
                continue
            grab_episode_release(db, series, ep, release)
            log.info(
                "Grabbed %s S%02dE%02d → %s",
                series.title,
                ep.season_number,
                ep.episode_number,
                release.get("title"),
            )
        except Exception as exc:
            log.exception(
                "Episode search/grab failed for id=%s: %s", ep.id, exc
            )
            db.rollback()


def run_youtube_cycle() -> None:
    db = SessionLocal()
    try:
        result = _check_youtube(db)
        if result["checked"]:
            log.info("YouTube check: %s channels, %s downloads, %s errors", result["checked"], result["downloaded"], len(result["errors"]))
    except Exception as exc:
        log.exception("YouTube cycle failed: %s", exc)
    finally:
        db.close()


def run_podcast_cycle() -> None:
    db = SessionLocal()
    try:
        result = _check_podcasts(db)
        if result["checked"]:
            log.info(
                "Podcast check: %s feeds, %s new downloads, %s errors",
                result["checked"],
                result["downloaded"],
                len(result["errors"]),
            )
    except Exception as exc:
        log.exception("Podcast cycle failed: %s", exc)
    finally:
        db.close()


def run_cycle() -> None:
    db = SessionLocal()
    try:
        _expire_stale_downloads(db)
        process_failed_downloads(db)
        process_completed_movie_downloads(db)
        process_completed_tv_downloads(db)
        process_completed_music_downloads(db)
        process_completed_book_downloads(db)
        process_completed_audiobook_downloads(db)
        process_completed_comic_downloads(db)
        _search_wanted_movies(db)
        _search_wanted_episodes(db)
        _search_wanted_music(db)
        _search_wanted_books(db)
        _search_wanted_audiobooks(db)
        _search_wanted_comics(db)
        _search_wanted_comic_issues(db)
        process_movie_upgrades(db)
        process_episode_upgrades(db)
        try:
            run_all_smart_lists(db)
        except Exception as exc:
            log.exception("Smart lists: %s", exc)
    except Exception as exc:
        log.exception("Scheduler cycle failed: %s", exc)
    finally:
        db.close()



def run_cleanuparr_cycle() -> None:
    """Cleanuparr-inspired queue + orphan cleaner."""
    db = SessionLocal()
    try:
        result = run_cleanup_cycle(db)
        q = result.get("queue") or {}
        o = result.get("orphans") or {}
        if q.get("struck") or o.get("orphans"):
            log.info(
                "Cleanup: struck=%s removed=%s orphans=%s",
                q.get("struck"),
                q.get("removed"),
                o.get("orphans"),
            )
    except Exception as exc:
        log.warning("Cleanup cycle: %s", exc)
    finally:
        db.close()


def run_queue_sse_tick() -> None:
    """Push live queue progress over SSE for UI progress bars."""
    try:
        from app.database import SessionLocal
        from app.routers.queue import get_queue
        db = SessionLocal()
        try:
            get_queue(db)  # publishes via sse inside
        finally:
            db.close()
    except Exception as exc:
        log.debug("queue sse tick: %s", exc)



def run_definition_sync(*, priority_only: bool = False) -> None:
    """Pull Jackett Cardigann YAML definitions (auto, for all users)."""
    try:
        from app.config import settings
        if not getattr(settings, "cardigann_auto_sync", True):
            return
        from app.services.definition_sync import sync_definitions, ensure_seed_definitions
        if priority_only:
            ensure_seed_definitions()
        else:
            max_files = int(getattr(settings, "cardigann_sync_max_files", 0) or 0) or None
            sync_definitions(max_files=max_files, force=False)
    except Exception as exc:
        log.warning("definition sync: %s", exc)



def run_series_status_backfill() -> None:
    """Quietly fill missing TV series_status from TVDb (continuing/ended)."""
    try:
        from app.database import SessionLocal
        from app.models import MediaItem, MediaType
        from app.clients.tvdb import tvdb_client
        db = SessionLocal()
        try:
            rows = (
                db.query(MediaItem)
                .filter(
                    MediaItem.media_type == MediaType.tv,
                    MediaItem.series_status.is_(None),
                )
                .limit(40)
                .all()
            )
            n = 0
            for item in rows:
                try:
                    details = tvdb_client.get_series(int(item.external_id))
                    stv = details.get("series_status")
                    if stv:
                        item.series_status = stv
                        db.add(item)
                        n += 1
                except Exception:
                    continue
            if n:
                db.commit()
                log.info("series_status backfill: updated %s", n)
        finally:
            db.close()
    except Exception as exc:
        log.debug("series_status backfill: %s", exc)

def run_jackett_sync() -> None:
    from app.config import settings
    if not getattr(settings, "jackett_url", None):
        return
    try:
        from app.database import SessionLocal
        from app.services.jackett_sync import sync_jackett_indexers
        db = SessionLocal()
        try:
            sync_jackett_indexers(db, enable_new=True)
        finally:
            db.close()
    except Exception as exc:
        log.debug("jackett sync: %s", exp if False else exc)




def run_comic_pull_sync() -> None:
    try:
        from app.services.comic_pull_sync import run_pull_list_sync
        result = run_pull_list_sync()
        log.info("Comic pull-list sync: %s", result)
    except Exception as exc:
        log.exception("Comic pull-list sync failed: %s", exc)


def run_trash_guide_sync() -> None:
    try:
        from app.services.trash_guide_fetch import fetch_and_apply
        result = fetch_and_apply()
        log.info("TRaSH guide sync: %s", result)
    except Exception as exc:
        log.exception("TRaSH guide sync failed: %s", exc)


def run_iptv_org_resync() -> None:
    db = SessionLocal()
    try:
        from app.services.livetv_defaults import resync_iptv_org_sources, seed_if_empty
        seeded = seed_if_empty(db)
        if seeded:
            log.info("LiveTV iptv-org seed: %s", seeded)
        result = resync_iptv_org_sources(db)
        log.info("LiveTV iptv-org resync: %s", result)
    except Exception as exc:
        log.exception("iptv-org resync failed: %s", exc)
    finally:
        db.close()


def run_livetv_epg_sync() -> None:
    db = SessionLocal()
    try:
        from app.services.livetv import fetch_and_index_epg
        result = fetch_and_index_epg(db)
        log.info("LiveTV EPG sync: %s", result)
    except Exception as exc:
        log.exception("LiveTV EPG sync failed: %s", exc)
    finally:
        db.close()



def run_hunt_cycle_job() -> None:
    """Aggressive missing/upgrade hunt (Huntarr-inspired)."""
    try:
        from app.services.hunt import run_hunt_cycle
        limit = int(getattr(settings, "hunt_batch_limit", 25) or 25)
        result = run_hunt_cycle(limit=limit)
        if result.get("processed"):
            log.info("Hunt: planned=%s processed=%s grabbed=%s",
                     result.get("planned"), result.get("processed"), result.get("grabbed"))
    except Exception as exc:
        log.warning("Hunt cycle: %s", exc)


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    minutes = max(1, int(settings.search_interval_minutes))
    scheduler.add_job(
        run_cycle,
        "interval",
        minutes=minutes,
        id="mediaos_cycle",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    # Run once shortly after startup so first adds don't wait a full interval
    scheduler.add_job(
        run_cycle,
        "date",
        run_date=_utcnow() + timedelta(seconds=15),
        id="mediaos_startup_cycle",
        replace_existing=True,
    )

    podcast_minutes = max(5, int(settings.podcast_check_interval_minutes))
    scheduler.add_job(
        run_podcast_cycle,
        "interval",
        minutes=podcast_minutes,
        id="mediaos_podcast_cycle",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_podcast_cycle,
        "date",
        run_date=_utcnow() + timedelta(seconds=25),
        id="mediaos_podcast_startup_cycle",
        replace_existing=True,
    )
    yt_minutes = max(15, int(getattr(settings, "youtube_check_interval_minutes", 60) or 60))
    cleanup_min = max(2, int(getattr(settings, "cleanup_interval_minutes", 5) or 5))
    scheduler.add_job(run_definition_sync, "interval", days=7, id="mediaos_def_sync", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(lambda: run_definition_sync(priority_only=True), "date", run_date=_utcnow() + timedelta(seconds=20), id="mediaos_def_sync_startup", replace_existing=True)
    scheduler.add_job(run_jackett_sync, "date", run_date=_utcnow() + timedelta(seconds=35), id="mediaos_jackett_sync_startup", replace_existing=True)
    scheduler.add_job(run_series_status_backfill, "interval", hours=12, id="mediaos_series_status", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_series_status_backfill, "date", run_date=_utcnow() + timedelta(seconds=90), id="mediaos_series_status_startup", replace_existing=True)
    scheduler.add_job(run_jackett_sync, "interval", hours=6, id="mediaos_jackett_sync", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_queue_sse_tick, "interval", seconds=5, id="mediaos_queue_sse", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_cleanuparr_cycle, "interval", minutes=cleanup_min, id="mediaos_cleanup_cycle", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_cleanuparr_cycle, "date", run_date=_utcnow() + timedelta(seconds=70), id="mediaos_cleanup_startup", replace_existing=True)
    scheduler.add_job(run_convert_cycle, "interval", seconds=45, id="mediaos_convert_cycle", replace_existing=True, max_instances=1, coalesce=True)
    watch_min = max(5, int(getattr(settings, "converter_watch_interval_minutes", 15) or 15))
    scheduler.add_job(run_convert_watch_cycle, "interval", minutes=watch_min, id="mediaos_convert_watch", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_convert_watch_cycle, "date", run_date=_utcnow() + __import__("datetime").timedelta(seconds=90), id="mediaos_convert_watch_startup", replace_existing=True)
    scheduler.add_job(run_youtube_cycle, "interval", minutes=yt_minutes, id="mediaos_youtube_cycle", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_youtube_cycle, "date", run_date=_utcnow() + timedelta(seconds=40), id="mediaos_youtube_startup_cycle", replace_existing=True)

    pull_h = max(1, int(getattr(settings, "comic_pull_sync_hours", 12) or 12))
    trash_h = max(1, int(getattr(settings, "trash_guide_sync_hours", 168) or 168))
    epg_h = max(1, int(getattr(settings, "livetv_epg_sync_hours", 6) or 6))
    scheduler.add_job(run_comic_pull_sync, "interval", hours=pull_h, id="mediaos_comic_pull", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_comic_pull_sync, "date", run_date=_utcnow() + timedelta(seconds=120), id="mediaos_comic_pull_startup", replace_existing=True)
    scheduler.add_job(run_trash_guide_sync, "interval", hours=trash_h, id="mediaos_trash_guide", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_trash_guide_sync, "date", run_date=_utcnow() + timedelta(seconds=150), id="mediaos_trash_guide_startup", replace_existing=True)
    iptv_h = max(1, int(getattr(settings, "livetv_iptv_org_sync_hours", 24) or 24))
    scheduler.add_job(run_iptv_org_resync, "interval", hours=iptv_h, id="mediaos_iptv_org", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_iptv_org_resync, "date", run_date=_utcnow() + timedelta(seconds=80), id="mediaos_iptv_org_startup", replace_existing=True)
    scheduler.add_job(run_livetv_epg_sync, "interval", hours=epg_h, id="mediaos_livetv_epg", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_livetv_epg_sync, "date", run_date=_utcnow() + timedelta(seconds=100), id="mediaos_livetv_epg_startup", replace_existing=True)
    # Hunt engine — missing / failed items
    hunt_min = max(15, int(getattr(settings, "hunt_interval_minutes", 60) or 60))
    scheduler.add_job(run_hunt_cycle_job, "interval", minutes=hunt_min, id="mediaos_hunt", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(run_hunt_cycle_job, "date", run_date=_utcnow() + timedelta(seconds=180), id="mediaos_hunt_startup", replace_existing=True)

    scheduler.start()
    log.info("Scheduler started (every %s min, podcasts every %s min)", minutes, podcast_minutes)
    return scheduler


def run_convert_cycle() -> None:
    """Tdarr-style converter worker tick (parallel + schedule window)."""
    db = SessionLocal()
    try:
        if not within_convert_schedule():
            return
        results = _convert_tick(db)
        for result in results or []:
            if result and not result.get("idle") and not result.get("busy") and not result.get("paused"):
                log.info("Converter: %s", result)
    except Exception as exc:
        log.warning("Converter cycle: %s", exc)
    finally:
        db.close()


def run_convert_watch_cycle() -> None:
    """Watch-folder auto-queue for converter."""
    db = SessionLocal()
    try:
        result = _convert_watch(db)
        if result.get("enabled") and result.get("queued"):
            log.info("Converter watch: queued %s from %s", result.get("queued"), result.get("folders"))
    except Exception as exc:
        log.warning("Converter watch: %s", exc)
    finally:
        db.close()
