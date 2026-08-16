"""Resolve music smart playlists: saved, live-updating filters over the
*existing* local library — the opposite of app/services/smartlists.py, which
discovers and adds new items from external APIs (TMDb/Trakt/IMDb). There is
nothing to "run"; every read re-evaluates the filter against MediaItem/
MusicTrack right now.

SUPPORTED_SOURCES:
- library_genre       — MediaItem.genre substring match (comma list = OR)
- library_mood        — MediaItem.mood substring match (comma list = OR)
- library_recent      — albums added within the last `added_within_days` days
- library_most_played — tracks with at least `min_play_count` plays, most first
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import MediaItem, MediaType, MusicSmartlist, MusicTrack

SUPPORTED_SOURCES = (
    "library_genre",
    "library_mood",
    "library_recent",
    "library_most_played",
)


def _split_terms(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _tag_filter(column, raw: str | None):
    """Substring/OR match against a comma-separated tag column, matching the
    convention already used by LiveTvVirtualChannel.genre_filter."""
    terms = _split_terms(raw)
    if not terms:
        return None
    return or_(*[column.ilike(f"%{t}%") for t in terms])


def _track_row(tr: MusicTrack, album: MediaItem | None) -> dict:
    return {
        "id": tr.id,
        "title": tr.title,
        "file_path": tr.file_path,
        "duration_ms": tr.duration_ms,
        "track_number": tr.track_number,
        "disc_number": tr.disc_number,
        "play_count": tr.play_count,
        "album_id": album.id if album else None,
        "album_title": album.title if album else None,
        "artist_name": album.artist_name if album else None,
        "poster_path": album.poster_path if album else None,
    }


def resolve_smartlist(db: Session, sl: MusicSmartlist) -> list[dict]:
    """Return the current list of matching tracks for a saved smart playlist.
    Only downloaded tracks with a real file are returned — an undownloaded
    row can't be queued for playback."""
    limit = max(1, min(int(sl.result_limit or 50), 500))
    src = (sl.source or "").lower()

    if src in ("library_genre", "library_mood"):
        col = MediaItem.genre if src == "library_genre" else MediaItem.mood
        raw = sl.genre_filter if src == "library_genre" else sl.mood_filter
        cond = _tag_filter(col, raw)
        q = db.query(MediaItem).filter(MediaItem.media_type == MediaType.music)
        if cond is not None:
            q = q.filter(cond)
        albums = q.order_by(MediaItem.title).limit(limit * 3).all()
        out: list[dict] = []
        for album in albums:
            tracks = (
                db.query(MusicTrack)
                .filter(MusicTrack.media_item_id == album.id, MusicTrack.file_path.isnot(None))
                .order_by(MusicTrack.disc_number, MusicTrack.track_number)
                .all()
            )
            out.extend(_track_row(t, album) for t in tracks)
            if len(out) >= limit:
                break
        return out[:limit]

    if src == "library_recent":
        days = sl.added_within_days if sl.added_within_days and sl.added_within_days > 0 else 30
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        albums = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.music, MediaItem.added_at >= cutoff)
            .order_by(MediaItem.added_at.desc())
            .limit(limit * 3)
            .all()
        )
        out = []
        for album in albums:
            tracks = (
                db.query(MusicTrack)
                .filter(MusicTrack.media_item_id == album.id, MusicTrack.file_path.isnot(None))
                .order_by(MusicTrack.disc_number, MusicTrack.track_number)
                .all()
            )
            out.extend(_track_row(t, album) for t in tracks)
            if len(out) >= limit:
                break
        return out[:limit]

    if src == "library_most_played":
        min_plays = sl.min_play_count if sl.min_play_count and sl.min_play_count > 0 else 1
        tracks = (
            db.query(MusicTrack)
            .filter(MusicTrack.file_path.isnot(None), MusicTrack.play_count >= min_plays)
            .order_by(MusicTrack.play_count.desc())
            .limit(limit)
            .all()
        )
        album_ids = {t.media_item_id for t in tracks if t.media_item_id}
        albums = {a.id: a for a in db.query(MediaItem).filter(MediaItem.id.in_(album_ids)).all()} if album_ids else {}
        return [_track_row(t, albums.get(t.media_item_id)) for t in tracks]

    raise ValueError(f"Unknown music smart playlist source: {sl.source}")
