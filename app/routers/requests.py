from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_admin, require_auth
from app.database import get_db
from app.models import MediaRequest, RequestStatus
from app.services.requests import approve_request, deny_request

router = APIRouter(prefix="/requests", tags=["requests"])


class RequestCreate(BaseModel):
    media_type: str  # movie | tv | music | book | audiobook
    external_id: int
    external_source: str | None = None
    title: str
    year: int | None = None
    overview: str | None = None
    poster_path: str | None = None
    artist_name: str | None = None
    note: str | None = None


class RequestOut(BaseModel):
    id: int
    media_type: str
    external_id: int
    external_source: str | None
    title: str
    year: int | None
    overview: str | None
    poster_path: str | None
    artist_name: str | None
    requested_by: str | None
    note: str | None
    status: str
    resolved_by: str | None
    resolution_note: str | None
    media_item_id: int | None
    created_at: datetime
    resolved_at: datetime | None

    class Config:
        from_attributes = True


@router.post("", response_model=RequestOut)
def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    requester: Annotated[str | None, Depends(require_auth)] = None,
):
    if payload.media_type not in ("movie", "tv", "music", "book", "audiobook"):
        raise HTTPException(400, "Unsupported media_type")
    existing = (
        db.query(MediaRequest)
        .filter(
            MediaRequest.media_type == payload.media_type,
            MediaRequest.external_id == payload.external_id,
            MediaRequest.status == RequestStatus.pending.value,
        )
        .first()
    )
    if existing:
        raise HTTPException(409, "Already requested and pending review")

    row = MediaRequest(
        media_type=payload.media_type,
        external_id=payload.external_id,
        external_source=payload.external_source,
        title=payload.title,
        year=payload.year,
        overview=payload.overview,
        poster_path=payload.poster_path,
        artist_name=payload.artist_name,
        note=payload.note,
        requested_by=requester,
        status=RequestStatus.pending.value,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[RequestOut])
def list_requests(
    status: str | None = None,
    mine: bool = False,
    db: Session = Depends(get_db),
    requester: Annotated[str | None, Depends(require_auth)] = None,
):
    q = db.query(MediaRequest)
    if status:
        q = q.filter(MediaRequest.status == status)
    if mine and requester:
        q = q.filter(MediaRequest.requested_by == requester)
    return q.order_by(MediaRequest.created_at.desc()).all()


@router.get("/{request_id}", response_model=RequestOut)
def get_request(request_id: int, db: Session = Depends(get_db)):
    row = db.get(MediaRequest, request_id)
    if not row:
        raise HTTPException(404, "Not found")
    return row


class ApproveIn(BaseModel):
    quality_profile: str | None = None


@router.post("/{request_id}/approve", response_model=RequestOut)
def approve(
    request_id: int,
    payload: ApproveIn = ApproveIn(),
    db: Session = Depends(get_db),
    admin: Annotated[str, Depends(require_admin)] = "admin",
):
    row = db.get(MediaRequest, request_id)
    if not row:
        raise HTTPException(404, "Not found")
    approve_request(db, row, resolved_by=admin, quality_profile=payload.quality_profile)
    db.refresh(row)
    return row


class DenyIn(BaseModel):
    reason: str | None = None


@router.post("/{request_id}/deny", response_model=RequestOut)
def deny(
    request_id: int,
    payload: DenyIn = DenyIn(),
    db: Session = Depends(get_db),
    admin: Annotated[str, Depends(require_admin)] = "admin",
):
    row = db.get(MediaRequest, request_id)
    if not row:
        raise HTTPException(404, "Not found")
    return deny_request(db, row, resolved_by=admin, reason=payload.reason)


@router.delete("/{request_id}", status_code=204)
def cancel_request(
    request_id: int,
    db: Session = Depends(get_db),
    requester: Annotated[str | None, Depends(require_auth)] = None,
):
    row = db.get(MediaRequest, request_id)
    if not row:
        raise HTTPException(404, "Not found")
    if requester and row.requested_by and row.requested_by != requester:
        raise HTTPException(403, "Not your request")
    db.delete(row)
    db.commit()
