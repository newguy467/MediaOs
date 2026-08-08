"""Migrate library from Sonarr / Radarr (API) into mediaos."""
from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import Episode, ItemStatus, MediaItem, MediaType
from app.services.activity import log_activity
from app.services.sse import publish as sse_publish

log = logging.getLogger(__name__)


def _client(base_url: str, api_key: str) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={"X-Api-Key": api_key},
        timeout=60.0,
    )


def migrate_radarr(db: Session, *, url: str, api_key: str, monitor: bool = True) -> dict:
    """Pull movies from Radarr API and upsert into mediaos MediaItem rows."""
    added = updated = skipped = 0
    with _client(url, api_key) as client:
        r = client.get("/api/v3/movie")
        r.raise_for_status()
        movies = r.json()
    for m in movies:
        tmdb = m.get("tmdbId") or m.get("tmdb_id")
        if not tmdb:
            skipped += 1
            continue
        title = m.get("title") or m.get("sortTitle") or f"Movie {tmdb}"
        year = m.get("year")
        path = m.get("path")
        has_file = bool(m.get("hasFile") or m.get("movieFile"))
        row = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.movie, MediaItem.external_id == int(tmdb))
            .first()
        )
        if row is None:
            row = MediaItem(
                media_type=MediaType.movie,
                external_id=int(tmdb),
                title=title,
                year=year,
                monitored=bool(m.get("monitored", monitor)),
                status=ItemStatus.downloaded if has_file else ItemStatus.wanted,
                file_path=path if has_file else None,
                overview=(m.get("overview") or "")[:2000] or None,
                quality_profile=(m.get("qualityProfile") or {}).get("name") if isinstance(m.get("qualityProfile"), dict) else (m.get("qualityProfileId") and str(m.get("qualityProfileId"))),
            )
            db.add(row)
            added += 1
        else:
            row.title = title
            if year:
                row.year = year
            if has_file and path:
                row.file_path = path
                row.status = ItemStatus.downloaded
            row.monitored = bool(m.get("monitored", row.monitored))
            db.add(row)
            updated += 1
    db.commit()
    log_activity(db, "migrate_radarr", f"Radarr import +{added} ~{updated}")
    try:
        sse_publish("migrate", {"source": "radarr", "added": added, "updated": updated})
    except Exception:
        pass
    return {"ok": True, "source": "radarr", "added": added, "updated": updated, "skipped": skipped, "total": len(movies)}


def migrate_sonarr(db: Session, *, url: str, api_key: str, monitor: bool = True) -> dict:
    """Pull series + episodes from Sonarr API into mediaos."""
    added = updated = eps_added = skipped = 0
    with _client(url, api_key) as client:
        r = client.get("/api/v3/series")
        r.raise_for_status()
        series_list = r.json()
        # episode endpoint can be heavy — fetch per series
        for s in series_list:
            tvdb = s.get("tvdbId") or s.get("tvdb_id")
            tmdb = s.get("tmdbId")
            external = int(tvdb or tmdb or 0)
            if not external:
                skipped += 1
                continue
            title = s.get("title") or f"Series {external}"
            year = s.get("year")
            path = s.get("path")
            series_type = (s.get("seriesType") or "standard").lower()  # standard|anime|daily
            row = (
                db.query(MediaItem)
                .filter(MediaItem.media_type == MediaType.tv, MediaItem.external_id == external)
                .first()
            )
            if row is None:
                row = MediaItem(
                    media_type=MediaType.tv,
                    external_id=external,
                    title=title,
                    year=year,
                    monitored=bool(s.get("monitored", monitor)),
                    status=ItemStatus.wanted,
                    file_path=path,
                    overview=(s.get("overview") or "")[:2000] or None,
                    quality_profile=series_type,  # stash series type until dedicated column used
                )
                db.add(row)
                db.flush()
                added += 1
            else:
                row.title = title
                if year:
                    row.year = year
                if path:
                    row.file_path = path
                row.quality_profile = series_type or row.quality_profile
                db.add(row)
                updated += 1
            db.flush()
            sid = s.get("id")
            if not sid:
                continue
            try:
                er = client.get("/api/v3/episode", params={"seriesId": sid})
                er.raise_for_status()
                episodes = er.json()
            except Exception as e:
                log.warning("Sonarr episodes for %s: %s", title, e)
                continue
            for ep in episodes:
                season = int(ep.get("seasonNumber") or 0)
                number = int(ep.get("episodeNumber") or 0)
                absolute = ep.get("absoluteEpisodeNumber")
                existing = (
                    db.query(Episode)
                    .filter(
                        Episode.media_item_id == row.id,
                        Episode.season_number == season,
                        Episode.episode_number == number,
                    )
                    .first()
                )
                has_file = bool(ep.get("hasFile"))
                title_ep = ep.get("title")
                if existing is None:
                    existing = Episode(
                        media_item_id=row.id,
                        season_number=season,
                        episode_number=number,
                        title=title_ep,
                        air_date=(ep.get("airDate") or None),
                        monitored=bool(ep.get("monitored", True)),
                        status=ItemStatus.downloaded if has_file else ItemStatus.wanted,
                        file_path=(ep.get("episodeFile") or {}).get("path") if has_file else None,
                    )
                    # absolute via overview stash if column missing — set if model has attr
                    if absolute is not None and hasattr(existing, "absolute_episode_number"):
                        existing.absolute_episode_number = int(absolute)
                    db.add(existing)
                    eps_added += 1
                else:
                    if title_ep:
                        existing.title = title_ep
                    if has_file:
                        existing.status = ItemStatus.downloaded
                        fp = (ep.get("episodeFile") or {}).get("path")
                        if fp:
                            existing.file_path = fp
                    if absolute is not None and hasattr(existing, "absolute_episode_number"):
                        existing.absolute_episode_number = int(absolute)
                    db.add(existing)
    db.commit()
    log_activity(db, "migrate_sonarr", f"Sonarr import series +{added} ~{updated}, eps +{eps_added}")
    try:
        sse_publish("migrate", {"source": "sonarr", "added": added, "updated": updated, "episodes": eps_added})
    except Exception:
        pass
    return {
        "ok": True,
        "source": "sonarr",
        "added": added,
        "updated": updated,
        "episodes_added": eps_added,
        "skipped": skipped,
        "total_series": len(series_list),
    }



