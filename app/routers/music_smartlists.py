from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_permission
from app.database import get_db
from app.models import MusicSmartlist
from app.services.music_smartlists import SUPPORTED_SOURCES, resolve_smartlist
from sqlalchemy.orm import Session

router = APIRouter(prefix="/music-smartlists", tags=["music-smartlists"])


class MusicSmartlistCreate(BaseModel):
    name: str
    source: str = "library_genre"
    genre_filter: str | None = None
    mood_filter: str | None = None
    added_within_days: int | None = None
    min_play_count: int | None = None
    result_limit: int = 50


class MusicSmartlistUpdate(BaseModel):
    name: str | None = None
    source: str | None = None
    genre_filter: str | None = None
    mood_filter: str | None = None
    added_within_days: int | None = None
    min_play_count: int | None = None
    result_limit: int | None = None


class MusicSmartlistOut(BaseModel):
    id: int
    name: str
    source: str
    genre_filter: str | None
    mood_filter: str | None
    added_within_days: int | None
    min_play_count: int | None
    result_limit: int
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=list[MusicSmartlistOut])
def list_music_smartlists(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.view"))):
    return db.query(MusicSmartlist).order_by(MusicSmartlist.name).all()


@router.post("", response_model=MusicSmartlistOut)
def create_music_smartlist(payload: MusicSmartlistCreate, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    if payload.source not in SUPPORTED_SOURCES:
        raise HTTPException(400, f"source must be one of: {', '.join(SUPPORTED_SOURCES)}")
    sl = MusicSmartlist(
        name=payload.name,
        source=payload.source,
        genre_filter=payload.genre_filter,
        mood_filter=payload.mood_filter,
        added_within_days=payload.added_within_days,
        min_play_count=payload.min_play_count,
        result_limit=payload.result_limit or 50,
    )
    db.add(sl)
    db.commit()
    db.refresh(sl)
    return sl


@router.patch("/{list_id}", response_model=MusicSmartlistOut)
def update_music_smartlist(list_id: int, payload: MusicSmartlistUpdate, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    sl = db.get(MusicSmartlist, list_id)
    if not sl:
        raise HTTPException(404, "Not found")
    data = payload.model_dump(exclude_unset=True)
    if "source" in data and data["source"] not in SUPPORTED_SOURCES:
        raise HTTPException(400, f"source must be one of: {', '.join(SUPPORTED_SOURCES)}")
    for field, val in data.items():
        setattr(sl, field, val)
    db.add(sl)
    db.commit()
    db.refresh(sl)
    return sl


@router.delete("/{list_id}", status_code=204)
def delete_music_smartlist(list_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    sl = db.get(MusicSmartlist, list_id)
    if not sl:
        raise HTTPException(404, "Not found")
    db.delete(sl)
    db.commit()


@router.get("/{list_id}/tracks")
def music_smartlist_tracks(list_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.view"))):
    sl = db.get(MusicSmartlist, list_id)
    if not sl:
        raise HTTPException(404, "Not found")
    try:
        return resolve_smartlist(db, sl)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
