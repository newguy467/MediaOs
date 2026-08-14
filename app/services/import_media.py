"""
Manual import from the downloads folder.

Scans DOWNLOADS_PATH for video files / folders, lets the user match them to
library items (or import with a provided title/year), and moves into the
movies or TV library using the same organize naming rules.
"""
from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Episode, ItemStatus, MediaItem, MediaType
from app.services.activity import log_activity
from app.services.organize import VIDEO_EXTENSIONS, _find_video_file, _folder_name, _sanitize
from app.services.quality.parser import parse_release_title

log = logging.getLogger(__name__)

_SE_RE = re.compile(r"[Ss](\d{1,2})[Ee](\d{1,3})")


def _downloads_root() -> Path:
    return Path(settings.downloads_path)


def scan_downloads() -> list[dict]:
    """List importable video files/folders under downloads (top-level entries)."""
    root = _downloads_root()
    if not root.exists():
        return []

    items: list[dict] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith("."):
            continue
        video = _find_video_file(entry)
        if not video:
            continue
        parsed = parse_release_title(entry.name)
        size = video.stat().st_size if video.exists() else 0
        items.append(
            {
                "path": str(entry),
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "video_file": str(video),
                "size": size,
                "parsed": {
                    "resolution": parsed.resolution,
                    "source": parsed.source,
                    "codec": parsed.codec,
                    "year": parsed.year,
                    "season": parsed.season,
                    "episode": parsed.episode,
                    "release_group": parsed.release_group,
                },
            }
        )
    return items


def _guess_series_episode(name: str) -> tuple[int | None, int | None]:
    m = _SE_RE.search(name)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _require_within_downloads(source_path: str) -> Path:
    """Resolve source_path and reject anything outside DOWNLOADS_PATH.

    Manual import is reachable by any user with `library.manage`, and
    source_path is a raw string from the request body — without this check
    it's an arbitrary-file-move primitive (any file the app process can
    read/write, anywhere on disk, could be moved into a served library
    folder or off of a path the app depends on).
    """
    root = _downloads_root().resolve()
    candidate = Path(source_path)
    resolved = candidate if candidate.is_absolute() else (root / candidate)
    resolved = resolved.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"source_path must be inside the downloads folder: {source_path}")
    return resolved


def import_to_movie(
    db: Session,
    *,
    source_path: str,
    media_item_id: int | None = None,
    title: str | None = None,
    year: int | None = None,
) -> dict:
    """
    Move a download into the movie library.
    Either attach to an existing MediaItem or require title (creates no DB row
    unless media_item_id is set — matching Radarr manual import behavior of
    linking to a tracked movie).
    """
    src = _require_within_downloads(source_path)
    if not src.exists():
        raise FileNotFoundError(f"Source not found: {source_path}")

    video = _find_video_file(src)
    if not video:
        raise ValueError("No video file found in source path")

    item: MediaItem | None = None
    if media_item_id:
        item = db.get(MediaItem, media_item_id)
        if not item or item.media_type != MediaType.movie:
            raise ValueError("media_item_id is not a movie")
        title = item.title
        year = item.year
    if not title:
        # fallback: use folder/file stem cleaned
        title = _sanitize(src.stem if src.is_file() else src.name)
        parsed = parse_release_title(src.name)
        if year is None:
            year = parsed.year

    folder = _folder_name(title, year)
    dest_dir = Path(settings.movies_library_path) / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{folder}{video.suffix.lower()}"

    if dest_path.exists():
        raise FileExistsError(f"Already exists: {dest_path}")

    shutil.move(str(video), str(dest_path))

    # Clean leftover folder if we emptied it
    if src.is_dir():
        try:
            if src.exists() and not any(src.rglob("*")):
                src.rmdir()
            elif src.exists():
                # remove empty dirs only; leave other files
                pass
        except OSError:
            pass

    if item:
        item.status = ItemStatus.downloaded
        item.file_path = str(dest_path)
        db.add(item)
        db.commit()
        log_activity(
            db,
            "imported",
            f"Manual import movie: {title} → {dest_path}",
            media_type="movie",
            media_item_id=item.id,
            release_title=src.name,
        )
        return {
            "ok": True,
            "dest": str(dest_path),
            "media_item_id": item.id,
            "title": title,
        }

    log_activity(
        db,
        "imported",
        f"Manual import (untracked) movie: {title} → {dest_path}",
        media_type="movie",
        release_title=src.name,
    )
    return {"ok": True, "dest": str(dest_path), "media_item_id": None, "title": title}


def import_to_episode(
    db: Session,
    *,
    source_path: str,
    episode_id: int | None = None,
    series_id: int | None = None,
    season: int | None = None,
    episode: int | None = None,
) -> dict:
    src = _require_within_downloads(source_path)
    if not src.exists():
        raise FileNotFoundError(f"Source not found: {source_path}")

    video = _find_video_file(src)
    if not video:
        raise ValueError("No video file found in source path")

    ep: Episode | None = None
    series: MediaItem | None = None

    if episode_id:
        ep = db.get(Episode, episode_id)
        if not ep:
            raise ValueError("episode not found")
        series = ep.series
        season = ep.season_number
        episode = ep.episode_number
    elif series_id and season is not None and episode is not None:
        series = db.get(MediaItem, series_id)
        if not series or series.media_type != MediaType.tv:
            raise ValueError("series_id is not a TV series")
        ep = (
            db.query(Episode)
            .filter(
                Episode.media_item_id == series_id,
                Episode.season_number == season,
                Episode.episode_number == episode,
            )
            .first()
        )
    else:
        # try parse SxxExx from name and require series_id
        gs, ge = _guess_series_episode(src.name)
        if series_id and gs is not None and ge is not None:
            season, episode = gs, ge
            series = db.get(MediaItem, series_id)
            if series:
                ep = (
                    db.query(Episode)
                    .filter(
                        Episode.media_item_id == series_id,
                        Episode.season_number == season,
                        Episode.episode_number == episode,
                    )
                    .first()
                )

    if not series or season is None or episode is None:
        raise ValueError("Need episode_id, or series_id + season + episode")

    series_folder = _folder_name(series.title, series.year)
    season_folder = f"Season {season:02d}"
    dest_dir = Path(settings.tv_library_path) / series_folder / season_folder
    dest_dir.mkdir(parents=True, exist_ok=True)

    file_stem = _sanitize(f"{series.title} - S{season:02d}E{episode:02d}")
    if ep and ep.title:
        file_stem = _sanitize(f"{file_stem} - {ep.title}")
    dest_path = dest_dir / f"{file_stem}{video.suffix.lower()}"

    if dest_path.exists():
        raise FileExistsError(f"Already exists: {dest_path}")

    shutil.move(str(video), str(dest_path))

    if ep:
        ep.status = ItemStatus.downloaded
        ep.file_path = str(dest_path)
        db.add(ep)
        db.commit()

    log_activity(
        db,
        "imported",
        f"Manual import TV: {series.title} S{season:02d}E{episode:02d} → {dest_path}",
        media_type="tv",
        media_item_id=series.id,
        release_title=src.name,
    )
    return {
        "ok": True,
        "dest": str(dest_path),
        "series_id": series.id,
        "episode_id": ep.id if ep else None,
        "season": season,
        "episode": episode,
    }