def migrate_lidarr(db: Session, *, url: str, api_key: str, monitor: bool = True) -> dict:
    """Pull albums from Lidarr API into mediaos music items."""
    added = updated = skipped = 0
    with _client(url, api_key) as client:
        r = client.get("/api/v1/album")
        r.raise_for_status()
        albums = r.json()
    for a in albums:
        # Prefer MusicBrainz release-group id stored as external when present
        mbid = a.get("foreignAlbumId") or a.get("mbId") or a.get("id")
        title = a.get("title") or f"Album {mbid}"
        artist = None
        if isinstance(a.get("artist"), dict):
            artist = a["artist"].get("artistName") or a["artist"].get("name")
        artist = artist or a.get("artistName") or ""
        year = None
        if a.get("releaseDate"):
            try:
                year = int(str(a["releaseDate"])[:4])
            except Exception:
                pass
        has_file = bool(a.get("statistics", {}).get("trackFileCount") or a.get("grabbed"))
        path = a.get("path")
        # external_id: hash string to int stable-ish for non-int ids
        try:
            ext = int(mbid) if str(mbid).isdigit() else abs(hash(str(mbid))) % (10**9)
        except Exception:
            skipped += 1
            continue
        row = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.music, MediaItem.external_id == ext)
            .first()
        )
        if row is None:
            row = MediaItem(
                media_type=MediaType.music,
                external_id=ext,
                title=title if not artist else f"{artist} - {title}",
                artist_name=artist or None,
                year=year,
                monitored=bool(a.get("monitored", monitor)),
                status=ItemStatus.downloaded if has_file else ItemStatus.wanted,
                file_path=path if has_file else None,
            )
            db.add(row)
            added += 1
        else:
            row.title = title if not artist else f"{artist} - {title}"
            row.artist_name = artist or row.artist_name
            if year:
                row.year = year
            if has_file and path:
                row.file_path = path
                row.status = ItemStatus.downloaded
            row.monitored = bool(a.get("monitored", row.monitored))
            db.add(row)
            updated += 1
    db.commit()
    try:
        log_activity(db, "migrate", f"Lidarr import: +{added} ~{updated} skip {skipped}", media_type="music")
        sse_publish("activity", {"kind": "migrate", "source": "lidarr"})
    except Exception:
        pass
    return {"source": "lidarr", "added": added, "updated": updated, "skipped": skipped, "total": added + updated + skipped}


