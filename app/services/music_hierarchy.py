"""Music hierarchy — Headphones-inspired Artist → Album → Track."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import MediaItem, MediaType, MusicTrack, ItemStatus


def artist_album_track_tree(db: Session, *, monitored_only: bool = False, limit_artists: int = 200) -> list[dict]:
    q = db.query(MediaItem).filter(MediaItem.media_type == MediaType.music)
    if monitored_only:
        q = q.filter(MediaItem.monitored.is_(True))
    albums = q.order_by(MediaItem.artist_name, MediaItem.title).limit(2000).all()
    tree: dict[str, dict] = {}
    for album in albums:
        artist = (album.artist_name or "Unknown Artist").strip() or "Unknown Artist"
        node = tree.setdefault(artist, {"artist": artist, "albums": [], "album_count": 0, "complete_albums": 0})
        tracks = db.query(MusicTrack).filter(MusicTrack.media_item_id == album.id).order_by(MusicTrack.disc_number, MusicTrack.track_number).all()
        have = 0
        track_rows = []
        for t in tracks:
            st = str(getattr(t.status, "value", t.status) or "")
            ok = bool(t.file_path) or st in ("downloaded", "complete")
            if ok:
                have += 1
            track_rows.append({
                "id": t.id,
                "title": t.title,
                "track_number": t.track_number,
                "disc_number": t.disc_number,
                "file_path": t.file_path,
                "have": ok,
            })
        total = len(tracks)
        if total == 0:
            pct = 100 if album.file_path else 0
            complete = bool(album.file_path)
        else:
            pct = int(100 * have / total) if total else 0
            complete = pct >= 100
        node["albums"].append({
            "id": album.id,
            "title": album.title,
            "year": album.year,
            "status": album.status.value if album.status else None,
            "monitored": album.monitored,
            "percent": pct,
            "complete": complete,
            "tracks_total": total,
            "tracks_have": have,
            "tracks": track_rows,
        })
        node["album_count"] += 1
        if complete:
            node["complete_albums"] += 1
        if len(tree) >= limit_artists:
            break
    # sort albums inside artist
    out = []
    for artist in sorted(tree.keys(), key=lambda s: s.lower()):
        node = tree[artist]
        node["albums"].sort(key=lambda a: (a.get("year") or 0, a.get("title") or ""))
        node["percent"] = int(100 * node["complete_albums"] / node["album_count"]) if node["album_count"] else 0
        out.append(node)
    return out


def wanted_by_artist(db: Session) -> list[dict]:
    wanted = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.music,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing] if hasattr(ItemStatus, "missing") else [ItemStatus.wanted]),
        )
        .order_by(MediaItem.artist_name, MediaItem.title)
        .all()
    )
    tree: dict[str, list] = {}
    for item in wanted:
        key = item.artist_name or "Unknown Artist"
        tree.setdefault(key, []).append({
            "id": item.id,
            "title": item.title,
            "year": item.year,
            "status": item.status.value if item.status else None,
        })
    return [{"artist": k, "albums": v} for k, v in tree.items()]


def list_wanted_hierarchy(db: Session, limit: int = 100) -> dict:
    """API shape expected by /music/wanted-hierarchy."""
    rows = wanted_by_artist(db)
    # flatten-ish count limit
    count = 0
    out = []
    for block in rows:
        out.append(block)
        count += len(block.get("albums") or [])
        if count >= limit:
            break
    return {"artists": out, "count": count}
