"""Major gap helpers: identity, status transitions, attention, path maps, metadata refresh."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Download, ItemStatus, MediaItem, MediaType, PathMap

log = logging.getLogger(__name__)

# Canonical item lifecycle (wanted → grabbed → downloading → downloaded/organized | failed)
STATUS_FLOW = {
    "wanted": {"grabbed", "downloading", "failed"},
    "missing": {"grabbed", "downloading", "failed"},
    "grabbed": {"downloading", "downloaded", "failed"},
    "downloading": {"downloaded", "failed"},
    "downloaded": {"downloaded"},  # terminal success (organize may keep same)
    "failed": {"wanted", "grabbed", "downloading"},
}


def find_duplicates(db: Session, *, media_type: str | None = None, limit: int = 100) -> list[dict]:
    """Group items sharing external_id or normalized title+year."""
    q = db.query(MediaItem)
    if media_type:
        try:
            q = q.filter(MediaItem.media_type == MediaType(media_type))
        except Exception:
            pass
    rows = q.order_by(MediaItem.id).limit(5000).all()
    by_ext: dict[str, list] = {}
    by_title: dict[str, list] = {}
    for it in rows:
        if it.external_id:
            key = f"{it.media_type.value if hasattr(it.media_type,'value') else it.media_type}:{it.external_source or ''}:{it.external_id}"
            by_ext.setdefault(key, []).append(it)
        title_key = f"{(it.title or '').strip().lower()}|{(it.year or '')}|{it.media_type.value if hasattr(it.media_type,'value') else it.media_type}"
        by_title.setdefault(title_key, []).append(it)
    out = []
    seen = set()
    for src, groups in (("external_id", by_ext), ("title_year", by_title)):
        for k, items in groups.items():
            if len(items) < 2:
                continue
            ids = tuple(sorted(i.id for i in items))
            if ids in seen:
                continue
            seen.add(ids)
            out.append({
                "reason": src,
                "key": k,
                "ids": list(ids),
                "titles": [i.title for i in items],
            })
            if len(out) >= limit:
                return out
    return out


def transition_status(item: MediaItem, new_status: str, *, force: bool = False) -> str:
    cur = item.status.value if hasattr(item.status, "value") else str(item.status or "")
    allowed = STATUS_FLOW.get(cur, set())
    if not force and allowed and new_status not in allowed and new_status != cur:
        log.info("status transition blocked %s → %s for item %s", cur, new_status, item.id)
        return cur
    try:
        item.status = ItemStatus(new_status)
    except Exception:
        item.status = new_status  # type: ignore
    return new_status


def needs_attention(db: Session, limit: int = 40) -> list[dict]:
    """Failed downloads, failed items, empty stream paths — dashboard strip."""
    alerts = []
    fails = (
        db.query(Download)
        .filter(Download.status.in_(["failed", "error"]))
        .order_by(Download.id.desc())
        .limit(limit)
        .all()
    )
    for d in fails:
        alerts.append({
            "kind": "download_failed",
            "id": d.id,
            "title": getattr(d, "release_title", None) or getattr(d, "title", None) or f"download {d.id}",
            "detail": getattr(d, "error", None) or d.status,
        })
    bad_items = (
        db.query(MediaItem)
        .filter(MediaItem.status == ItemStatus.failed)
        .order_by(MediaItem.id.desc())
        .limit(limit)
        .all()
    )
    for it in bad_items:
        alerts.append({
            "kind": "item_failed",
            "id": it.id,
            "title": it.title,
            "detail": it.status.value if hasattr(it.status, "value") else str(it.status),
            "media_type": it.media_type.value if hasattr(it.media_type, "value") else str(it.media_type),
        })
    return alerts[:limit]


def apply_path_map(db: Session, path: str, media_type: str | None = None) -> str:
    if not path:
        return path
    q = db.query(PathMap).filter(PathMap.enabled.is_(True))
    maps = q.all()
    best = None
    for m in maps:
        if media_type and m.media_type and m.media_type != media_type:
            continue
        if path.startswith(m.container_prefix):
            if best is None or len(m.container_prefix) > len(best.container_prefix):
                best = m
    if not best:
        return path
    return best.host_prefix + path[len(best.container_prefix):]


def dry_run_organize_path(db: Session, container_path: str, media_type: str | None = None) -> dict:
    mapped = apply_path_map(db, container_path, media_type)
    return {"container": container_path, "mapped": mapped, "changed": mapped != container_path}
