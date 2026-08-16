"""Dashboard widgets — Prismarr-inspired calendar/activity/queue summary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import ItemStatus, Activity, Download, Episode, MediaItem, MediaType


def widget_activity(db: Session, limit: int = 20) -> list[dict]:
    rows = db.query(Activity).order_by(Activity.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "event": r.event,
            "message": getattr(r, "message", None) or getattr(r, "title", None),
            "media_type": r.media_type,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def widget_queue(db: Session, limit: int = 20) -> list[dict]:
    rows = db.query(Download).order_by(Download.id.desc()).limit(limit * 2).all()
    out = []
    for r in rows:
        st = r.status.value if hasattr(r.status, "value") else str(r.status or "")
        if st in ("completed", "failed", "removed"):
            continue
        mt = getattr(r, "media_type", None)
        if not mt and getattr(r, "game_id", None):
            mt = "game"
        out.append({
            "id": r.id,
            "title": getattr(r, "release_title", None) or getattr(r, "title", None),
            "status": st,
            "progress": getattr(r, "progress", None),
            "media_type": mt,
            "game_id": getattr(r, "game_id", None),
            "media_item_id": getattr(r, "media_item_id", None),
        })
        if len(out) >= limit:
            break
    return out


def widget_calendar(db: Session, days: int = 14) -> list[dict]:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    # Episodes with air dates in range if column exists
    eps = db.query(Episode).limit(500).all()
    items = []
    for e in eps:
        air = getattr(e, "air_date", None) or getattr(e, "air_date_utc", None)
        if not air:
            continue
        if isinstance(air, str):
            try:
                air_dt = datetime.fromisoformat(air.replace("Z", "+00:00"))
            except Exception:
                continue
        else:
            air_dt = air
        if air_dt.tzinfo is None:
            air_dt = air_dt.replace(tzinfo=timezone.utc)
        if now - timedelta(days=1) <= air_dt <= end:
            series = e.series
            items.append({
                "type": "episode",
                "series": series.title if series else None,
                "season": e.season_number,
                "episode": e.episode_number,
                "title": e.title,
                "air_date": air_dt.isoformat(),
                "status": str(e.status.value if hasattr(e.status, "value") else e.status),
            })
    items.sort(key=lambda x: x.get("air_date") or "")
    return items[:100]


def widget_wanted_counts(db: Session) -> dict[str, int]:
    from app.models import ItemStatus
    counts = {}
    for mt in (MediaType.movie, MediaType.tv, MediaType.music, MediaType.book, MediaType.audiobook, MediaType.comic, MediaType.adult):
        try:
            n = (
                db.query(MediaItem)
                .filter(
                    MediaItem.media_type == mt,
                    MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
                )
                .count()
            )
            counts[mt.value if hasattr(mt, "value") else str(mt)] = n
        except Exception:
            counts[str(mt)] = 0
    return counts




def widget_library_counts(db: Session) -> dict[str, int]:
    out = {}
    for mt in MediaType:
        try:
            out[mt.value if hasattr(mt, "value") else str(mt)] = (
                db.query(MediaItem).filter(MediaItem.media_type == mt).count()
            )
        except Exception:
            out[str(mt)] = 0
    return out


def widget_health() -> dict[str, Any]:
    from app.version import get_version
    return {
        "version": get_version(),
        "status": "ok",
    }


def widget_recent_downloads(db: Session, limit: int = 12) -> list[dict]:
    rows = (
        db.query(MediaItem)
        .filter(MediaItem.status == ItemStatus.downloaded)
        .order_by(MediaItem.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "year": r.year,
            "media_type": r.media_type.value if hasattr(r.media_type, "value") else str(r.media_type),
            "poster_path": r.poster_path,
            "file_path": r.file_path,
        }
        for r in rows
    ]


DEFAULT_WIDGET_LAYOUT = [
    {"id": "stats", "enabled": True},
    {"id": "calendar", "enabled": True},
    {"id": "queue", "enabled": True},
    {"id": "wanted", "enabled": True},
    {"id": "activity", "enabled": True},
    {"id": "recent", "enabled": True},
    {"id": "health", "enabled": True},
]


def widget_dvr_jobs(db: Session, limit: int = 15) -> list[dict]:
    """Upcoming / active Live TV DVR recordings for dashboard control plane."""
    try:
        from app.models import LiveTvRecording
        rows = (
            db.query(LiveTvRecording)
            .filter(LiveTvRecording.status.in_(["scheduled", "recording"]))
            .order_by(LiveTvRecording.starts_at.asc().nullslast())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "title": r.title,
                "channel_name": getattr(r, "channel_name", None),
                "status": r.status,
                "starts_at": r.starts_at.isoformat() if r.starts_at else None,
                "ends_at": r.ends_at.isoformat() if r.ends_at else None,
            }
            for r in rows
        ]
    except Exception:
        return []




def widget_external_arr(db: Session) -> list[dict]:
    """Live status of configured external *arr instances (Sonarr/Radarr/etc)."""
    from app.services import app_settings as aset
    out = []
    try:
        overrides = {}
        try:
            overrides = aset.get_all_overrides(db) if hasattr(aset, "get_all_overrides") else {}
        except Exception:
            pass
        from app.config import settings
        pairs = [
            ("sonarr", getattr(settings, "sonarr_url", None) or overrides.get("sonarr_url"), getattr(settings, "sonarr_api_key", None) or overrides.get("sonarr_api_key")),
            ("radarr", getattr(settings, "radarr_url", None) or overrides.get("radarr_url"), getattr(settings, "radarr_api_key", None) or overrides.get("radarr_api_key")),
            ("lidarr", getattr(settings, "lidarr_url", None) or overrides.get("lidarr_url"), getattr(settings, "lidarr_api_key", None) or overrides.get("lidarr_api_key")),
            ("prowlarr", getattr(settings, "prowlarr_url", None) or overrides.get("prowlarr_url"), getattr(settings, "prowlarr_api_key", None) or overrides.get("prowlarr_api_key")),
        ]
        import httpx
        for name, url, key in pairs:
            if not url or not str(url).strip():
                continue
            status = "unknown"
            version = None
            try:
                base = str(url).rstrip("/")
                headers = {"X-Api-Key": key} if key else {}
                with httpx.Client(timeout=3.0) as client:
                    r = client.get(f"{base}/api/v3/system/status", headers=headers)
                    if r.status_code == 200:
                        status = "up"
                        version = (r.json() or {}).get("version")
                    else:
                        status = f"http_{r.status_code}"
            except Exception as e:
                status = "down"
                version = str(e)[:80]
            out.append({"name": name, "url": url, "status": status, "version": version})
    except Exception:
        pass
    return out

def dashboard_bundle(db: Session) -> dict[str, Any]:
    return {
        "activity": widget_activity(db),
        "queue": widget_queue(db),
        "calendar": widget_calendar(db),
        "wanted": widget_wanted_counts(db),
        "library": widget_library_counts(db),
        "recent": widget_recent_downloads(db),
        "health": widget_health(),
        # MediaOS v2 control plane
        "continue_watching": widget_continue_watching(db),
        "continue_reading": widget_continue_reading(db),
        "recent_scrobbles": widget_recent_scrobbles(db),
        "games_wanted": widget_games_wanted(db),
        "tracking_summary": widget_tracking_summary(db),
        "dvr_jobs": widget_dvr_jobs(db),
        "external_arr": widget_external_arr(db),
        "layout_default": DEFAULT_WIDGET_LAYOUT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# --- MediaOS v2 expansions (Prismarr density + scrob + games) ---

# Media type -> (page slug, label). Shared shape with app/routers/global_search.py's
# MODULE_MAP; kept as a separate literal here (dashboard_widgets must not import
# routers) but the two must be updated together if a module is added.
CONTINUE_PAGE_MAP = {
    "movie": "movies",
    "tv": "tv",
    "music": "music",
    "book": "books",
    "audiobook": "audiobooks",
    "comic": "comics",
    "manga": "manga",
    "adult": "adult",
}


def widget_continue_watching(db: Session, limit: int = 12) -> list[dict]:
    """Continue Watching / Playing from local scrobbling progress, enriched
    with title/artwork/media-type so the dashboard can render real cards
    instead of a bare id."""
    from app.models import WatchProgress, Game

    rows = (
        db.query(WatchProgress)
        .filter(WatchProgress.progress_percent > 0, WatchProgress.progress_percent < 90)
        .order_by(WatchProgress.last_watched_at.desc())
        .limit(limit * 2)  # over-fetch: some rows may be orphaned (item deleted)
        .all()
    )
    out: list[dict] = []
    for p in rows:
        title = subtitle = poster = media_type = page = None
        if p.media_item_id:
            item = db.get(MediaItem, p.media_item_id)
            if item:
                title = item.title
                media_type = item.media_type.value if hasattr(item.media_type, "value") else str(item.media_type)
                poster = item.poster_path
                subtitle = item.artist_name if media_type == "music" else (str(item.year) if item.year else None)
                page = CONTINUE_PAGE_MAP.get(media_type)
        elif p.game_id:
            g = db.get(Game, p.game_id)
            if g:
                title, media_type, poster, page = g.title, "game", g.poster_path, "games"
        if not title:
            continue  # orphaned progress row — underlying item was deleted
        out.append({
            "media_item_id": p.media_item_id,
            "game_id": p.game_id,
            "title": title,
            "subtitle": subtitle,
            "media_type": media_type,
            "poster_path": poster,
            "page": page,
            "progress_percent": p.progress_percent,
            "last_watched_at": p.last_watched_at.isoformat() if p.last_watched_at else None,
            "source": p.source,
        })
        if len(out) >= limit:
            break
    return out


def widget_continue_reading(db: Session, limit: int = 12) -> list[dict]:
    """In-progress comic/manga issues ordered by most recently read.

    Requires last_read_at (added in schema 2.0.30). Only issues that have
    been opened at least once and are not fully read are returned.
    """
    from app.models import ComicIssue, MediaItem, MediaType

    rows = (
        db.query(ComicIssue)
        .filter(
            ComicIssue.last_read_at.isnot(None),
            ComicIssue.is_read.is_(False),
            ComicIssue.last_page_read.isnot(None),
            ComicIssue.last_page_read > 0,
        )
        .order_by(ComicIssue.last_read_at.desc())
        .limit(limit * 2)  # oversample in case of orphaned volume rows
        .all()
    )
    out: list[dict] = []
    for iss in rows:
        vol = db.get(MediaItem, iss.media_item_id)
        if not vol or vol.media_type not in (MediaType.comic, MediaType.manga):
            continue
        media_type = vol.media_type.value if hasattr(vol.media_type, "value") else str(vol.media_type)
        page = CONTINUE_PAGE_MAP.get(media_type, "comics")
        out.append({
            "issue_id": iss.id,
            "media_item_id": iss.media_item_id,
            "title": vol.title,
            "subtitle": iss.title or (f"#{iss.issue_number}" if iss.issue_number else None),
            "issue_number": iss.issue_number,
            "media_type": media_type,
            "poster_path": iss.poster_path or vol.poster_path,
            "page": page,
            "last_page_read": iss.last_page_read,
            "last_read_at": iss.last_read_at.isoformat() if iss.last_read_at else None,
        })
        if len(out) >= limit:
            break
    return out


def widget_recent_scrobbles(db: Session, limit: int = 15) -> list[dict]:
    from app.models import ScrobbleEvent
    rows = db.query(ScrobbleEvent).order_by(ScrobbleEvent.created_at.desc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "media_item_id": e.media_item_id,
            "game_id": e.game_id,
            "event_type": e.event_type,
            "progress_percent": e.progress_percent,
            "source": e.source,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]


def widget_games_wanted(db: Session, limit: int = 10) -> list[dict]:
    from app.models import Game
    rows = (
        db.query(Game)
        .filter(Game.monitored == True, Game.status.in_(["wanted", "monitored"]))
        .order_by(Game.title)
        .limit(limit)
        .all()
    )
    return [
        {"id": g.id, "title": g.title, "year": g.year, "status": g.status, "platform_id": g.platform_id}
        for g in rows
    ]


def widget_tracking_summary(db: Session) -> dict:
    from app.models import TrackedItem
    from sqlalchemy import func
    rows = db.query(TrackedItem.status, func.count(TrackedItem.id)).group_by(TrackedItem.status).all()
    return {status: count for status, count in rows}
