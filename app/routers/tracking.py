"""
Unified Tracking layer (Yamtrack-inspired, MediaOS v2).
"""
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_permission
from app.models import TrackedItem

log = logging.getLogger(__name__)

TRACKING_STATUSES = [
    {"id": "planned", "label": "Wanted / Planned"},
    {"id": "in_progress", "label": "In Progress"},
    {"id": "completed", "label": "Completed"},
    {"id": "on_hold", "label": "On Hold"},
    {"id": "dropped", "label": "Dropped"},
]

router = APIRouter(prefix="/tracking", tags=["tracking"])


class TrackedIn(BaseModel):
    media_item_id: Optional[int] = None
    game_id: Optional[int] = None
    status: str = "planned"  # planned|in_progress|completed|dropped|on_hold|repeating
    progress_percent: float = 0.0
    rating: Optional[float] = None
    notes: Optional[str] = None


class TrackedUpdate(BaseModel):
    status: Optional[str] = None
    progress_percent: Optional[float] = None
    rating: Optional[float] = None
    notes: Optional[str] = None


@router.get("")
def list_tracked(
    status: Optional[str] = None,
    media_type: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    from app.models import MediaItem, Game, MediaType

    q = db.query(TrackedItem)
    if status:
        q = q.filter(TrackedItem.status == status)

    mt = (media_type or "").strip().lower()
    if mt == "game":
        q = q.filter(TrackedItem.game_id.isnot(None))
    elif mt:
        # join media_items for movie|tv|music|...
        q = q.join(MediaItem, TrackedItem.media_item_id == MediaItem.id)
        try:
            enum_val = MediaType(mt)
            q = q.filter(MediaItem.media_type == enum_val)
        except Exception as e:
            log.warning("tracking soft-fail: %s", e)
            q = q.filter(MediaItem.media_type == mt)

    total = q.count()
    rows = q.order_by(TrackedItem.updated_at.desc()).offset(offset).limit(limit).all()
    items = []
    for row in rows:
        title = None
        resolved_type = None
        if row.media_item_id:
            mi = db.get(MediaItem, row.media_item_id)
            if mi:
                title = mi.title
                resolved_type = mi.media_type.value if hasattr(mi.media_type, "value") else str(mi.media_type)
        elif row.game_id:
            g = db.get(Game, row.game_id)
            if g:
                title = getattr(g, "title", None) or getattr(g, "name", None)
                resolved_type = "game"
        items.append(
            {
                "id": row.id,
                "media_item_id": row.media_item_id,
                "game_id": row.game_id,
                "title": title,
                "media_type": resolved_type,
                "status": row.status,
                "progress_percent": row.progress_percent,
                "rating": row.rating,
                "notes": row.notes,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )
    return {"total": total, "items": items}


@router.post("")
def upsert_tracked(
    body: TrackedIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("library")),
):
    if not body.media_item_id and not body.game_id:
        raise HTTPException(400, "media_item_id or game_id required")

    existing = None
    if body.media_item_id:
        existing = db.query(TrackedItem).filter(TrackedItem.media_item_id == body.media_item_id).first()
    elif body.game_id:
        existing = db.query(TrackedItem).filter(TrackedItem.game_id == body.game_id).first()

    if existing:
        existing.status = body.status
        existing.progress_percent = body.progress_percent
        existing.rating = body.rating
        existing.notes = body.notes
        if body.status == "completed":
            existing.completed_at = datetime.now(timezone.utc)
        if body.status == "in_progress" and not existing.started_at:
            existing.started_at = datetime.now(timezone.utc)
        db.commit()
        return {"ok": True, "id": existing.id, "action": "updated"}

    t = TrackedItem(
        media_item_id=body.media_item_id,
        game_id=body.game_id,
        status=body.status,
        progress_percent=body.progress_percent,
        rating=body.rating,
        notes=body.notes,
        started_at=datetime.now(timezone.utc) if body.status == "in_progress" else None,
        completed_at=datetime.now(timezone.utc) if body.status == "completed" else None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"ok": True, "id": t.id, "action": "created"}




class TrackedBulkIn(BaseModel):
    items: list[TrackedIn]


@router.post("/bulk")
def bulk_upsert_tracked(
    body: TrackedBulkIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("library")),
):
    """Upsert many tracking rows (same rules as single POST)."""
    results = []
    for item in body.items:
        # reuse single-path logic via internal call pattern
        if not item.media_item_id and not item.game_id:
            results.append({"ok": False, "error": "ids required"})
            continue
        existing = None
        if item.media_item_id:
            existing = db.query(TrackedItem).filter(TrackedItem.media_item_id == item.media_item_id).first()
        elif item.game_id:
            existing = db.query(TrackedItem).filter(TrackedItem.game_id == item.game_id).first()
        if existing:
            existing.status = item.status
            existing.progress_percent = item.progress_percent
            existing.rating = item.rating
            existing.notes = item.notes
            if item.status == "completed":
                existing.completed_at = datetime.now(timezone.utc)
            if item.status == "in_progress" and not existing.started_at:
                existing.started_at = datetime.now(timezone.utc)
            db.add(existing)
            results.append({"ok": True, "id": existing.id, "action": "updated"})
        else:
            row = TrackedItem(
                media_item_id=item.media_item_id,
                game_id=item.game_id,
                status=item.status,
                progress_percent=item.progress_percent,
                rating=item.rating,
                notes=item.notes,
                started_at=datetime.now(timezone.utc) if item.status == "in_progress" else None,
                completed_at=datetime.now(timezone.utc) if item.status == "completed" else None,
            )
            db.add(row)
            db.flush()
            results.append({"ok": True, "id": row.id, "action": "created"})
    db.commit()
    return {"ok": True, "results": results, "count": len(results)}


