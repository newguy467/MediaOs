"""Library storage maintenance stats (MediaOs storage page parity)."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from app.config import settings


def _dir_stats(path: str) -> dict:
    root = Path(path) if path else None
    if not root or not root.exists():
        return {"path": path, "exists": False, "files": 0, "bytes": 0}
    files = 0
    total = 0
    largest = []
    try:
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                fp = Path(dirpath) / name
                try:
                    sz = fp.stat().st_size
                except OSError:
                    continue
                files += 1
                total += sz
                largest.append((sz, str(fp)))
        largest.sort(reverse=True)
        largest = [{"path": p, "bytes": b} for b, p in largest[:15]]
    except Exception:
        largest = []
    usage = None
    try:
        du = shutil.disk_usage(root)
        usage = {"total": du.total, "used": du.used, "free": du.free}
    except Exception:
        pass
    return {
        "path": str(root),
        "exists": True,
        "files": files,
        "bytes": total,
        "largest": largest,
        "disk": usage,
    }


def library_storage() -> dict:
    libs = {
        "movies": settings.movies_library_path,
        "tv": settings.tv_library_path,
        "music": settings.music_library_path,
        "books": settings.books_library_path,
        "audiobooks": settings.audiobooks_library_path,
        "downloads": settings.downloads_path,
    }
    return {k: _dir_stats(v) for k, v in libs.items()}


# Folders shown in the dashboard "Storage" widget. Unlike library_storage()
# above, this intentionally does NOT walk every file — libraries can be
# multi-TB, and the dashboard widget polls periodically, so it only asks the
# filesystem for the mount's total/used/free (cheap, O(1) per folder).
_DISK_OVERVIEW_FOLDERS: list[tuple[str, str, str]] = [
    # (id, label, settings attribute)
    ("movies", "Movies", "movies_library_path"),
    ("tv", "TV", "tv_library_path"),
    ("music", "Music", "music_library_path"),
    ("books", "Books", "books_library_path"),
    ("audiobooks", "Audiobooks", "audiobooks_library_path"),
    ("podcasts", "Podcasts", "podcasts_library_path"),
    ("comics", "Comics", "comics_library_path"),
    ("manga", "Manga", "manga_library_path"),
    ("youtube", "YouTube", "youtube_library_path"),
    ("games", "Games", "games_library_path"),
    ("adult", "Adult", "adult_library_path"),
    ("downloads", "Downloads", "downloads_path"),
]


def disk_usage_overview() -> dict:
    """Fast per-folder disk usage (total/used/free) for the dashboard widget.

    Folders that don't exist (module disabled, path not mounted) or that
    share a filesystem with an already-seen path are collapsed: the caller
    gets one row per distinct mount rather than N duplicate bars all
    reporting the same total, which is what you'd get running disk_usage()
    on several bind-mounts of the same host filesystem.
    """
    seen_mounts: dict[tuple[int, int], str] = {}  # (total, free) proxy -> first id with that usage
    rows = []
    for fid, label, attr in _DISK_OVERVIEW_FOLDERS:
        path = getattr(settings, attr, None)
        root = Path(path) if path else None
        if not root or not root.exists():
            continue
        try:
            du = shutil.disk_usage(root)
        except Exception:
            continue
        mount_key = (du.total, du.free)
        if mount_key in seen_mounts:
            continue  # same underlying filesystem as an earlier row
        seen_mounts[mount_key] = fid
        rows.append({
            "id": fid,
            "label": label,
            "path": str(root),
            "total": du.total,
            "used": du.used,
            "free": du.free,
        })

    # App data + config (bind-mounted separately from library folders)
    for fid, label, path in (
        ("app_data", "App Data", "/app/data"),
        ("config", "Config", "/config"),
    ):
        root = Path(path)
        if not root.exists():
            continue
        try:
            du = shutil.disk_usage(root)
        except Exception:
            continue
        mount_key = (du.total, du.free)
        if mount_key in seen_mounts:
            continue
        seen_mounts[mount_key] = fid
        rows.append({
            "id": fid,
            "label": label,
            "path": str(root),
            "total": du.total,
            "used": du.used,
            "free": du.free,
        })

    return {"folders": rows}
