"""Real-time library file watch (watchdog/inotify) with poll fallback."""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models import Episode, ItemStatus, MediaItem
from app.services.naming import parse_ids_from_path

log = logging.getLogger(__name__)

_VIDEO_EXT = {".mkv", ".mp4", ".avi", ".m4v", ".ts", ".m2ts", ".wmv", ".mov"}
_AUDIO_EXT = {".flac", ".mp3", ".m4a", ".opus", ".ogg", ".wav", ".aac"}
_BOOK_EXT = {".epub", ".mobi", ".pdf", ".azw3", ".cbz", ".cbr"}
_MEDIA_EXT = _VIDEO_EXT | _AUDIO_EXT | _BOOK_EXT

_state: dict[str, float] = {}
_thread: threading.Thread | None = None
_observer = None
_stop = threading.Event()
_mode = "none"


def _library_roots() -> list[str]:
    roots = []
    for path in (
        settings.movies_library_path,
        settings.tv_library_path,
        settings.music_library_path,
        settings.books_library_path,
        settings.audiobooks_library_path,
    ):
        if path and os.path.isdir(path):
            roots.append(path)
    return roots


def _is_media(path: str) -> bool:
    return Path(path).suffix.lower() in _MEDIA_EXT


def _reconcile_removed(paths: set[str]) -> int:
    if not paths:
        return 0
    db = SessionLocal()
    n = 0
    try:
        for path in paths:
            for item in db.query(MediaItem).filter(MediaItem.file_path == path).all():
                if item.status == ItemStatus.downloaded:
                    item.status = ItemStatus.missing
                    item.file_path = None
                    n += 1
            for ep in db.query(Episode).filter(Episode.file_path == path).all():
                if ep.status == ItemStatus.downloaded:
                    ep.status = ItemStatus.missing
                    ep.file_path = None
                    n += 1
        db.commit()
    except Exception:
        db.rollback()
        log.exception("watch remove reconcile")
    finally:
        db.close()
    return n


def _match_item_by_ids(db, path: str, candidates: list) -> object | None:
    """Prefer exact external-id match from IDs embedded in path (Radarr/Sonarr style)."""
    ids = parse_ids_from_path(path)
    if not ids:
        return None
    for item in candidates:
        src = (item.external_source or "").lower()
        try:
            eid = int(item.external_id) if item.external_id and str(item.external_id).isdigit() else None
        except (TypeError, ValueError):
            eid = None
        if eid is None:
            continue
        if src == "tmdb" and ids.get("tmdb") == eid:
            return item
        if src == "tvdb" and ids.get("tvdb") == eid:
            return item
        if src == "imdb" and ids.get("imdb") == eid:
            return item
    return None


def _reconcile_added(paths: set[str]) -> int:
    if not paths:
        return 0
    db = SessionLocal()
    n = 0
    try:
        candidates = (
            db.query(MediaItem)
            .filter(
                MediaItem.status.in_([ItemStatus.missing, ItemStatus.wanted, ItemStatus.downloaded]),
                MediaItem.monitored.is_(True),
            )
            .limit(1200)
            .all()
        )
        for path in paths:
            if db.query(MediaItem).filter(MediaItem.file_path == path).first():
                continue
            if db.query(Episode).filter(Episode.file_path == path).first():
                continue
            # 1) ID-in-path match (strongest)
            matched = _match_item_by_ids(db, path, candidates)
            if matched is not None:
                # Rename tracking: update path even if previously pointed elsewhere
                old = matched.file_path
                matched.file_path = path
                matched.status = ItemStatus.downloaded
                n += 1
                if old and old != path:
                    log.info("Rename tracked: %s → %s (id match)", old, path)
                continue
            # 2) Fuzzy title token match for missing/wanted only
            base = Path(path).stem.lower()
            for item in candidates:
                if item.status == ItemStatus.downloaded and item.file_path:
                    continue
                title = (item.title or "").lower()
                if len(title) < 3:
                    continue
                safe = "".join(c if c.isalnum() or c.isspace() else " " for c in title)
                tokens = [t for t in safe.split() if len(t) > 2][:3]
                if tokens and all(t in base or t in path.lower() for t in tokens):
                    item.file_path = path
                    item.status = ItemStatus.downloaded
                    n += 1
                    break
        db.commit()
    except Exception:
        db.rollback()
        log.exception("watch add reconcile")
    finally:
        db.close()
    return n


