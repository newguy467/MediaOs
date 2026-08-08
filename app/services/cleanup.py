"""
Cleanuparr-inspired download cleaner for mediaos.

Handles:
  - Strike system for stalled / slow / failed / malware downloads
  - Malware / junk filename patterns (*.lnk, *.zipx, sample spam, etc.)
  - Failed-import style cleanup (torrent done but item never organized)
  - Auto re-search after removal
  - Orphan torrent cleanup (qB category mediaos* with no matching Download row)

Designed as a native replacement for the core Cleanuparr queue-cleaner jobs
so most users do not need a separate Cleanuparr container.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.clients.qbittorrent import qbittorrent_client
from app.config import settings
from app.models import Download, Episode, ItemStatus, MediaItem, MediaType
from app.services.activity import log_activity
from app.services.blocklist import add_to_blocklist

log = logging.getLogger("mediaos.cleanup")

# Community-style junk / malware patterns (Cleanuparr malware blocker inspired)
_MALWARE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in (
        r"\.lnk$",
        r"\.zipx$",
        r"\.iso$",
        r"\.exe$",
        r"\.scr$",
        r"\.bat$",
        r"\.cmd$",
        r"\.js$",
        r"\.vbs$",
        r"\.wsf$",
        r"\.dll$",
        r"\.msi$",
        r"\.jar$",
        r"\.apk$",
        r"\.dmg$",
        r"\.appx$",
        r"password[\s._-]*txt",
        r"passw[o0]rd",
        r"rarbg\.com\.mp4$",
        r"rarbg\.com",
        r"sample[\s._-]*\.(mkv|mp4|avi)$",
        r"trailer[\s._-]*\.(mkv|mp4|avi)$",
        r"\.part\d+\.rar$",  # incomplete rar spam as sole content often junk
        r"www\.[a-z0-9-]+\.(mp4|mkv)$",
        r"downloaded[\s._-]*from",
        r"torrent[\s._-]*downloaded[\s._-]*from",
        r"\[www\.",
        r"crack\.(exe|zip|rar)$",
        r"keygen",
        r"codec[\s._-]*pack",
    )
]

_FAIL_STATES = {"error", "missingFiles", "unknown"}
_STALL_STATES = {
    "stalledDL",
    "stalledUP",
    "metaDL",
    "queuedDL",
    "allocating",
    "checkingDL",
    "checkingResumeData",
}
_MEDIAOS_CATEGORIES = (
    "mediaos",
    "mediaos-tv",
    "mediaos-music",
    "mediaos-books",
    "mediaos-audiobooks",
    "mediaos-comics",
    "mediaos-podcasts",
    "mediaos-youtube",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _max_strikes() -> int:
    return max(1, int(getattr(settings, "cleanup_max_strikes", 3) or 3))


def _stall_minutes() -> int:
    return max(5, int(getattr(settings, "cleanup_stall_minutes", 30) or 30))


def _min_speed_kb() -> float:
    return float(getattr(settings, "cleanup_min_speed_kb", 20) or 20)


def _enabled() -> bool:
    return bool(getattr(settings, "cleanup_enabled", True))


def _auto_search() -> bool:
    return bool(getattr(settings, "cleanup_auto_search", True))


def _looks_malware(name: str | None, files: list[str] | None = None) -> str | None:
    candidates = [name or ""]
    if files:
        candidates.extend(files)
    for c in candidates:
        for pat in _MALWARE_PATTERNS:
            if pat.search(c or ""):
                return pat.pattern
    return None


def _category_for(download: Download) -> str:
    item = download.media_item
    if download.episode_id:
        return "mediaos-tv"
    if item and item.media_type == MediaType.music:
        return "mediaos-music"
    if item and item.media_type == MediaType.book:
        return "mediaos-books"
    if item and item.media_type == MediaType.audiobook:
        return "mediaos-audiobooks"
    if item and item.media_type in (MediaType.comic, MediaType.manga):
        return "mediaos-comics"
    return "mediaos"


def _find_torrent(download: Download) -> dict | None:
    category = _category_for(download)
    try:
        torrents = qbittorrent_client.list_torrents(category=category)
        if download.torrent_hash:
            h = download.torrent_hash.lower()
            hit = next((t for t in torrents if (t.get("hash") or "").lower() == h), None)
            if hit:
                return hit
        title = (download.release_title or "").lower()
        if title:
            return next((t for t in torrents if (t.get("name") or "").lower() == title), None)
    except Exception as exc:
        log.warning("cleanup: list_torrents failed: %s", exc)
    return None


def _strike_reason(download: Download, torrent: dict | None) -> str | None:
    """Return a reason string if this download deserves a strike, else None."""
    if torrent is None:
        # No torrent found and still "grabbed" past timeout → strike
        added = download.added_at
        if added and added.tzinfo is None:
            added = added.replace(tzinfo=timezone.utc)
        timeout_h = float(getattr(settings, "download_timeout_hours", 24) or 24)
        if added and added < _utcnow() - timedelta(hours=timeout_h):
            return "missing_from_client"
        return None

    state = (torrent.get("state") or "").strip()
    progress = float(torrent.get("progress") or 0)
    # dlspeed is bytes/s in qB API
    dlspeed = float(torrent.get("dlspeed") or 0)
    eta = torrent.get("eta")  # seconds; 8640000 = qB "infinity"

    files: list[str] = []
    try:
        # optional: content paths if client exposes them
        content = torrent.get("content_path") or torrent.get("name") or ""
        if content:
            files.append(str(content))
    except Exception:
        pass

    mal = _looks_malware(torrent.get("name"), files)
    if mal:
        return f"malware_pattern:{mal}"

    if state in _FAIL_STATES:
        return f"error_state:{state}"

    if state in _STALL_STATES and progress < 0.99:
        added = download.added_at
        if added and added.tzinfo is None:
            added = added.replace(tzinfo=timezone.utc)
        if added and added < _utcnow() - timedelta(minutes=_stall_minutes()):
            return f"stalled:{state}"

    # Slow download (only when actively downloading and not nearly done)
    if state in {"downloading", "forcedDL"} and progress < 0.95:
        if dlspeed < _min_speed_kb() * 1024:
            added = download.added_at
            if added and added.tzinfo is None:
                added = added.replace(tzinfo=timezone.utc)
            if added and added < _utcnow() - timedelta(minutes=_stall_minutes()):
                return f"slow:{int(dlspeed/1024)}KB/s"
        if isinstance(eta, (int, float)) and eta > 0 and eta < 8640000:
            # eta > 2 days while still downloading
            if eta > 48 * 3600 and progress < 0.5:
                return f"high_eta:{int(eta/3600)}h"

    # Finished in client but never organized → failed import style
    if progress >= 0.999 and state in {"uploading", "stalledUP", "pausedUP", "queuedUP", "forcedUP"}:
        if download.status in {"grabbed", "downloading"}:
            # give organize a window first
            added = download.added_at
            if added and added.tzinfo is None:
                added = added.replace(tzinfo=timezone.utc)
            if added and added < _utcnow() - timedelta(hours=2):
                return "failed_import"

    return None


def _apply_strike(db: Session, download: Download, reason: str) -> dict:
    """Increment strike count; remove+blocklist+research when threshold hit."""
    strikes = int(download.strikes or 0) + 1
    download.strikes = strikes
    download.last_error = reason
    db.add(download)

    log_activity(
        db,
        "cleanup_strike",
        f"Strike {strikes}/{_max_strikes()} on download #{download.id}: {reason}",
        media_item_id=download.media_item_id,
        release_title=download.release_title,
    )

    result = {
        "download_id": download.id,
        "strikes": strikes,
        "reason": reason,
        "removed": False,
        "researched": False,
    }

    if strikes < _max_strikes():
        db.commit()
        return result

    # Threshold reached → remove from client, blocklist, reset parent, optional research
    torrent_hash = download.torrent_hash
    try:
        if torrent_hash:
            qbittorrent_client.delete_torrent(torrent_hash, delete_files=True)
    except Exception as exc:
        log.warning("cleanup: delete_torrent failed: %s", exc)

    try:
        add_to_blocklist(
            db,
            release_title=download.release_title or f"download-{download.id}",
            indexer=download.indexer,
            reason=f"cleanup:{reason}",
            media_item_id=download.media_item_id,
        )
    except Exception as exc:
        log.warning("cleanup: blocklist failed: %s", exc)

    item = download.media_item
    episode = download.episode
    if episode is not None:
        episode.status = ItemStatus.wanted
        db.add(episode)
    elif item is not None and item.media_type != MediaType.tv:
        item.status = ItemStatus.wanted
        db.add(item)

    download.status = "failed"
    db.add(download)
    db.commit()
    result["removed"] = True

    if _auto_search() and item is not None:
        try:
            from app.services.search import (
                find_best_episode_release,
                find_best_movie_release,
            )
            from app.services.grab import grab_release

            if episode is not None:
                rel = find_best_episode_release(episode, db=db)
                if rel:
                    grab_release(db, item, rel)
                    result["researched"] = True
            elif item.media_type == MediaType.movie:
                rel = find_best_movie_release(item, db=db)
                if rel:
                    grab_release(db, item, rel)
                    result["researched"] = True
        except Exception as exc:
            log.warning("cleanup: auto-search failed: %s", exc)

    log_activity(
        db,
        "cleanup_remove",
        f"Removed download #{download.id} after {strikes} strikes ({reason})",
        media_item_id=download.media_item_id,
        release_title=download.release_title,
    )
    return result


def run_queue_cleaner(db: Session) -> dict:
    """Main Cleanuparr-style queue cleaner tick."""
    if not _enabled():
        return {"enabled": False, "checked": 0, "struck": 0, "removed": 0}

    rows = (
        db.query(Download)
        .options(joinedload(Download.media_item), joinedload(Download.episode))
        .filter(Download.status.in_(["grabbed", "downloading"]))
        .order_by(Download.added_at.asc())
        .limit(200)
        .all()
    )

    struck = 0
    removed = 0
    details: list[dict] = []

    for d in rows:
        torrent = _find_torrent(d)
        if bool(getattr(settings, "cleanup_skip_private", True)) and _is_private_torrent(torrent):
            continue
        reason = _strike_reason(d, torrent)
        if not reason:
            continue
        res = _apply_strike(db, d, reason)
        struck += 1
        if res.get("removed"):
            removed += 1
        details.append(res)

    return {
        "enabled": True,
        "checked": len(rows),
        "struck": struck,
        "removed": removed,
        "details": details[:50],
    }


def run_orphan_cleaner(db: Session) -> dict:
    """Remove qB torrents in mediaos* categories that have no Download row."""
    if not _enabled() or not bool(getattr(settings, "cleanup_orphans", True)):
        return {"enabled": False, "orphans": 0}

    known_hashes: set[str] = set()
    for h, in db.query(Download.torrent_hash).filter(Download.torrent_hash.isnot(None)).all():
        if h:
            known_hashes.add(h.lower())

    orphans: list[dict] = []
    for cat in _MEDIAOS_CATEGORIES:
        try:
            torrents = qbittorrent_client.list_torrents(category=cat)
        except Exception:
            continue
        for t in torrents:
            h = (t.get("hash") or "").lower()
            if not h or h in known_hashes:
                continue
            # Only touch completed or stalled orphans older than 1 day
            added_on = t.get("added_on")  # unix
            if added_on:
                try:
                    age = _utcnow() - datetime.fromtimestamp(int(added_on), tz=timezone.utc)
                    if age < timedelta(days=1):
                        continue
                except Exception:
                    pass
            orphans.append({"hash": h, "name": t.get("name"), "category": cat})
            try:
                if bool(getattr(settings, "cleanup_orphans_delete", False)):
                    qbittorrent_client.delete_torrent(h, delete_files=False)
            except Exception as exc:
                log.warning("cleanup orphan delete failed: %s", exc)

    if orphans:
        log_activity(
            db,
            "cleanup_orphans",
            f"Found {len(orphans)} orphan torrent(s) in mediaos categories",
        )
        db.commit()

    return {"enabled": True, "orphans": len(orphans), "items": orphans[:50]}




def _is_private_torrent(torrent: dict | None) -> bool:
    if not torrent:
        return False
    # qB exposes private via properties; list endpoint may include "tags" or category hints
    if torrent.get("private") is True:
        return True
    tags = (torrent.get("tags") or "") + " " + (torrent.get("category") or "")
    if re.search(r"\bprivate\b", tags, re.I):
        return True
    # trackers list if present
    trackers = torrent.get("trackers") or []
    if isinstance(trackers, list):
        for tr in trackers:
            url = (tr.get("url") if isinstance(tr, dict) else str(tr)) or ""
            if "private" in url.lower():
                return True
    return False


def run_seed_cleaner(db: Session) -> dict:
    """Remove completed mediaos torrents that met seeding goals (Cleanuparr download-cleaner)."""
    if not _enabled() or not bool(getattr(settings, "cleanup_seed_enabled", True)):
        return {"enabled": False, "checked": 0, "removed": 0}

    ratio_target = float(getattr(settings, "cleanup_seed_ratio", 2.0) or 2.0)
    min_minutes = int(getattr(settings, "cleanup_seed_minutes", 10080) or 10080)
    require_both = bool(getattr(settings, "cleanup_seed_require_both", False))
    skip_private = bool(getattr(settings, "cleanup_skip_private", True))

    rows = (
        db.query(Download)
        .options(joinedload(Download.media_item))
        .filter(Download.status.in_(["grabbed", "downloading", "completed", "imported", "done"]))
        .limit(300)
        .all()
    )
    checked = 0
    removed = 0
    details: list[dict] = []

    for d in rows:
        torrent = _find_torrent(d)
        if not torrent:
            continue
        progress = float(torrent.get("progress") or 0)
        if progress < 0.999:
            continue
        checked += 1
        if skip_private and _is_private_torrent(torrent):
            continue

        ratio = float(torrent.get("ratio") or 0)
        # seeding_time in seconds (qB)
        seeding_time = float(torrent.get("seeding_time") or 0)
        seeding_minutes = seeding_time / 60.0

        ratio_ok = ratio >= ratio_target
        time_ok = seeding_minutes >= min_minutes
        if require_both:
            meets = ratio_ok and time_ok
        else:
            meets = ratio_ok or time_ok
        if not meets:
            continue

        h = d.torrent_hash or torrent.get("hash")
        try:
            if h:
                qbittorrent_client.delete_torrent(h, delete_files=False)
        except Exception as exc:
            log.warning("seed cleaner delete failed: %s", exc)
            continue
        d.status = "seeded_removed"
        db.add(d)
        removed += 1
        details.append({
            "download_id": d.id,
            "title": d.release_title,
            "ratio": ratio,
            "seeding_minutes": int(seeding_minutes),
        })
        log_activity(
            db,
            "cleanup_seed",
            f"Removed completed torrent after seeding goals (ratio={ratio:.2f}, minutes={int(seeding_minutes)}): {d.release_title}",
            media_item_id=d.media_item_id,
            release_title=d.release_title,
        )

    if removed:
        db.commit()
    return {"enabled": True, "checked": checked, "removed": removed, "details": details[:50]}


def run_cleanup_cycle(db: Session) -> dict:
    """Combined tick used by the scheduler."""
    queue = run_queue_cleaner(db)
    orphans = run_orphan_cleaner(db)
    seeds = run_seed_cleaner(db)
    return {"queue": queue, "orphans": orphans, "seeds": seeds}
