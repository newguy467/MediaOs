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
