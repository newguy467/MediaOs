"""
Scrobbling & progress router (scrob + Yamtrack inspired, MediaOS v2).
"""

from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_permission
from app.models import ScrobbleEvent, WatchProgress, MediaItem, Game, MusicTrack, TrackedItem

router = APIRouter(prefix="/scrobble", tags=["scrobbling"])


class ScrobbleIn(BaseModel):
    media_item_id: Optional[int] = None
    game_id: Optional[int] = None
    episode_id: Optional[int] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    event_type: str = "scrobble"  # start|pause|resume|stop|scrobble|progress
    progress_percent: float = 0.0
    position_seconds: Optional[int] = None
    duration_seconds: Optional[int] = None
    source: str = "manual"
    raw_payload: Optional[str] = None


class MusicScrobbleIn(BaseModel):
    track_id: int
    event_type: str = "scrobble"


class ProgressUpdate(BaseModel):
    media_item_id: Optional[int] = None
    game_id: Optional[int] = None
    progress_percent: float
    position_seconds: Optional[int] = None
    duration_seconds: Optional[int] = None
    completed: Optional[bool] = None
    source: str = "manual"


@router.post("")
def ingest_scrobble(
    body: ScrobbleIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("library")),
):
    if not body.media_item_id and not body.game_id:
        raise HTTPException(400, "media_item_id or game_id required")

    evt = ScrobbleEvent(
        media_item_id=body.media_item_id,
        game_id=body.game_id,
        episode_id=body.episode_id,
        season_number=body.season_number,
        episode_number=body.episode_number,
        event_type=body.event_type,
        progress_percent=body.progress_percent,
        position_seconds=body.position_seconds,
        duration_seconds=body.duration_seconds,
        source=body.source,
        raw_payload=body.raw_payload,
    )
    db.add(evt)

    # Upsert progress
    prog = None
    if body.media_item_id:
        prog = db.query(WatchProgress).filter(WatchProgress.media_item_id == body.media_item_id).first()
    elif body.game_id:
        prog = db.query(WatchProgress).filter(WatchProgress.game_id == body.game_id).first()

    if not prog:
        prog = WatchProgress(
            media_item_id=body.media_item_id,
            game_id=body.game_id,
            progress_percent=body.progress_percent,
            position_seconds=body.position_seconds,
            duration_seconds=body.duration_seconds,
            source=body.source,
            last_watched_at=datetime.now(timezone.utc),
            play_count=1 if body.event_type in ("scrobble", "stop") else 0,
            completed=body.progress_percent >= 90.0,
        )
        db.add(prog)
    else:
        prog.progress_percent = body.progress_percent
        prog.position_seconds = body.position_seconds or prog.position_seconds
        prog.duration_seconds = body.duration_seconds or prog.duration_seconds
        prog.last_watched_at = datetime.now(timezone.utc)
        prog.source = body.source
        if body.event_type in ("scrobble", "stop"):
            prog.play_count = (prog.play_count or 0) + 1
        if body.progress_percent >= 90.0:
            prog.completed = True

    # Optional: update game playtime
    if body.game_id and body.position_seconds:
        game = db.get(Game, body.game_id)
        if game:
            # crude: add delta if we had previous position; for now just store percent
            game.completion_percent = max(game.completion_percent or 0, body.progress_percent)
            game.last_played_at = datetime.now(timezone.utc)

    # Unified tracking writeback (status + progress)
    try:
        tracked = None
        if body.media_item_id:
            tracked = db.query(TrackedItem).filter(TrackedItem.media_item_id == body.media_item_id).first()
        elif body.game_id:
            tracked = db.query(TrackedItem).filter(TrackedItem.game_id == body.game_id).first()
        now = datetime.now(timezone.utc)
        status = "completed" if body.progress_percent >= 90.0 else "in_progress"
        if body.event_type in ("start", "resume") and body.progress_percent < 90:
            status = "in_progress"
        if tracked:
            tracked.progress_percent = max(tracked.progress_percent or 0, body.progress_percent)
            if status == "completed" or (tracked.status or "") in ("", "planned", "in_progress"):
                tracked.status = status
            if status == "completed":
                tracked.completed_at = tracked.completed_at or now
            if status == "in_progress" and not tracked.started_at:
                tracked.started_at = now
            tracked.updated_at = now
            db.add(tracked)
        elif body.media_item_id or body.game_id:
            tracked = TrackedItem(
                media_item_id=body.media_item_id,
                game_id=body.game_id,
                status=status,
                progress_percent=body.progress_percent,
                started_at=now if status == "in_progress" else None,
                completed_at=now if status == "completed" else None,
            )
            db.add(tracked)
    except Exception:
        pass  # never fail scrobble on tracking soft-fail

    db.commit()
    return {"ok": True, "event_id": evt.id, "progress_percent": prog.progress_percent}


