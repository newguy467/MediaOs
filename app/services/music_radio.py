"""Radio / mix mode for music: given a seed track, build a queue of similar
already-downloaded tracks from the local library.

Design decision (per todo section G): MusicBrainz has no real "similar
artists" endpoint (confirmed by inspecting app/clients/musicbrainz.py before
writing this — it only exposes search/lookup methods), and standing up a
real external recommendation source was out of scope for this pass. Uses a
same-genre / same-artist heuristic purely over local library data instead,
reusing MediaItem.genre (added in batch item F) as the only signal that
exists today.

Candidates are ranked:
  1. same artist, different album  (highest — a listener who queued one
     AJ McLean track is very likely fine with another)
  2. same genre, different artist  (genre overlap, comma-list OR match,
     same convention as music_smartlists._tag_filter)
  3. fallback: most-played tracks library-wide, so radio mode still
     produces *something* for a freshly-tagged or single-artist library
     instead of coming back empty.
Recently played tracks (the seed's own recent history, tracked via
WatchProgress at the album level — there's no per-track play history table
today, only MusicTrack.play_count, which is cumulative and not time-aware)
aren't de-prioritized by recency here for that reason; de-duplication
against the seed and against each other is what's enforced instead.
"""
from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.models import MediaItem, MediaType, MusicTrack


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


def _split_terms(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip().lower() for t in raw.split(",") if t.strip()]


def radio_queue(db: Session, seed_track_id: int, limit: int = 20) -> list[dict]:
    """Build a radio queue seeded from a specific track. Returns already-
    downloaded tracks only (file_path IS NOT NULL) — an undownloaded row
    can't be queued for playback, same rule as music smart playlists."""
    limit = max(1, min(int(limit or 20), 100))

    seed = db.get(MusicTrack, seed_track_id)
    if not seed:
        raise ValueError(f"Track {seed_track_id} not found")
    seed_album = db.get(MediaItem, seed.media_item_id) if seed.media_item_id else None

    exclude_track_ids = {seed.id}
    out: list[dict] = []

    # 1. Same artist, different album — strongest signal.
    if seed_album and seed_album.artist_name:
        other_albums = (
            db.query(MediaItem)
            .filter(
                MediaItem.media_type == MediaType.music,
                MediaItem.artist_name == seed_album.artist_name,
                MediaItem.id != seed_album.id,
            )
            .all()
        )
        # Include the seed's own album too, for its other tracks.
        album_ids = [a.id for a in other_albums] + [seed_album.id]
        albums_by_id = {a.id: a for a in other_albums}
        albums_by_id[seed_album.id] = seed_album
        candidates = (
            db.query(MusicTrack)
            .filter(MusicTrack.media_item_id.in_(album_ids), MusicTrack.file_path.isnot(None))
            .all()
        )
        candidates = [c for c in candidates if c.id not in exclude_track_ids]
        random.shuffle(candidates)
        for c in candidates:
            if len(out) >= limit:
                break
            out.append(_track_row(c, albums_by_id.get(c.media_item_id)))
            exclude_track_ids.add(c.id)

    # 2. Same genre, different artist — genre overlap (comma-list OR match).
    if len(out) < limit and seed_album and seed_album.genre:
        terms = _split_terms(seed_album.genre)
        if terms:
            genre_albums = (
                db.query(MediaItem)
                .filter(MediaItem.media_type == MediaType.music, MediaItem.genre.isnot(None))
                .all()
            )
            genre_albums = [
                a for a in genre_albums
                if a.id != (seed_album.id if seed_album else None)
                and any(t in _split_terms(a.genre) for t in terms)
            ]
            random.shuffle(genre_albums)
            for album in genre_albums:
                if len(out) >= limit:
                    break
                tracks = (
                    db.query(MusicTrack)
                    .filter(MusicTrack.media_item_id == album.id, MusicTrack.file_path.isnot(None))
                    .all()
                )
                tracks = [t for t in tracks if t.id not in exclude_track_ids]
                if not tracks:
                    continue
                pick = random.choice(tracks)
                out.append(_track_row(pick, album))
                exclude_track_ids.add(pick.id)

    # 3. Fallback: most-played tracks library-wide, so a sparsely-tagged
    # library still produces a non-empty radio queue.
    if len(out) < limit:
        fallback = (
            db.query(MusicTrack)
            .filter(MusicTrack.file_path.isnot(None))
            .order_by(MusicTrack.play_count.desc())
            .limit(limit * 2)
            .all()
        )
        fallback = [t for t in fallback if t.id not in exclude_track_ids]
        album_ids = {t.media_item_id for t in fallback if t.media_item_id}
        albums = {a.id: a for a in db.query(MediaItem).filter(MediaItem.id.in_(album_ids)).all()} if album_ids else {}
        for t in fallback:
            if len(out) >= limit:
                break
            out.append(_track_row(t, albums.get(t.media_item_id)))
            exclude_track_ids.add(t.id)

    random.shuffle(out)
    return out[:limit]
