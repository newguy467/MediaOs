"""Detect failed/stalled qB torrents → blocklist + reset item for retry."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.clients.qbittorrent import qbittorrent_client
from app.config import settings
from app.models import Download, Episode, ItemStatus, MediaItem, MediaType
from app.services.activity import log_activity
from app.services.blocklist import add_to_blocklist
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

# qBittorrent states that mean failure
_FAIL_STATES = {
    "error",
    "missingFiles",
    "unknown",
}


def process_failed_downloads(db: Session) -> int:
    """
    Look at grabbed downloads; if torrent is in error state or stalled past
    timeout with 0 progress, fail + blocklist + reset parent to wanted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.download_timeout_hours)
    downloads = db.query(Download).filter(Download.status == "grabbed").all()
    fixed = 0

    for d in downloads:
        category = "mediaos-tv" if d.episode_id else (
            "mediaos-music"
            if d.media_item and d.media_item.media_type == MediaType.music
            else "mediaos"
        )
        torrent = None
        try:
            torrents = qbittorrent_client.list_torrents(category=category)
            if d.torrent_hash:
                torrent = next((t for t in torrents if t.get("hash") == d.torrent_hash), None)
            if not torrent:
                title = (d.release_title or "").lower()
                torrent = next(
                    (t for t in torrents if (t.get("name") or "").lower() == title),
                    None,
                )
        except Exception as exc:
            log.warning("list_torrents failed: %s", exc)
            continue

        state = (torrent or {}).get("state", "")
        progress = float((torrent or {}).get("progress") or 0)
        added = d.added_at
        if added and added.tzinfo is None:
            added = added.replace(tzinfo=timezone.utc)

        is_error = state in _FAIL_STATES
        is_stale_zero = (added and added < cutoff and progress < 0.01)

        if not is_error and not is_stale_zero:
            continue

        reason = f"qB state={state}" if is_error else "stale zero progress"
        d.status = "failed"
        db.add(d)

        try:
            add_to_blocklist(
                db,
                d.release_title,
                reason=reason,
                torrent_hash=d.torrent_hash,
                media_item_id=d.media_item_id,
            )
        except Exception:
            pass

        if d.episode_id and d.episode:
            d.episode.status = ItemStatus.wanted
            d.episode.last_searched_at = None
            db.add(d.episode)
        elif d.media_item:
            d.media_item.status = ItemStatus.wanted
            d.media_item.last_searched_at = None
            db.add(d.media_item)

        try:
            if d.torrent_hash:
                qbittorrent_client.delete_torrent(d.torrent_hash, delete_files=True)
        except Exception:
            pass

        log_activity(
            db,
            "failed",
            f"Download failed ({reason}): {d.release_title}",
            media_item_id=d.media_item_id,
            release_title=d.release_title,
        )
        fixed += 1

    if fixed:
        db.commit()
        log.info("Processed %s failed downloads", fixed)
    return fixed


def release_in_cooldown(db, release_title: str) -> bool:
    """True if this release was blocklisted/failed within cooldown window (MediaOs-style)."""
    from app.models import Blocklist
    hours = float(getattr(settings, "failed_download_cooldown_hours", 1) or 1)
    if hours <= 0:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        q = (
            db.query(Blocklist)
            .filter(Blocklist.release_title == release_title)
            .order_by(Blocklist.added_at.desc())
            .first()
        )
        if not q:
            return False
        created = q.added_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return bool(created and created >= cutoff)
    except Exception:
        return False
