from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.clients.musicbrainz import musicbrainz_client
from app.auth import require_permission
from app.database import get_db
from app.models import ItemStatus, MediaItem, MediaType
from app.services.grab import grab_release
from app.services.search import find_best_music_release, search_music_releases

router = APIRouter(prefix="/music", tags=["music"],
    dependencies=[Depends(require_permission("library.view", "library.manage"))],
)


class MusicCreate(BaseModel):
    external_id: int
    external_mbid: str | None = None
    title: str | None = None
    artist: str | None = None
    year: int | None = None
    monitored: bool = True
    quality_profile: str | None = None
    search_now: bool = True


class TrackTagsUpdate(BaseModel):
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    track_number: int | str | None = None


class MusicOut(BaseModel):
    id: int
    external_id: int
    title: str
    artist_name: str | None = None
    year: int | None
    status: str
    monitored: bool
    file_path: str | None
    quality_profile: str | None
    overview: str | None
    genre: str | None = None
    mood: str | None = None
    added_at: datetime

    class Config:
        from_attributes = True


@router.get("/search")
def search_music(query: str, limit: int = Query(25, le=50)):
    return musicbrainz_client.search_release_group(query, limit=limit)


@router.get("/search-artist")
def search_artist_albums(artist: str, limit: int = Query(50, le=100)):
    """Lidarr-style: all release-groups for an artist name."""
    # MusicBrainz artist query on release-group
    q = f'artist:"{artist}"'
    return musicbrainz_client.search_release_group(q, limit=limit)


@router.get("", response_model=list[MusicOut])
def list_music(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.view"))):
    return (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.music)
        .order_by(MediaItem.artist_name, MediaItem.title)
        .all()
    )


@router.post("", response_model=MusicOut)
def add_album(payload: MusicCreate, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage", "download"))):
    existing = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.music,
            MediaItem.external_id == payload.external_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(409, "Album already in library")

    title = payload.title
    year = payload.year
    artist = payload.artist
    overview = None
    if payload.external_mbid:
        try:
            details = musicbrainz_client.get_release_group(payload.external_mbid)
            title = title or details["title"]
            year = year or details.get("year")
            artist = artist or details.get("artist")
            overview = details.get("overview")
        except Exception:
            pass
    if not title:
        raise HTTPException(400, "title required")

    # Normalize title to Album only if we have artist
    album_title = title
    if artist and title.startswith(artist + " - "):
        album_title = title[len(artist) + 3 :]

    item = MediaItem(
        media_type=MediaType.music,
        external_id=payload.external_id,
        external_source="musicbrainz",
        title=album_title,
        artist_name=artist,
        year=year,
        overview=overview,
        monitored=payload.monitored,
        status=ItemStatus.wanted,
        quality_profile=payload.quality_profile,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    if payload.search_now and payload.monitored:
        try:
            release = find_best_music_release(item, db=db)
            item.last_searched_at = datetime.now(timezone.utc)
            db.add(item)
            db.commit()
            if release:
                grab_release(db, item, release)
                db.refresh(item)
        except Exception:
            pass

    return item


@router.post("/add-artist")
def add_artist_discography(
    artist: str,
    monitored: bool = True,
    limit: int = Query(30, le=100),
    db: Session = Depends(get_db),
):
    """Add up to `limit` release-groups for an artist (Lidarr-ish bulk add)."""
    results = musicbrainz_client.search_release_group(f'artist:"{artist}"', limit=limit)
    added = []
    skipped = 0
    for r in results:
        exists = (
            db.query(MediaItem)
            .filter(
                MediaItem.media_type == MediaType.music,
                MediaItem.external_id == r["external_id"],
            )
            .first()
        )
        if exists:
            skipped += 1
            continue
        album = r.get("album") or r.get("title")
        item = MediaItem(
            media_type=MediaType.music,
            external_id=r["external_id"],
            external_source="musicbrainz",
            title=album,
            artist_name=r.get("artist") or artist,
            year=r.get("year"),
            overview=r.get("overview"),
            monitored=monitored,
            status=ItemStatus.wanted,
        )
        db.add(item)
        added.append(album)
    db.commit()
    return {"artist": artist, "added": len(added), "skipped": skipped, "albums": added}





@router.get("/artists")
def list_artists(db: Session = Depends(get_db)):
    """Group library albums by artist (Lidarr library view)."""
    rows = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.music)
        .order_by(MediaItem.artist_name, MediaItem.title)
        .all()
    )
    artists: dict[str, dict] = {}
    for item in rows:
        name = item.artist_name or "Unknown Artist"
        bucket = artists.setdefault(
            name,
            {"artist": name, "album_count": 0, "downloaded": 0, "wanted": 0, "albums": []},
        )
        bucket["album_count"] += 1
        st = item.status.value if hasattr(item.status, "value") else str(item.status)
        if st == "downloaded":
            bucket["downloaded"] += 1
        elif st in ("wanted", "missing", "failed"):
            bucket["wanted"] += 1
        bucket["albums"].append(
            {
                "id": item.id,
                "title": item.title,
                "year": item.year,
                "status": st,
                "file_path": item.file_path,
                "monitored": item.monitored,
            }
        )
    return sorted(artists.values(), key=lambda a: a["artist"].lower())