@router.patch("/{tracked_id}")
def update_tracked(
    tracked_id: int,
    body: TrackedUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("library")),
):
    t = db.get(TrackedItem, tracked_id)
    if not t:
        raise HTTPException(404, "Not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(t, k, v)
    if data.get("status") == "completed":
        t.completed_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.delete("/{tracked_id}")
def delete_tracked(
    tracked_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("library")),
):
    t = db.get(TrackedItem, tracked_id)
    if not t:
        raise HTTPException(404, "Not found")
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.get("/history")
def tracking_history(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    from app.models import TrackingHistory
    rows = db.query(TrackingHistory).order_by(TrackingHistory.created_at.desc()).limit(limit).all()
    return {
        "items": [
            {
                "id": h.id,
                "tracked_item_id": h.tracked_item_id,
                "media_item_id": h.media_item_id,
                "game_id": h.game_id,
                "action": h.action,
                "detail": h.detail,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in rows
        ]
    }


@router.post("/{tracked_id}/rewatch")
def bump_rewatch(tracked_id: int, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    from app.models import TrackingHistory
    t = db.get(TrackedItem, tracked_id)
    if not t:
        raise HTTPException(404, "Not found")
    t.rewatch_count = (t.rewatch_count or 0) + 1
    t.status = "repeating"
    db.add(TrackingHistory(
        tracked_item_id=t.id,
        media_item_id=t.media_item_id,
        game_id=t.game_id,
        action="rewatch",
        detail=f"count={t.rewatch_count}",
    ))
    db.commit()
    return {"ok": True, "rewatch_count": t.rewatch_count}


@router.get("/statuses")
def list_tracking_statuses():
    """Canonical unified tracking statuses across movies/TV/games/books/comics."""
    return {"statuses": TRACKING_STATUSES}


@router.post("/{tracked_id}/status")
def set_tracking_status(tracked_id: int, body: dict, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    from datetime import datetime, timezone
    from app.models import TrackedItem
    row = db.get(TrackedItem, tracked_id)
    if not row:
        raise HTTPException(404, "Not found")
    status = (body.get("status") or "").strip().lower()
    allowed = {s["id"] for s in TRACKING_STATUSES}
    if status not in allowed:
        raise HTTPException(400, f"status must be one of {sorted(allowed)}")
    row.status = status
    now = datetime.now(timezone.utc)
    if status == "in_progress" and not getattr(row, "started_at", None):
        row.started_at = now
    if status == "completed":
        row.completed_at = now
        if getattr(row, "progress_percent", None) is not None:
            row.progress_percent = 100.0
    row.updated_at = now
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id, "status": row.status}

