from datetime import datetime

from app.auth import require_permission
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SmartList
from app.services.smartlists import run_all_smart_lists, run_smart_list

router = APIRouter(prefix="/smartlists", tags=["smartlists"])


class SmartListCreate(BaseModel):
    name: str
    media_type: str = "movie"
    source: str = "tmdb_list"  # tmdb_list | tmdb_discover
    source_ref: str = Field(..., description="TMDb list id or discover key")
    enabled: bool = True
    min_vote_average: float | None = None
    min_year: int | None = None
    max_year: int | None = None
    quality_profile: str | None = None
    monitored: bool = True


class SmartListUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    min_vote_average: float | None = None
    min_year: int | None = None
    max_year: int | None = None
    quality_profile: str | None = None
    monitored: bool | None = None
    source_ref: str | None = None


class SmartListOut(BaseModel):
    id: int
    name: str
    media_type: str
    source: str
    source_ref: str
    enabled: bool
    min_vote_average: float | None
    min_year: int | None
    max_year: int | None
    quality_profile: str | None
    monitored: bool
    last_run_at: datetime | None
    last_added_count: int
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=list[SmartListOut])
def list_smart_lists(db: Session = Depends(get_db)):
    return db.query(SmartList).order_by(SmartList.name).all()


@router.post("", response_model=SmartListOut)
def create_smart_list(payload: SmartListCreate, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    from app.services.smartlists import SUPPORTED_SOURCES
    if payload.source not in SUPPORTED_SOURCES:
        raise HTTPException(400, f"source must be one of: {', '.join(SUPPORTED_SOURCES)}")
    sl = SmartList(
        name=payload.name,
        media_type=payload.media_type,
        source=payload.source,
        source_ref=payload.source_ref,
        enabled=payload.enabled,
        min_vote_average=payload.min_vote_average,
        min_year=payload.min_year,
        max_year=payload.max_year,
        quality_profile=payload.quality_profile,
        monitored=payload.monitored,
    )
    db.add(sl)
    db.commit()
    db.refresh(sl)
    return sl


@router.patch("/{list_id}", response_model=SmartListOut)
def update_smart_list(list_id: int, payload: SmartListUpdate, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    sl = db.get(SmartList, list_id)
    if not sl:
        raise HTTPException(404, "Not found")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(sl, field, val)
    db.add(sl)
    db.commit()
    db.refresh(sl)
    return sl


@router.delete("/{list_id}", status_code=204)
def delete_smart_list(list_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    sl = db.get(SmartList, list_id)
    if not sl:
        raise HTTPException(404, "Not found")
    db.delete(sl)
    db.commit()


@router.post("/{list_id}/run")
def run_one(list_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    sl = db.get(SmartList, list_id)
    if not sl:
        raise HTTPException(404, "Not found")
    n = run_smart_list(db, sl)
    return {"added": n, "list_id": list_id}


@router.post("/run-all")
def run_all(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    return run_all_smart_lists(db)