def migrate_readarr(db: Session, *, url: str, api_key: str, monitor: bool = True, audiobooks: bool = False) -> dict:
    """Pull books from Readarr API into mediaos books (or audiobooks)."""
    added = updated = skipped = 0
    mt = MediaType.audiobook if audiobooks else MediaType.book
    with _client(url, api_key) as client:
        r = client.get("/api/v1/book")
        r.raise_for_status()
        books = r.json()
    for b in books:
        foreign = b.get("foreignBookId") or b.get("id")
        title = b.get("title") or f"Book {foreign}"
        year = None
        if b.get("releaseDate"):
            try:
                year = int(str(b["releaseDate"])[:4])
            except Exception:
                pass
        author = None
        if isinstance(b.get("author"), dict):
            author = b["author"].get("authorName")
        author = author or b.get("authorTitle") or ""
        has_file = bool(b.get("statistics", {}).get("bookFileCount") or b.get("grabbed"))
        path = b.get("path")
        try:
            ext = int(foreign) if str(foreign).isdigit() else abs(hash(str(foreign))) % (10**9)
        except Exception:
            skipped += 1
            continue
        row = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == mt, MediaItem.external_id == ext)
            .first()
        )
        if row is None:
            row = MediaItem(
                media_type=mt,
                external_id=ext,
                title=title,
                artist_name=author or None,  # reuse artist_name for author
                year=year,
                monitored=bool(b.get("monitored", monitor)),
                status=ItemStatus.downloaded if has_file else ItemStatus.wanted,
                file_path=path if has_file else None,
            )
            db.add(row)
            added += 1
        else:
            row.title = title
            if author:
                row.artist_name = author
            if year:
                row.year = year
            if has_file and path:
                row.file_path = path
                row.status = ItemStatus.downloaded
            row.monitored = bool(b.get("monitored", row.monitored))
            db.add(row)
            updated += 1
    db.commit()
    try:
        log_activity(db, "migrate", f"Readarr import: +{added} ~{updated} skip {skipped}", media_type=mt.value)
        sse_publish("activity", {"kind": "migrate", "source": "readarr"})
    except Exception:
        pass
    return {"source": "readarr", "media_type": mt.value, "added": added, "updated": updated, "skipped": skipped, "total": added + updated + skipped}


def test_arr_connection(url: str, api_key: str, kind: str = "sonarr") -> dict:
    """Ping *arr system/status endpoint."""
    kind = (kind or "sonarr").lower()
    paths = {
        "sonarr": "/api/v3/system/status",
        "radarr": "/api/v3/system/status",
        "lidarr": "/api/v1/system/status",
        "readarr": "/api/v1/system/status",
        "prowlarr": "/api/v1/system/status",
        "bazarr": "/api/system/status",  # may vary
        "whisparr": "/api/v3/system/status",
    }
    path = paths.get(kind, "/api/v3/system/status")
    try:
        with _client(url, api_key) as client:
            r = client.get(path)
            ok = r.status_code < 400
            data = {}
            try:
                data = r.json()
            except Exception:
                data = {"raw": r.text[:200]}
            return {
                "ok": ok,
                "status_code": r.status_code,
                "kind": kind,
                "version": data.get("version") or data.get("appName"),
                "instanceName": data.get("instanceName") or data.get("appName"),
                "detail": data if ok else (data or r.text[:200]),
            }
    except Exception as e:
        return {"ok": False, "kind": kind, "error": str(e)}


def sync_prowlarr_indexers(
    db: Session,
    *,
    url: str,
    api_key: str,
    enable_new: bool = True,
    indexer_ids: list[int] | None = None,
) -> dict:
    """Import Prowlarr indexers as Torznab rows in mediaos.

    indexer_ids: optional allow-list of Prowlarr indexer IDs (from setup wizard pick).
    """
    from app.models import Indexer
    added = updated = skipped = 0
    allow = set(int(x) for x in indexer_ids) if indexer_ids else None
    with _client(url, api_key) as client:
        r = client.get("/api/v1/indexer")
        r.raise_for_status()
        indexers = r.json()
    for ix in indexers:
        ix_id = ix.get("id")
        if allow is not None and int(ix_id or -1) not in allow:
            skipped += 1
            continue
        if not ix.get("enable", True) and allow is None:
            skipped += 1
            continue
        name = ix.get("name") or f"Prowlarr-{ix_id}"
        # Build torznab URL: {prowlarr}/api/v1/indexer/{id}/api?apikey=
        proto = (ix.get("protocol") or "torrent").lower()
        kind = "newznab" if proto == "usenet" else "torznab"
        torznab_url = f"{url.rstrip('/')}/api/v1/indexer/{ix_id}/api"
        row = db.query(Indexer).filter(Indexer.name == name).first()
        if row is None:
            if not enable_new:
                skipped += 1
                continue
            row = Indexer(
                name=name,
                url=torznab_url,
                api_key=api_key,
                kind=kind,
                enabled=True,
                priority=int(ix.get("priority") or 25),
            )
            db.add(row)
            added += 1
        else:
            row.url = torznab_url
            row.api_key = api_key
            row.kind = kind
            row.enabled = True
            db.add(row)
            updated += 1
    db.commit()
    return {"source": "prowlarr", "added": added, "updated": updated, "skipped": skipped}
