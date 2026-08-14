"""Import from Sonarr/Radarr Postgres dumps or SQLite files (offline migrator).

Supports:
  - SQLite: path to sonarr.db / radarr.db
  - Postgres: DATABASE_URL-style connection string to a *arr database
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import Episode, ItemStatus, MediaItem, MediaType
from app.services.activity import log_activity

log = logging.getLogger(__name__)


def _connect_sqlite(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_pg(url: str):
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as e:
        raise RuntimeError("psycopg2-binary required for Postgres migrator — already in requirements.txt; rebuild image if ImportError persists") from e
    conn = psycopg2.connect(url)
    return conn, RealDictCursor


def migrate_radarr_sqlite(db: Session, path: str) -> dict:
    conn = _connect_sqlite(path)
    cur = conn.cursor()
    try:
        rows = cur.execute(
            "SELECT Id, Title, Year, TmdbId, Path, Monitored, Overview FROM Movies"
        ).fetchall()
    except sqlite3.Error:
        rows = cur.execute(
            "SELECT Id, Title, Year, TmdbId, Path, Monitored FROM Movies"
        ).fetchall()
    added = updated = skipped = 0
    for r in rows:
        tmdb = r["TmdbId"] if "TmdbId" in r.keys() else None
        if not tmdb:
            skipped += 1
            continue
        title = r["Title"]
        year = r["Year"] if "Year" in r.keys() else None
        path_v = r["Path"] if "Path" in r.keys() else None
        mon = bool(r["Monitored"]) if "Monitored" in r.keys() else True
        overview = r["Overview"] if "Overview" in r.keys() else None
        item = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.movie, MediaItem.external_id == int(tmdb))
            .first()
        )
        if item is None:
            db.add(MediaItem(
                media_type=MediaType.movie,
                external_id=int(tmdb),
                external_source="tmdb",
                title=title,
                year=year,
                monitored=mon,
                status=ItemStatus.downloaded if path_v else ItemStatus.wanted,
                file_path=path_v,
                overview=(overview or "")[:2000] or None,
            ))
            added += 1
        else:
            item.title = title
            if year:
                item.year = year
            if path_v:
                item.file_path = path_v
                item.status = ItemStatus.downloaded
            item.monitored = mon
            db.add(item)
            updated += 1
    db.commit()
    conn.close()
    log_activity(db, "migrate_radarr_db", f"SQLite Radarr +{added} ~{updated}")
    return {"ok": True, "source": "radarr_sqlite", "added": added, "updated": updated, "skipped": skipped}


def migrate_sonarr_sqlite(db: Session, path: str) -> dict:
    conn = _connect_sqlite(path)
    cur = conn.cursor()
    series_rows = cur.execute(
        "SELECT Id, Title, Year, TvdbId, Path, Monitored, SeriesType FROM Series"
    ).fetchall()
    added = updated = eps_added = skipped = 0
    for s in series_rows:
        tvdb = s["TvdbId"] if "TvdbId" in s.keys() else None
        if not tvdb:
            skipped += 1
            continue
        title = s["Title"]
        year = s["Year"] if "Year" in s.keys() else None
        path_v = s["Path"] if "Path" in s.keys() else None
        mon = bool(s["Monitored"]) if "Monitored" in s.keys() else True
        stype = (s["SeriesType"] if "SeriesType" in s.keys() else "standard") or "standard"
        sid = s["Id"]
        item = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.tv, MediaItem.external_id == int(tvdb))
            .first()
        )
        if item is None:
            item = MediaItem(
                media_type=MediaType.tv,
                external_id=int(tvdb),
                external_source="tvdb",
                tvdb_id=int(tvdb),
                title=title,
                year=year,
                monitored=mon,
                status=ItemStatus.wanted,
                file_path=path_v,
                series_type=str(stype).lower(),
            )
            db.add(item)
            db.flush()
            added += 1
        else:
            item.title = title
            item.series_type = str(stype).lower()
            if path_v:
                item.file_path = path_v
            db.add(item)
            updated += 1
            db.flush()
        try:
            eps = cur.execute(
                "SELECT Id, SeasonNumber, EpisodeNumber, AbsoluteEpisodeNumber, Title, AirDate, Monitored "
                "FROM Episodes WHERE SeriesId = ?",
                (sid,),
            ).fetchall()
        except sqlite3.Error:
            eps = cur.execute(
                "SELECT Id, SeasonNumber, EpisodeNumber, Title, AirDate, Monitored "
                "FROM Episodes WHERE SeriesId = ?",
                (sid,),
            ).fetchall()
        for e in eps:
            season = int(e["SeasonNumber"] or 0)
            number = int(e["EpisodeNumber"] or 0)
            absolute = e["AbsoluteEpisodeNumber"] if "AbsoluteEpisodeNumber" in e.keys() else None
            existing = (
                db.query(Episode)
                .filter(
                    Episode.media_item_id == item.id,
                    Episode.season_number == season,
                    Episode.episode_number == number,
                )
                .first()
            )
            if existing is None:
                ep = Episode(
                    media_item_id=item.id,
                    season_number=season,
                    episode_number=number,
                    title=e["Title"] if "Title" in e.keys() else None,
                    air_date=e["AirDate"] if "AirDate" in e.keys() else None,
                    monitored=bool(e["Monitored"]) if "Monitored" in e.keys() else True,
                    status=ItemStatus.wanted,
                )
                if absolute is not None:
                    ep.absolute_episode_number = int(absolute)
                db.add(ep)
                eps_added += 1
            elif absolute is not None:
                existing.absolute_episode_number = int(absolute)
                db.add(existing)
    db.commit()
    conn.close()
    log_activity(db, "migrate_sonarr_db", f"SQLite Sonarr +{added} eps+{eps_added}")
    return {
        "ok": True,
        "source": "sonarr_sqlite",
        "added": added,
        "updated": updated,
        "episodes_added": eps_added,
        "skipped": skipped,
    }


def migrate_arr_postgres(db: Session, *, url: str, kind: str) -> dict:
    """kind: radarr | sonarr — reads from live/restored *arr Postgres."""
    conn, cursor_factory = _connect_pg(url)
    cur = conn.cursor(cursor_factory=cursor_factory)
    if kind == "radarr":
        cur.execute('SELECT "Id", "Title", "Year", "TmdbId", "Path", "Monitored", "Overview" FROM "Movies"')
        rows = cur.fetchall()
        # reuse sqlite logic via dict-like rows
        tmp = "/tmp/_radarr_pg_bridge.db"
        # process inline
        added = updated = skipped = 0
        for r in rows:
            tmdb = r.get("TmdbId") or r.get("tmdbid")
            if not tmdb:
                skipped += 1
                continue
            item = (
                db.query(MediaItem)
                .filter(MediaItem.media_type == MediaType.movie, MediaItem.external_id == int(tmdb))
                .first()
            )
            title = r.get("Title") or r.get("title")
            path_v = r.get("Path") or r.get("path")
            if item is None:
                db.add(MediaItem(
                    media_type=MediaType.movie,
                    external_id=int(tmdb),
                    title=title,
                    year=r.get("Year") or r.get("year"),
                    monitored=bool(r.get("Monitored", True)),
                    status=ItemStatus.downloaded if path_v else ItemStatus.wanted,
                    file_path=path_v,
                ))
                added += 1
            else:
                item.title = title
                if path_v:
                    item.file_path = path_v
                    item.status = ItemStatus.downloaded
                db.add(item)
                updated += 1
        db.commit()
        conn.close()
        return {"ok": True, "source": "radarr_postgres", "added": added, "updated": updated, "skipped": skipped}
    # sonarr
    cur.execute('SELECT "Id", "Title", "Year", "TvdbId", "Path", "Monitored", "SeriesType" FROM "Series"')
    series_rows = cur.fetchall()
    added = updated = skipped = 0
    for s in series_rows:
        tvdb = s.get("TvdbId") or s.get("tvdbid")
        if not tvdb:
            skipped += 1
            continue
        item = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.tv, MediaItem.external_id == int(tvdb))
            .first()
        )
        title = s.get("Title") or s.get("title")
        if item is None:
            item = MediaItem(
                media_type=MediaType.tv,
                external_id=int(tvdb),
                title=title,
                year=s.get("Year"),
                monitored=bool(s.get("Monitored", True)),
                series_type=str(s.get("SeriesType") or "standard").lower(),
                file_path=s.get("Path"),
                status=ItemStatus.wanted,
            )
            db.add(item)
            added += 1
        else:
            item.title = title
            db.add(item)
            updated += 1
    db.commit()
    conn.close()
    return {"ok": True, "source": "sonarr_postgres", "added": added, "updated": updated, "skipped": skipped}


def migrate_radarr_extras_sqlite(db: Session, path: str) -> dict:
    """Import *arr Blocklist into mediaos Blocklist + History into Activity (fuller clone)."""
    import sqlite3
    from datetime import datetime, timezone
    from app.models import Activity, Blocklist

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    block = hist = 0

    # ── Blocklist ──────────────────────────────────────────────────────────
    rows = []
    for sql in (
        "SELECT TorrentInfoHash, SourceTitle, Message FROM Blocklist LIMIT 2000",
        "SELECT TorrentInfoHash, SourceTitle FROM Blocklist LIMIT 2000",
        "SELECT SourceTitle FROM Blocklist LIMIT 2000",
    ):
        try:
            rows = cur.execute(sql).fetchall()
            break
        except Exception:
            continue
    for r in rows:
        keys = r.keys()
        title = r["SourceTitle"] if "SourceTitle" in keys else None
        if not title:
            continue
        th = r["TorrentInfoHash"] if "TorrentInfoHash" in keys else None
        reason = r["Message"] if "Message" in keys else "imported from *arr"
        exists = (
            db.query(Blocklist)
            .filter(Blocklist.release_title == title[:500])
            .first()
        )
        if exists:
            continue
        db.add(Blocklist(
            release_title=title[:500],
            torrent_hash=(str(th)[:64] if th else None),
            reason=(str(reason)[:300] if reason else "imported from *arr"),
        ))
        block += 1

    # ── History → Activity ─────────────────────────────────────────────────
    rows = []
    for sql in (
        "SELECT SourceTitle, EventType, Date, SeriesId, MovieId, Quality FROM History ORDER BY Date DESC LIMIT 1000",
        "SELECT SourceTitle, EventType, Date FROM History ORDER BY Date DESC LIMIT 1000",
    ):
        try:
            rows = cur.execute(sql).fetchall()
            break
        except Exception:
            continue
    # *arr EventType: 1 grabbed, 3 imported, etc. — store raw + label
    evt_map = {
        1: "grabbed", 2: "download_failed", 3: "download_folder_imported",
        4: "download_ignored", 5: "download_failed", 6: "download_imported",
        7: "episode_file_deleted", 8: "episode_file_renamed",
    }
    for r in rows:
        keys = r.keys()
        title = r["SourceTitle"] if "SourceTitle" in keys else "history"
        raw_evt = r["EventType"] if "EventType" in keys else "history"
        try:
            evt = evt_map.get(int(raw_evt), f"arr_{raw_evt}")
        except Exception:
            evt = f"arr_{raw_evt}"
        media_type = None
        if "MovieId" in keys and r["MovieId"]:
            media_type = "movie"
        elif "SeriesId" in keys and r["SeriesId"]:
            media_type = "tv"
        created = None
        if "Date" in keys and r["Date"]:
            try:
                created = datetime.fromisoformat(str(r["Date"]).replace("Z", "+00:00"))
            except Exception:
                try:
                    created = datetime.strptime(str(r["Date"])[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                except Exception:
                    created = None
        act = Activity(
            event=str(evt)[:64],
            message=f"*arr history: {title}"[:500],
            media_type=media_type,
            release_title=str(title)[:300],
        )
        if created is not None:
            act.created_at = created
        db.add(act)
        hist += 1

    db.commit()
    conn.close()
    return {"blocklist_rows": block, "history_rows": hist}


def migrate_sonarr_extras_sqlite(db: Session, path: str) -> dict:
    return migrate_radarr_extras_sqlite(db, path)



