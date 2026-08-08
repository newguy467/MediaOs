"""
Hunt engine — aggressive missing / cutoff / upgrade logic (Huntarr-inspired).
Wired to search + grab services with rate-limit awareness.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import ItemStatus, MediaItem, MediaType

log = logging.getLogger("mediaos.hunt")


def plan_hunt(
    db: Session,
    *,
    media_types: list[str] | None = None,
    only_monitored: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    q = db.query(MediaItem)
    if only_monitored:
        q = q.filter(MediaItem.monitored.is_(True))
    if media_types:
        types = []
        for t in media_types:
            try:
                types.append(MediaType(t))
            except Exception:
                pass
        if types:
            q = q.filter(MediaItem.media_type.in_(types))
    q = q.filter(MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.downloaded, ItemStatus.failed]))
    items = q.order_by(MediaItem.last_searched_at.nullsfirst(), MediaItem.id.desc()).limit(limit).all()

    plan = []
    for it in items:
        st = it.status.value if it.status else None
        reason = "missing" if st in ("wanted", "missing", "failed") else "upgrade_check"
        plan.append({
            "id": it.id,
            "media_type": it.media_type.value if it.media_type else None,
            "title": it.title,
            "year": it.year,
            "status": st,
            "reason": reason,
            "quality_profile": it.quality_profile,
            "last_searched_at": it.last_searched_at.isoformat() if it.last_searched_at else None,
        })
    return plan


def _search_one(db: Session, item: MediaItem) -> dict[str, Any]:
    from app.services.search import (
        find_best_book_release,
        find_best_comic_release,
        find_best_movie_release,
        find_best_music_release,
    )
    from app.services.grab import grab_release

    mt = item.media_type
    release = None
    try:
        if mt == MediaType.movie:
            release = find_best_movie_release(item, db=db)
        elif mt == MediaType.music:
            release = find_best_music_release(item, db=db)
        elif mt == MediaType.book:
            release = find_best_book_release(item, db=db)
        elif mt in (MediaType.comic, MediaType.manga):
            release = find_best_comic_release(item, db=db)
        # TV episodes handled by existing scheduler episode path
    except Exception as e:
        log.warning("hunt search failed for %s: %s", item.title, e)
        return {"id": item.id, "ok": False, "error": str(e)}

    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()

    if not release:
        return {"id": item.id, "ok": True, "grabbed": False, "title": item.title}

    try:
        grab_release(db, item, release)
        return {
            "id": item.id,
            "ok": True,
            "grabbed": True,
            "title": item.title,
            "release": release.get("title"),
        }
    except Exception as e:
        log.warning("hunt grab failed for %s: %s", item.title, e)
        db.rollback()
        return {"id": item.id, "ok": False, "error": str(e)}


def run_hunt_batch(db: Session, plan: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    grabbed = 0
    for entry in plan:
        item = db.get(MediaItem, entry["id"])
        if not item:
            continue
        # Skip pure upgrade_check for now unless missing
        if entry.get("reason") == "upgrade_check" and item.status == ItemStatus.downloaded:
            continue
        r = _search_one(db, item)
        results.append(r)
        if r.get("grabbed"):
            grabbed += 1
    return {
        "planned": len(plan),
        "processed": len(results),
        "grabbed": grabbed,
        "results": results[:50],
        "message": f"Hunt processed {len(results)} items, grabbed {grabbed}",
    }


def run_hunt_cycle(
    *,
    media_types: list[str] | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    """Scheduler entrypoint."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        plan = plan_hunt(db, media_types=media_types, limit=limit)
        return run_hunt_batch(db, plan)
    except Exception as e:
        log.exception("hunt cycle failed")
        return {"ok": False, "error": str(e)}
    finally:
        db.close()