@router.get("/history")
def history(
    media_item_id: Optional[int] = None,
    game_id: Optional[int] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(ScrobbleEvent)
    if media_item_id:
        q = q.filter(ScrobbleEvent.media_item_id == media_item_id)
    if game_id:
        q = q.filter(ScrobbleEvent.game_id == game_id)
    rows = q.order_by(ScrobbleEvent.created_at.desc()).limit(limit).all()
    items = []
    for e in rows:
        title = None
        media_type = None
        if e.media_item_id:
            item = db.get(MediaItem, e.media_item_id)
            if item:
                title = item.title
                media_type = item.media_type.value if hasattr(item.media_type, "value") else str(item.media_type)
        if e.game_id:
            g = db.get(Game, e.game_id)
            if g:
                title = g.title
                media_type = "game"
        items.append({
            "id": e.id,
            "media_item_id": e.media_item_id,
            "game_id": e.game_id,
            "title": title,
            "media_type": media_type,
            "event_type": e.event_type,
            "progress_percent": e.progress_percent,
            "source": e.source,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        })
    return {"items": items, "count": len(items)}


@router.get("/progress")
def get_progress(
    media_item_id: Optional[int] = None,
    game_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(WatchProgress)
    if media_item_id:
        q = q.filter(WatchProgress.media_item_id == media_item_id)
    if game_id:
        q = q.filter(WatchProgress.game_id == game_id)
    rows = q.limit(100).all()
    return {
        "items": [
            {
                "id": p.id,
                "media_item_id": p.media_item_id,
                "game_id": p.game_id,
                "progress_percent": p.progress_percent,
                "completed": p.completed,
                "play_count": p.play_count,
                "last_watched_at": p.last_watched_at.isoformat() if p.last_watched_at else None,
                "source": p.source,
            }
            for p in rows
        ]
    }


@router.get("/continue")
def continue_watching(limit: int = 20, db: Session = Depends(get_db)):
    """Items with progress > 0 and < 90% — Continue Watching / Playing."""
    rows = (
        db.query(WatchProgress)
        .filter(WatchProgress.progress_percent > 0, WatchProgress.progress_percent < 90)
        .order_by(WatchProgress.last_watched_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "media_item_id": p.media_item_id,
                "game_id": p.game_id,
                "progress_percent": p.progress_percent,
                "last_watched_at": p.last_watched_at.isoformat() if p.last_watched_at else None,
            }
            for p in rows
        ]
    }


@router.post("/trakt/push")
def trakt_push(body: ScrobbleIn, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Forward scrobble to Trakt when enabled."""
    from app.config import settings
    if not getattr(settings, "trakt_scrobble_out", True):
        return {"ok": False, "reason": "disabled"}
    try:
        from app.clients.trakt import TraktClient
        mi = db.query(MediaItem).filter(MediaItem.id == body.media_item_id).first() if body.media_item_id else None
        ok = TraktClient().scrobble(
            progress=body.progress_percent,
            media_item_id=body.media_item_id,
            event=body.event_type or "scrobble",
            tmdb_id=(mi.external_id if mi and mi.external_source == "tmdb" else None),
            imdb_id=(mi.imdb_id if mi else None),
            media_type=(mi.media_type.value if mi and hasattr(mi.media_type, "value") else str(mi.media_type) if mi else "movie"),
            title=(mi.title if mi else None),
            year=(mi.year if mi else None),
            season=body.season_number,
            episode=body.episode_number,
        )
        return {"ok": bool(ok), "provider": "trakt"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _music_scrobble_meta(db: Session, track_id: int) -> dict | None:
    """Look up a MusicTrack + its parent album MediaItem and return the
    metadata both Last.fm and ListenBrainz scrobble calls need. Sourced from
    the DB rather than trusted from the request body — music has no
    tmdb/imdb id, so unlike the Trakt push this can't rely on the client
    round-tripping provider ids.
    """
    track = db.get(MusicTrack, track_id)
    if not track:
        return None
    album = db.get(MediaItem, track.media_item_id) if track.media_item_id else None
    return {
        "title": track.title,
        "artist": (album.artist_name if album else None) or "Unknown Artist",
        "album": album.title if album else None,
        "duration_ms": track.duration_ms,
        "recording_mbid": track.recording_mbid,
    }


@router.post("/lastfm/push")
def lastfm_push(body: MusicScrobbleIn, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Forward a music scrobble to Last.fm when enabled."""
    from app.config import settings
    if not getattr(settings, "lastfm_scrobble_out", True):
        return {"ok": False, "reason": "disabled"}
    meta = _music_scrobble_meta(db, body.track_id)
    if not meta:
        return {"ok": False, "reason": "track not found"}
    try:
        from app.clients.lastfm import LastfmClient
        ok = LastfmClient().scrobble(
            artist=meta["artist"],
            track=meta["title"],
            album=meta["album"],
            duration_seconds=(meta["duration_ms"] // 1000) if meta["duration_ms"] else None,
        )
        return {"ok": bool(ok), "provider": "lastfm"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/listenbrainz/push")
def listenbrainz_push(body: MusicScrobbleIn, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Forward a music scrobble to ListenBrainz when enabled."""
    from app.config import settings
    if not getattr(settings, "listenbrainz_scrobble_out", True):
        return {"ok": False, "reason": "disabled"}
    meta = _music_scrobble_meta(db, body.track_id)
    if not meta:
        return {"ok": False, "reason": "track not found"}
    try:
        from app.clients.listenbrainz import ListenBrainzClient
        ok = ListenBrainzClient().scrobble(
            artist=meta["artist"],
            track=meta["title"],
            release=meta["album"],
            duration_ms=meta["duration_ms"],
            recording_mbid=meta["recording_mbid"],
        )
        return {"ok": bool(ok), "provider": "listenbrainz"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
