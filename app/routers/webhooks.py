"""
Player webhook receivers — Jellyfin / Plex / Emby → scrobble events.

POST /api/webhooks/jellyfin
POST /api/webhooks/plex
POST /api/webhooks/emby
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ScrobbleEvent, WatchProgress, MediaItem, MediaType, Episode

log = logging.getLogger("mediaos.webhooks")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _utcnow():
    return datetime.now(timezone.utc)


def _pct(position: Optional[float], duration: Optional[float]) -> float:
    if position is None or duration is None or duration <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * float(position) / float(duration)))


def _check_webhook_secret(request: Request) -> None:
    """Optional shared secret via X-MediaOS-Webhook-Secret or ?secret=."""
    from app.config import settings
    expected = (getattr(settings, "webhook_secret", None) or "").strip()
    if not expected:
        return
    got = request.headers.get("X-MediaOS-Webhook-Secret") or request.headers.get("X-Webhook-Secret")
    if not got:
        got = request.query_params.get("secret")
    if got != expected:
        from fastapi import HTTPException
        raise HTTPException(401, "Invalid webhook secret")


def _find_media(
    db: Session,
    *,
    title: str | None = None,
    tmdb_id: int | None = None,
    imdb_id: str | None = None,
    tvdb_id: int | None = None,
    media_type: str | None = None,
) -> MediaItem | None:
    """Strong library match: provider IDs first, then exact/fuzzy title.

    Order of preference:
      1. imdb_id column
      2. tvdb_id column
      3. external_id + external_source=tmdb/tvdb
      4. external_ids JSON blob contains id
      5. exact title, case-insensitive title, then contains
    """
    q = db.query(MediaItem)
    if media_type:
        try:
            q = q.filter(MediaItem.media_type == media_type)
        except Exception:
            pass

    # 1) IMDb (tt…)
    if imdb_id:
        iid = str(imdb_id).strip()
        if not iid.startswith("tt") and iid.isdigit():
            iid = f"tt{iid}"
        row = q.filter(MediaItem.imdb_id == iid).first()
        if row:
            return row
        # JSON blob fallback
        try:
            row = db.query(MediaItem).filter(MediaItem.external_ids.ilike(f"%{iid}%")).first()
            if row:
                return row
        except Exception:
            pass

    # 2) TVDb
    if tvdb_id:
        try:
            tid = int(tvdb_id)
            row = q.filter(MediaItem.tvdb_id == tid).first()
            if row:
                return row
            row = q.filter(
                MediaItem.external_id == tid,
                MediaItem.external_source.in_(["tvdb", "TVDB"]),
            ).first()
            if row:
                return row
        except (TypeError, ValueError):
            pass

    # 3) TMDb via external_id
    if tmdb_id:
        try:
            tid = int(tmdb_id)
            row = q.filter(
                MediaItem.external_id == tid,
                MediaItem.external_source.in_([None, "tmdb", "TMDB", "tvdb"]),
            ).first()
            if row:
                return row
            row = db.query(MediaItem).filter(MediaItem.external_id == tid).first()
            if row:
                return row
            try:
                row = db.query(MediaItem).filter(
                    MediaItem.external_ids.ilike(f'%"tmdb": {tid}%')
                    | MediaItem.external_ids.ilike(f'%"tmdb":{tid}%')
                ).first()
                if row:
                    return row
            except Exception:
                pass
        except (TypeError, ValueError):
            pass

    # 4) Title fallbacks (exact → ilike → contains)
    if title:
        tclean = (title or "").strip()
        if tclean:
            row = q.filter(MediaItem.title == tclean).first()
            if row:
                return row
            row = q.filter(MediaItem.title.ilike(tclean)).first()
            if row:
                return row
            # Avoid very short contains matches
            if len(tclean) >= 4:
                row = q.filter(MediaItem.title.ilike(f"%{tclean}%")).first()
                if row:
                    return row
    return None



def _resolve_episode(db: Session, media_item_id: int | None, season: int | None, episode: int | None):
    """Canonical episode row for tight progress keys."""
    if not media_item_id or season is None or episode is None:
        return None
    try:
        return (
            db.query(Episode)
            .filter(
                Episode.media_item_id == media_item_id,
                Episode.season_number == int(season),
                Episode.episode_number == int(episode),
            )
            .first()
        )
    except Exception:
        return None


def _upsert_progress(
    db: Session,
    *,
    media_item_id: int | None,
    episode_id: int | None = None,
    season: int | None = None,
    episode: int | None = None,
    progress_percent: float,
    position_seconds: int | None,
    duration_seconds: int | None,
    source: str,
    event_type: str,
    raw: str | None = None,
) -> dict:
    if episode_id is None and media_item_id and season is not None and episode is not None:
        ep_row = _resolve_episode(db, media_item_id, season, episode)
        if ep_row:
            episode_id = ep_row.id
    evt = ScrobbleEvent(
        media_item_id=media_item_id,
        episode_id=episode_id,
        season_number=season,
        episode_number=episode,
        event_type=event_type,
        progress_percent=progress_percent,
        position_seconds=position_seconds,
        duration_seconds=duration_seconds,
        source=source,
        raw_payload=raw,
    )
    db.add(evt)

    q = db.query(WatchProgress)
    if episode_id:
        prog = q.filter(WatchProgress.episode_id == episode_id).first()
    elif media_item_id and season is not None and episode is not None:
        prog = q.filter(
            WatchProgress.media_item_id == media_item_id,
            WatchProgress.season_number == season,
            WatchProgress.episode_number == episode,
        ).first()
    elif media_item_id:
        prog = q.filter(WatchProgress.media_item_id == media_item_id, WatchProgress.episode_id.is_(None)).first()
    else:
        prog = None

    if not prog:
        prog = WatchProgress(
            media_item_id=media_item_id,
            episode_id=episode_id,
            season_number=season,
            episode_number=episode,
            progress_percent=progress_percent,
            position_seconds=position_seconds,
            duration_seconds=duration_seconds,
            source=source,
            last_watched_at=_utcnow(),
            play_count=1 if event_type in ("scrobble", "stop", "PlaybackStop") else 0,
            completed=progress_percent >= 90.0,
        )
        db.add(prog)
    else:
        prog.progress_percent = progress_percent
        prog.position_seconds = position_seconds or prog.position_seconds
        prog.duration_seconds = duration_seconds or prog.duration_seconds
        prog.last_watched_at = _utcnow()
        prog.source = source
        if event_type in ("scrobble", "stop", "PlaybackStop"):
            prog.play_count = (prog.play_count or 0) + 1
        if progress_percent >= 90.0:
            prog.completed = True

    # Optional Trakt scrobble-out
    try:
        from app.config import settings
        if getattr(settings, "trakt_access_token", None) and getattr(settings, "trakt_scrobble_out", True):
            from app.clients.trakt import trakt_client
            mi = db.query(MediaItem).filter(MediaItem.id == media_item_id).first() if media_item_id else None
            if mi:
                trakt_client.scrobble(
                    progress_percent,
                    media_item_id=media_item_id,
                    event=event_type,
                    tmdb_id=mi.external_id if mi.external_source == "tmdb" else None,
                    imdb_id=mi.imdb_id,
                    media_type=mi.media_type.value if hasattr(mi.media_type, "value") else str(mi.media_type),
                    title=mi.title,
                    year=mi.year,
                    season=season,
                    episode=episode,
                )
    except Exception as e:
        log.debug("trakt scrobble-out: %s", e)

    db.commit()
    return {"ok": True, "event_id": evt.id, "progress_percent": progress_percent}


@router.post("/jellyfin")
async def jellyfin_webhook(request: Request, db: Session = Depends(get_db)):
    """Jellyfin webhook (Notification or Playback progress payloads)."""
    _check_webhook_secret(request)

    try:
        body = await request.json()
    except Exception:
        body = {}
    raw = json.dumps(body)[:4000]
    # Jellyfin shapes vary: NotificationType + Item, or Session
    ntype = (body.get("NotificationType") or body.get("Event") or body.get("event") or "").lower()
    item = body.get("Item") or body.get("item") or body.get("Data") or {}
    if isinstance(item, str):
        item = {}
    title = item.get("Name") or item.get("SeriesName") or body.get("Name") or body.get("Title")
    tmdb = imdb = tvdb = None
    try:
        provider = item.get("ProviderIds") or {}
        tmdb = int(provider.get("Tmdb") or provider.get("tmdb") or 0) or None
        imdb = provider.get("Imdb") or provider.get("imdb") or provider.get("IMDB")
        tvdb_raw = provider.get("Tvdb") or provider.get("tvdb") or provider.get("TvDb")
        tvdb = int(tvdb_raw) if tvdb_raw else None
    except Exception:
        pass
    season = item.get("ParentIndexNumber") or item.get("SeasonNumber")
    episode = item.get("IndexNumber") or item.get("EpisodeNumber")
    runtime_ticks = item.get("RunTimeTicks") or body.get("RunTimeTicks")
    pos_ticks = body.get("PlaybackPositionTicks") or item.get("PlaybackPositionTicks")
    duration = int(runtime_ticks / 10_000_000) if runtime_ticks else None
    position = int(pos_ticks / 10_000_000) if pos_ticks else None
    pct = _pct(position, duration)
    if "progress" in ntype or "start" in ntype:
        et = "progress" if "progress" in ntype else "start"
    elif "stop" in ntype:
        et = "stop"
    else:
        et = "scrobble" if pct >= 90 else "progress"
    mi = _find_media(
        db,
        title=title if not season else (item.get("SeriesName") or title),
        tmdb_id=tmdb,
        imdb_id=imdb,
        tvdb_id=tvdb,
    )
    return _upsert_progress(
        db,
        media_item_id=mi.id if mi else None,
        season=int(season) if season is not None else None,
        episode=int(episode) if episode is not None else None,
        progress_percent=pct,
        position_seconds=position,
        duration_seconds=duration,
        source="jellyfin",
        event_type=et,
        raw=raw,
    )


@router.post("/plex")
async def plex_webhook(request: Request, db: Session = Depends(get_db)):
    """Plex webhook (form payload=JSON or raw JSON)."""
    _check_webhook_secret(request)

    body: dict[str, Any] = {}
    try:
        form = await request.form()
        if "payload" in form:
            body = json.loads(str(form["payload"]))
        else:
            body = await request.json()
    except Exception:
        try:
            body = await request.json()
        except Exception:
            body = {}
    raw = json.dumps(body)[:4000]
    event = (body.get("event") or "").lower()
    md = body.get("Metadata") or {}
    title = md.get("grandparentTitle") or md.get("title") or md.get("parentTitle")
    season = md.get("parentIndex")
    episode = md.get("index")
    duration_ms = md.get("duration")
    offset_ms = body.get("viewOffset") or md.get("viewOffset")
    duration = int(duration_ms / 1000) if duration_ms else None
    position = int(offset_ms / 1000) if offset_ms else None
    pct = _pct(position, duration)
    if "stop" in event or "scrobble" in event:
        et = "scrobble" if pct >= 80 else "stop"
    elif "pause" in event:
        et = "pause"
    elif "resume" in event or "play" in event or "start" in event:
        et = "start"
    else:
        et = "progress"
    guid = str(md.get("guid") or "")
    tmdb = imdb = tvdb = None
    # Plex guid forms: tmdb://123, imdb://tt123, tvdb://456, or com.plexapp...
    try:
        if "tmdb://" in guid:
            tmdb = int(guid.split("tmdb://")[-1].split("?")[0].split("/")[0])
        if "imdb://" in guid:
            imdb = guid.split("imdb://")[-1].split("?")[0].split("/")[0]
        if "tvdb://" in guid:
            tvdb = int(guid.split("tvdb://")[-1].split("?")[0].split("/")[0])
        # Guid array on some payloads
        for g in (md.get("Guid") or md.get("guid_list") or []):
            gid = g.get("id") if isinstance(g, dict) else str(g)
            if not gid:
                continue
            if gid.startswith("tmdb://") and not tmdb:
                tmdb = int(gid.split("://", 1)[1].split("?")[0])
            elif gid.startswith("imdb://") and not imdb:
                imdb = gid.split("://", 1)[1].split("?")[0]
            elif gid.startswith("tvdb://") and not tvdb:
                tvdb = int(gid.split("://", 1)[1].split("?")[0])
    except Exception:
        pass
    mi = _find_media(db, title=title, tmdb_id=tmdb, imdb_id=imdb, tvdb_id=tvdb)
    return _upsert_progress(
        db,
        media_item_id=mi.id if mi else None,
        season=int(season) if season is not None else None,
        episode=int(episode) if episode is not None else None,
        progress_percent=pct,
        position_seconds=position,
        duration_seconds=duration,
        source="plex",
        event_type=et,
        raw=raw,
    )


@router.post("/emby")
async def emby_webhook(request: Request, db: Session = Depends(get_db)):
    """Emby webhook (similar to Jellyfin)."""
    _check_webhook_secret(request)

    try:
        body = await request.json()
    except Exception:
        body = {}
    # Reuse jellyfin-like parsing
    request._body = json.dumps(body).encode()  # type: ignore
    # Call shared logic by duplicating minimal path
    raw = json.dumps(body)[:4000]
    item = body.get("Item") or body.get("Data") or {}
    title = item.get("Name") or item.get("SeriesName") or body.get("Title")
    season = item.get("ParentIndexNumber")
    episode = item.get("IndexNumber")
    runtime_ticks = item.get("RunTimeTicks")
    pos_ticks = body.get("PlaybackPositionTicks") or item.get("PlaybackPositionTicks")
    duration = int(runtime_ticks / 10_000_000) if runtime_ticks else None
    position = int(pos_ticks / 10_000_000) if pos_ticks else None
    pct = _pct(position, duration)
    et = "scrobble" if pct >= 90 else "progress"
    tmdb = imdb = tvdb = None
    try:
        provider = item.get("ProviderIds") or {}
        tmdb = int(provider.get("Tmdb") or provider.get("tmdb") or 0) or None
        imdb = provider.get("Imdb") or provider.get("imdb") or provider.get("IMDB")
        tvdb_raw = provider.get("Tvdb") or provider.get("tvdb") or provider.get("TvDb")
        tvdb = int(tvdb_raw) if tvdb_raw else None
    except Exception:
        pass
    mi = _find_media(
        db,
        title=item.get("SeriesName") or title,
        tmdb_id=tmdb,
        imdb_id=imdb,
        tvdb_id=tvdb,
    )
    return _upsert_progress(
        db,
        media_item_id=mi.id if mi else None,
        season=int(season) if season is not None else None,
        episode=int(episode) if episode is not None else None,
        progress_percent=pct,
        position_seconds=position,
        duration_seconds=duration,
        source="emby",
        event_type=et,
        raw=raw,
    )
