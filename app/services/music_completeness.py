"""Music album completeness — Headphones-inspired."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import MediaItem, MediaType, MusicTrack, ItemStatus


def album_completeness(db: Session, album_id: int) -> dict:
    album = db.get(MediaItem, album_id)
    if not album or album.media_type != MediaType.music:
        return {"ok": False, "error": "not a music album"}
    tracks = db.query(MusicTrack).filter(MusicTrack.media_item_id == album_id).all()
    total = len(tracks)
    have = 0
    missing = []
    for t in tracks:
        ok = bool(t.file_path) or (
            t.status in (ItemStatus.downloaded,) if hasattr(ItemStatus, "downloaded") else False
        )
        if t.status and str(getattr(t.status, "value", t.status)) in ("downloaded", "complete"):
            ok = True
        if ok:
            have += 1
        else:
            missing.append({
                "id": t.id,
                "title": t.title,
                "track_number": t.track_number,
                "disc_number": t.disc_number,
            })
    if total == 0:
        pct = 100 if album.file_path else 0
        complete = bool(album.file_path)
    else:
        pct = int(100 * have / total)
        complete = pct >= 100
    return {
        "ok": True,
        "album_id": album_id,
        "title": album.title,
        "artist": album.artist_name,
        "tracks_total": total,
        "tracks_have": have,
        "tracks_missing": len(missing),
        "percent": pct,
        "complete": complete,
        "missing": missing[:50],
        "album_file": album.file_path,
    }


def list_incomplete_albums(db: Session, limit: int = 50) -> list[dict]:
    albums = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.music, MediaItem.monitored.is_(True))
        .order_by(MediaItem.id.desc())
        .limit(200)
        .all()
    )
    out = []
    for a in albums:
        c = album_completeness(db, a.id)
        if c.get("ok") and not c.get("complete"):
            out.append(c)
        if len(out) >= limit:
            break
    return out