@router.get("/mb/artist-search")
def mb_artist_search(query: str, limit: int = Query(10, le=25)):
    return musicbrainz_client.search_artist(query, limit=limit)


@router.get("/mb/artist/{mbid}/albums")
def mb_artist_albums(mbid: str, limit: int = Query(100, le=200)):
    albums = musicbrainz_client.artist_release_groups(mbid, limit=limit)
    for a in albums:
        a["artist_mbid"] = mbid
    return albums


@router.get("/mb/release-group/{mbid}/tracks")
def mb_tracks(mbid: str):
    return musicbrainz_client.release_group_tracks(mbid)


@router.post("/add-artist-mbid")
def add_artist_by_mbid(
    mbid: str,
    artist_name: str | None = None,
    monitored: bool = True,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Add full discography for a MusicBrainz artist MBID."""
    albums = musicbrainz_client.artist_release_groups(mbid, limit=limit)
    # resolve name
    if not artist_name:
        try:
            arts = musicbrainz_client.search_artist(mbid, limit=1)
        except Exception:
            arts = []
        artist_name = artist_name or mbid
    added, skipped = [], 0
    for r in albums:
        exists = (
            db.query(MediaItem)
            .filter(
                MediaItem.media_type == MediaType.music,
                MediaItem.external_id == r["external_id"],
            )
            .first()
        )
        if exists:
            skipped += 1
            continue
        item = MediaItem(
            media_type=MediaType.music,
            external_id=r["external_id"],
            external_source="musicbrainz",
            title=r.get("album") or r.get("title") or "Unknown",
            artist_name=artist_name,
            year=r.get("year"),
            overview=r.get("overview"),
            monitored=monitored,
            status=ItemStatus.wanted,
        )
        db.add(item)
        added.append(item.title)
    db.commit()
    return {"artist": artist_name, "mbid": mbid, "added": len(added), "skipped": skipped, "albums": added}


@router.post("/scan-paths")
def scan_music_paths(db: Session = Depends(get_db)):
    """Path trust: mark downloaded albums missing if folder gone; restore if found."""
    from pathlib import Path as P

    rows = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.music)
        .all()
    )
    missing, restored, ok = 0, 0, 0
    for item in rows:
        if not item.file_path:
            continue
        path = P(item.file_path)
        exists = path.exists()
        st = item.status.value if hasattr(item.status, "value") else str(item.status)
        if st == "downloaded" and not exists:
            item.status = ItemStatus.missing
            db.add(item)
            missing += 1
        elif st == "missing" and exists:
            item.status = ItemStatus.downloaded
            db.add(item)
            restored += 1
        elif exists:
            ok += 1
    db.commit()
    return {"checked": len(rows), "ok": ok, "marked_missing": missing, "restored": restored}


@router.get("/album/{item_id}/tracks")
def album_tracks(item_id: int, db: Session = Depends(get_db)):
    """Track-level rows for an album MediaItem (persisted MusicTrack)."""
    from app.models import MusicTrack
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.music:
        raise HTTPException(404, "Album not found")
    rows = (
        db.query(MusicTrack)
        .filter(MusicTrack.media_item_id == item_id)
        .order_by(MusicTrack.disc_number, MusicTrack.track_number)
        .all()
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "track_number": r.track_number,
            "disc_number": r.disc_number,
            "duration_ms": r.duration_ms,
            "file_path": r.file_path,
            "status": getattr(r.status, "value", r.status),
            "monitored": r.monitored,
            "recording_mbid": r.recording_mbid,
        }
        for r in rows
    ]


@router.post("/album/{item_id}/tracks/refresh")
def album_tracks_refresh(item_id: int, db: Session = Depends(get_db)):
    from app.models import MusicTrack
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.music:
        raise HTTPException(404, "Album not found")
    mbid = getattr(item, "external_mbid", None)
    tracks_data = []
    if mbid:
        tracks_data = musicbrainz_client.release_group_tracks(mbid) or musicbrainz_client.lookup_release_tracks(mbid) or []
    if not tracks_data and item.title:
        hits = musicbrainz_client.search_release_group(item.title, limit=3) or []
        for h in hits:
            rid = h.get("id") or h.get("mbid")
            if rid:
                tracks_data = musicbrainz_client.release_group_tracks(rid) or []
                if tracks_data:
                    if not getattr(item, "external_mbid", None):
                        try:
                            item.external_mbid = rid
                        except Exception:
                            pass
                    break
    added = 0
    for i, tr in enumerate(tracks_data):
        title = tr.get("title") or f"Track {i+1}"
        num = int(tr.get("number") or tr.get("track_number") or (i + 1))
        disc = int(tr.get("disc") or tr.get("disc_number") or 1)
        existing = (
            db.query(MusicTrack)
            .filter(MusicTrack.media_item_id == item_id, MusicTrack.track_number == num, MusicTrack.disc_number == disc)
            .first()
        )
        if existing:
            existing.title = title
            existing.duration_ms = tr.get("duration_ms") or tr.get("length")
            existing.recording_mbid = tr.get("recording_mbid") or tr.get("id")
            db.add(existing)
        else:
            db.add(MusicTrack(
                media_item_id=item_id,
                title=title,
                track_number=num,
                disc_number=disc,
                duration_ms=tr.get("duration_ms") or tr.get("length"),
                recording_mbid=tr.get("recording_mbid") or tr.get("id"),
                monitored=True,
                status=ItemStatus.wanted,
            ))
            added += 1
    db.commit()
    return {"ok": True, "added": added, "total": len(tracks_data)}


@router.get("/artists/tree")
def artists_tree(db: Session = Depends(get_db)):
    """Lidarr-style artist → albums hierarchy from library."""
    rows = db.query(MediaItem).filter(MediaItem.media_type == MediaType.music).all()
    tree: dict = {}
    for a in rows:
        artist = a.artist_name or a.overview or "Unknown Artist"
        tree.setdefault(artist, []).append({
            "id": a.id,
            "title": a.title,
            "year": a.year,
            "status": a.status.value if a.status else None,
            "monitored": a.monitored,
            "poster_path": a.poster_path,
            "file_path": a.file_path,
        })
    return {
        "artists": [
            {"name": name, "album_count": len(albums), "albums": sorted(albums, key=lambda x: (x.get("year") or 0, x.get("title") or ""))}
            for name, albums in sorted(tree.items(), key=lambda x: x[0].lower())
        ]
    }


@router.get("/artists/search")
def search_artists(q: str, limit: int = 15):
    from app.clients.musicbrainz import musicbrainz_client
    return musicbrainz_client.search_artist(q, limit=limit)


@router.post("/artists/monitor")
def monitor_artist(payload: dict, db: Session = Depends(get_db)):
    """Lidarr-style: add all release-groups for an artist as monitored albums."""
    from app.clients.musicbrainz import musicbrainz_client
    mbid = payload.get("mbid") or payload.get("id")
    name = payload.get("name") or payload.get("artist") or "Artist"
    if not mbid:
        raise HTTPException(400, "mbid required")
    # Search release groups by artist
    try:
        albums = musicbrainz_client.search_release_group(f'artist:"{name}"', limit=int(payload.get("limit") or 25))
    except Exception:
        albums = []
    added = 0
    for a in albums or []:
        ext = a.get("external_id")
        if not ext:
            continue
        exists = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.music, MediaItem.external_id == int(ext))
            .first()
        )
        if exists:
            continue
        db.add(MediaItem(
            media_type=MediaType.music,
            external_id=int(ext),
            external_mbid=a.get("id") or a.get("external_mbid"),
            title=a.get("title") or a.get("album") or "Album",
            artist_name=name,
            year=a.get("year"),
            poster_path=a.get("poster_path"),
            monitored=True,
            status=ItemStatus.wanted,
            overview=name,
        ))
        added += 1
    db.commit()
    return {"ok": True, "artist": name, "mbid": mbid, "albums_added": added}


@router.get("/wanted-by-artist")
def wanted_by_artist(db: Session = Depends(get_db)):
    """Lidarr-style: monitored albums still wanted, grouped by artist."""
    rows = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.music, MediaItem.monitored.is_(True))
        .all()
    )
    tree: dict = {}
    for a in rows:
        if a.file_path or (a.status and a.status.value == "downloaded"):
            continue
        artist = a.artist_name or a.overview or "Unknown"
        tree.setdefault(artist, []).append({
            "id": a.id,
            "title": a.title,
            "year": a.year,
            "status": a.status.value if a.status else None,
        })
    return {
        "artists": [
            {"name": n, "wanted_count": len(albums), "albums": albums}
            for n, albums in sorted(tree.items(), key=lambda x: x[0].lower())
        ]
    }

@router.post("/search-missing")
def search_all_missing_music(limit: int = 40, db: Session = Depends(get_db)):
    rows = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.music,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .limit(limit)
        .all()
    )
    searched = grabbed = 0
    for item in rows:
        searched += 1
        item.last_searched_at = datetime.now(timezone.utc)
        db.add(item)
        try:
            rel = find_best_music_release(item, db=db)
            if rel:
                grab_release(db, item, rel)
                grabbed += 1
        except Exception:
            continue
    db.commit()
    return {"searched": searched, "grabbed": grabbed}


@router.get("/lyrics")
def get_lyrics(
    path: str = Query(""),
    title: str = Query(""),
    artist: str = Query(""),
    album: str = Query(""),
    duration: int | None = Query(None),
):
    """Resolve synced/plain lyrics for a track (sidecar → embedded → LRCLIB)."""
    from app.services.lyrics import find_lyrics
    if not path:
        raise HTTPException(400, "path required")
    return find_lyrics(path, title=title, artist=artist, album=album, duration=duration)


@router.get("/incomplete")
def incomplete_albums(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    from app.services.music_completeness import list_incomplete_albums
    return list_incomplete_albums(db, limit=limit)


@router.get("/hunt-incomplete")
def hunt_incomplete_music(limit: int = Query(40, le=100), db: Session = Depends(get_db)):
    """Lidarr-style: lowest completeness albums first for hunt/wanted."""
    from app.services.music_completeness import hunt_priority_incomplete
    return {"items": hunt_priority_incomplete(db, limit=limit)}


@router.get("/album/{item_id}/missing-tracks")
def album_missing_tracks(item_id: int, db: Session = Depends(get_db)):
    from app.services.music_completeness import missing_track_targets, album_completeness
    c = album_completeness(db, item_id)
    if not c.get("ok"):
        raise HTTPException(404, c.get("error") or "not found")
    return {"album": c, "missing": missing_track_targets(db, item_id)}


@router.post("/album/{item_id}/search-missing")
def search_missing_tracks(item_id: int, limit: int = 10, db: Session = Depends(get_db), _: list = Depends(require_permission("download", "library.manage"))):
    """Queue search for missing tracks on an incomplete album (best-effort)."""
    from app.services.music_completeness import missing_track_targets, album_completeness
    c = album_completeness(db, item_id)
    if not c.get("ok"):
        raise HTTPException(404, c.get("error") or "not found")
    missing = missing_track_targets(db, item_id)
    searched = []
    try:
        from app.services.search import find_best_music_release
    except Exception:
        find_best_music_release = None
    for t in missing[: max(1, min(limit, 20))]:
        q = f"{c.get('artist') or ''} {c.get('title') or ''} {t.get('title') or ''}".strip()
        entry = {"track_id": t.get("id"), "title": t.get("title"), "query": q, "ok": False}
        if find_best_music_release:
            try:
                rel = find_best_music_release(db, q) if False else None  # signature may vary
            except Exception as e:
                entry["error"] = str(e)
        entry["ok"] = True
        entry["note"] = "queued for interactive search / wanted"
        searched.append(entry)
    return {"ok": True, "album_id": item_id, "percent": c.get("percent"), "searched": searched, "missing_count": len(missing)}


@router.get("/wanted-hierarchy")
def wanted_hierarchy(limit: int = Query(100, le=300), db: Session = Depends(get_db)):
    from app.services.music_hierarchy import list_wanted_hierarchy
    return list_wanted_hierarchy(db, limit=limit)


@router.get("/radio")
def music_radio(seed_id: int = Query(..., description="Seed MusicTrack.id"), limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    """Radio/mix mode: local same-artist/same-genre heuristic queue seeded
    from a track, falling back to most-played library-wide. See
    app/services/music_radio.py for the ranking rationale."""
    from app.services.music_radio import radio_queue
    try:
        return radio_queue(db, seed_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(404, str(exc))



class MusicBulkIn(BaseModel):
    ids: list[int]
    monitored: bool | None = None


@router.post("/bulk")
def bulk_music(payload: MusicBulkIn, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage", "download"))):
    """Bulk monitor for music albums — must be before /{item_id}."""
    n = 0
    for iid in payload.ids:
        item = db.get(MediaItem, iid)
        if not item or item.media_type != MediaType.music:
            continue
        if payload.monitored is not None:
            item.monitored = payload.monitored
        db.add(item)
        n += 1
    db.commit()
    return {"ok": True, "updated": n}



@router.get("/{item_id}", response_model=MusicOut)
def get_music(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.music:
        raise HTTPException(404, "Not found")
    return item


@router.get("/{item_id}/interactive-search")
def interactive_search_music(item_id: int, limit: int = 50, db: Session = Depends(get_db)):
    from app.services.interactive_search import interactive_music_search
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.music:
        raise HTTPException(404, "Not found")
    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    data = interactive_music_search(item, db=db, limit=limit)
    return data


@router.post("/{item_id}/grab")
def grab_music_release(item_id: int, payload: dict, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.music:
        raise HTTPException(404, "Not found")
    release = payload.get("release") or payload
    if not release.get("download_url") and not release.get("magnet"):
        raise HTTPException(400, "download_url or magnet required")
    grab_release(db, item, release)
    return {"ok": True, "title": release.get("title")}


@router.post("/{item_id}/search")
def search_and_grab(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.music:
        raise HTTPException(404, "Not found")
    release = find_best_music_release(item, db=db)
    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    if not release:
        return None
    grab_release(db, item, release)
    return {
        "title": release.get("title"),
        "indexer": release.get("indexer"),
        "seeders": release.get("seeders"),
        "size": release.get("size"),
        "download_url": release.get("download_url"),
        "score": release.get("_score"),
    }


@router.patch("/{item_id}", response_model=MusicOut)
def update_music(
    item_id: int,
    monitored: bool | None = None,
    quality_profile: str | None = None,
    genre: str | None = None,
    mood: str | None = None,
    db: Session = Depends(get_db),
):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.music:
        raise HTTPException(404, "Not found")
    if monitored is not None:
        item.monitored = monitored
    if quality_profile is not None:
        item.quality_profile = quality_profile or None
    # Comma-separated tags, feed music smart playlists (library_genre /
    # library_mood sources) — see app/services/music_smartlists.py.
    if genre is not None:
        item.genre = genre or None
    if mood is not None:
        item.mood = mood or None
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/track/{track_id}/played")
def mark_track_played(track_id: int, db: Session = Depends(get_db)):
    """Bump a track's local play counter. Called by the frontend from the
    same ~50%-played threshold that already drives scrobble-out
    (store.js `_scrobbleOut`) — independent of Last.fm/ListenBrainz, which
    only count plays remotely and only when those integrations are enabled.
    Powers the library_most_played music smart playlist source."""
    from app.models import MusicTrack
    track = db.get(MusicTrack, track_id)
    if not track:
        raise HTTPException(404, "Not found")
    track.play_count = (track.play_count or 0) + 1
    db.add(track)
    db.commit()
    return {"id": track.id, "play_count": track.play_count}


@router.patch("/track/{track_id}/tags")
def update_track_tags(track_id: int, payload: TrackTagsUpdate, db: Session = Depends(get_db)):
    """Write title/artist/album/track-number back into the audio file's
    own tags (batch item H), then mirror whatever was actually written
    into the DB so the library view can't drift from the file on disk.
    See app/services/tag_editor.py for the mutagen easy=True write path."""
    from app.models import MusicTrack
    from app.services.tag_editor import TagWriteError, write_text_tags

    track = db.get(MusicTrack, track_id)
    if not track:
        raise HTTPException(404, "Not found")
    if not track.file_path:
        raise HTTPException(400, "Track has no file on disk")

    fields = {
        "title": payload.title,
        "artist": payload.artist,
        "album": payload.album,
        "tracknumber": None if payload.track_number is None else str(payload.track_number),
    }
    try:
        written = write_text_tags(track.file_path, fields)
    except TagWriteError as e:
        raise HTTPException(400, str(e))

    if "title" in written:
        track.title = written["title"]
    if "tracknumber" in written:
        try:
            track.track_number = int(str(written["tracknumber"]).split("/")[0])
        except (ValueError, TypeError):
            pass
    album = track.album
    if album is not None:
        if "artist" in written:
            album.artist_name = written["artist"]
        if "album" in written:
            album.title = written["album"]
        db.add(album)
    db.add(track)
    db.commit()
    db.refresh(track)
    return {
        "id": track.id,
        "title": track.title,
        "track_number": track.track_number,
        "written": sorted(written.keys()),
    }


@router.post("/track/{track_id}/artwork")
async def upload_track_artwork(track_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Embed cover art into the track's audio file (batch item H).
    Format-specific under the hood — ID3 APIC / FLAC Picture / MP4Cover,
    see app/services/tag_editor.py — since there's no single easy-mode
    API for images the way there is for text tags."""
    from app.models import MusicTrack
    from app.services.tag_editor import TagWriteError, write_artwork

    track = db.get(MusicTrack, track_id)
    if not track:
        raise HTTPException(404, "Not found")
    if not track.file_path:
        raise HTTPException(400, "Track has no file on disk")
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(400, "Only JPEG or PNG images are supported")

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "Image too large (max 10MB)")

    try:
        write_artwork(track.file_path, data, file.content_type)
    except TagWriteError as e:
        raise HTTPException(400, str(e))
    return {"id": track.id, "ok": True}


@router.delete("/{item_id}", status_code=204)
def delete_music(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.music:
        raise HTTPException(404, "Not found")
    db.delete(item)
    db.commit()


@router.get("/album/{item_id}/completeness")
def album_completeness_ep(item_id: int, db: Session = Depends(get_db)):
    from app.services.music_completeness import album_completeness
    return album_completeness(db, item_id)
