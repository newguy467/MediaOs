"""
Homelab Links / Services page (Organizr-inspired, MediaOS v2).
"""

from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_permission
from app.models import HomelabLink

router = APIRouter(prefix="/homelab", tags=["homelab"])


class LinkIn(BaseModel):
    title: str
    url: str
    icon_url: Optional[str] = None
    group_name: Optional[str] = None
    sort_order: int = 0
    enabled: bool = True
    iframe: bool = False
    health_check_url: Optional[str] = None


class LinkUpdate(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    icon_url: Optional[str] = None
    group_name: Optional[str] = None
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None
    iframe: Optional[bool] = None
    health_check_url: Optional[str] = None


@router.get("/links")
def list_links(db: Session = Depends(get_db)):
    rows = db.query(HomelabLink).order_by(HomelabLink.group_name, HomelabLink.sort_order, HomelabLink.title).all()
    return {
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "url": r.url,
                "icon_url": r.icon_url,
                "group_name": r.group_name,
                "sort_order": r.sort_order,
                "enabled": r.enabled,
                "iframe": getattr(r, "iframe", False),
                "last_status": r.last_status,
                "last_check_at": r.last_check_at.isoformat() if r.last_check_at else None,
            }
            for r in rows
        ]
    }


@router.post("/links")
def add_link(
    body: LinkIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("settings")),
):
    link = HomelabLink(
        title=body.title,
        url=body.url,
        icon_url=body.icon_url,
        group_name=body.group_name,
        sort_order=body.sort_order,
        enabled=body.enabled,
        iframe=body.iframe,
        health_check_url=body.health_check_url,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return {"ok": True, "id": link.id}


@router.patch("/links/{link_id}")
def update_link(
    link_id: int,
    body: LinkUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("settings")),
):
    link = db.get(HomelabLink, link_id)
    if not link:
        raise HTTPException(404, "Link not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(link, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/links/{link_id}")
def delete_link(
    link_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("settings")),
):
    link = db.get(HomelabLink, link_id)
    if not link:
        raise HTTPException(404, "Link not found")
    db.delete(link)
    db.commit()
    return {"ok": True}


@router.post("/links/health-check")
def health_check_all(db: Session = Depends(get_db), _=Depends(require_permission("settings"))):
    """Probe health_check_url (or url) for every enabled link; update last_status."""
    import httpx
    from datetime import datetime, timezone
    rows = db.query(HomelabLink).filter(HomelabLink.enabled == True).all()  # noqa: E712
    results = []
    for link in rows:
        probe = link.health_check_url or link.url
        status = "unknown"
        try:
            with httpx.Client(timeout=5.0, follow_redirects=True) as client:
                r = client.get(probe)
                status = "up" if r.status_code < 400 else f"http_{r.status_code}"
        except Exception:
            status = "down"
        link.last_status = status
        link.last_check_at = datetime.now(timezone.utc)
        db.add(link)
        results.append({"id": link.id, "title": link.title, "status": status, "probed": probe})
    db.commit()
    return {"ok": True, "checked": len(results), "results": results}


@router.post("/links/{link_id}/health-check")
def health_check_one(link_id: int, db: Session = Depends(get_db), _=Depends(require_permission("settings"))):
    import httpx
    from datetime import datetime, timezone
    link = db.get(HomelabLink, link_id)
    if not link:
        raise HTTPException(404, "Link not found")
    probe = link.health_check_url or link.url
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            r = client.get(probe)
            status = "up" if r.status_code < 400 else f"http_{r.status_code}"
    except Exception:
        status = "down"
    link.last_status = status
    link.last_check_at = datetime.now(timezone.utc)
    db.add(link)
    db.commit()
    return {"ok": True, "id": link.id, "status": status}


# ── Announce Lab (autobrr-style, in-process — no extra container) ───────────

class AnnounceFiltersBody(BaseModel):
    filters: list[dict] = []


@router.get("/announce")
def announce_status(db: Session = Depends(get_db)):
    from app.services.announce_lab import status
    return status(db)


@router.put("/announce/filters")
def announce_save_filters(
    body: AnnounceFiltersBody,
    db: Session = Depends(get_db),
    _=Depends(require_permission("settings")),
):
    from app.services.announce_lab import save_filters
    return {"ok": True, "filters": save_filters(db, body.filters)}


@router.post("/announce/run")
def announce_run(
    db: Session = Depends(get_db),
    _=Depends(require_permission("settings")),
):
    from app.services.announce_lab import run_cycle
    return run_cycle(db)