def _on_created(path: str):
    if not _is_media(path):
        return
    log.info("Library watch CREATE %s", path)
    _reconcile_added({path})
    try:
        _state[path] = os.path.getmtime(path)
    except OSError:
        pass


def _on_deleted(path: str):
    log.info("Library watch DELETE %s", path)
    _reconcile_removed({path})
    _state.pop(path, None)


def _start_watchdog(roots: list[str]) -> bool:
    global _observer, _mode
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        log.warning("watchdog not installed; falling back to poll")
        return False

    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                _on_created(event.src_path)

        def on_moved(self, event):
            if not event.is_directory:
                _on_deleted(event.src_path)
                _on_created(event.dest_path)

        def on_deleted(self, event):
            if not event.is_directory:
                _on_deleted(event.src_path)

    obs = Observer()
    handler = Handler()
    for root in roots:
        obs.schedule(handler, root, recursive=True)
    obs.daemon = True
    obs.start()
    _observer = obs
    _mode = "inotify"
    log.info("Library watch: watchdog/inotify on %s", roots)
    return True


def poll_once() -> dict:
    """Full tree scan (also used as fallback mode)."""
    global _state
    current: dict[str, float] = {}
    for root in _library_roots():
        for dirpath, _, files in os.walk(root):
            for name in files:
                fp = os.path.join(dirpath, name)
                if not _is_media(fp):
                    continue
                try:
                    current[fp] = os.path.getmtime(fp)
                except OSError:
                    pass
    if not _state:
        _state = current
        return {"mode": _mode, "initialized": True, "files": len(current)}
    added = set(current) - set(_state)
    removed = set(_state) - set(current)
    _state = current
    return {
        "mode": _mode,
        "added": len(added),
        "removed": len(removed),
        "marked_missing": _reconcile_removed(removed),
        "restored": _reconcile_added(added),
        "tracked": len(current),
    }


def _poll_loop(interval: float):
    global _mode
    if _mode != "inotify":
        _mode = "poll"
    log.info("Library watch poll loop interval=%s", interval)
    while not _stop.is_set():
        try:
            if _mode == "poll":
                r = poll_once()
                if r.get("added") or r.get("removed"):
                    log.info("Library poll: %s", r)
        except Exception:
            log.exception("poll tick")
        _stop.wait(interval)


def start_library_watch(interval_seconds: float | None = None):
    global _thread
    if not getattr(settings, "library_watch_enabled", True):
        return
    if _thread and _thread.is_alive():
        return
    roots = _library_roots()
    if not roots:
        log.info("Library watch: no roots mounted yet")
        return
    interval = float(interval_seconds or getattr(settings, "library_watch_interval_seconds", 30) or 30)
    _stop.clear()
    if not _start_watchdog(roots):
        _thread = threading.Thread(target=_poll_loop, args=(interval,), name="library-watch", daemon=True)
        _thread.start()
    else:
        # light poll as safety net every 5 minutes
        _thread = threading.Thread(target=_poll_loop, args=(max(interval, 300),), name="library-watch-safety", daemon=True)
        _thread.start()


def stop_library_watch():
    global _observer
    _stop.set()
    if _observer is not None:
        try:
            _observer.stop()
            _observer.join(timeout=5)
        except Exception:
            pass
        _observer = None


def status() -> dict:
    return {"mode": _mode, "tracked": len(_state), "roots": _library_roots()}
