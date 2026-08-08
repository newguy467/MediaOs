from __future__ import annotations

from app.auth import require_permission
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.clients.tmdb import tmdb_client
from app.database import get_db
from app.models import Collection
from app.services.collections import add_all_movies, collection_progress, track_collection

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("/search")
def search_collections(query: str):
    return tmdb_client.search_collections(query)


@router.get("")
def list_collections(db: Session = Depends(get_db)):
    rows = db.query(Collection).order_by(Collection.name).all()
    return [collection_progress(db, r) for r in rows]

@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    rows = db.query(Collection).order_by(Collection.name).all()
    out = []
    for r in rows:
        prog = collection_progress(db, r)
        out.append({"id": prog["id"], "name": prog["name"], "poster_path": prog["poster_path"],
            "owned": prog["owned"], "total_parts": prog["total_parts"],
            "progress_label": prog["progress_label"],
            "pct": int(100 * prog["owned"] / prog["total_parts"]) if prog["total_parts"] else 0})
    return out


@router.get("/{collection_id}")
def get_collection(collection_id: int, db: Session = Depends(get_db)):
    row = db.get(Collection, collection_id)
    if not row:
        raise HTTPException(404, "Not found")
    return collection_progress(db, row)


class CollectionCreate(BaseModel):
    tmdb_id: int
    monitored: bool = True
    add_all: bool = True


@router.post("")
def create_collection(payload: CollectionCreate, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    existing = db.query(Collection).filter(Collection.tmdb_id == payload.tmdb_id).first()
    if existing:
        raise HTTPException(409, "Collection already tracked")
    row = track_collection(db, payload.tmdb_id, monitored=payload.monitored)
    result = {"collection": collection_progress(db, row)}
    if payload.add_all:
        result["add_all"] = add_all_movies(db, row, monitored=payload.monitored)
        result["collection"] = collection_progress(db, row)
    return result


@router.post("/{collection_id}/add-all")
def add_all(collection_id: int, monitored: bool = True, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    row = db.get(Collection, collection_id)
    if not row:
        raise HTTPException(404, "Not found")
    result = add_all_movies(db, row, monitored=monitored)
    result["collection"] = collection_progress(db, row)
    return result


@router.post("/{collection_id}/refresh")
def refresh_collection(collection_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    row = db.get(Collection, collection_id)
    if not row:
        raise HTTPException(404, "Not found")
    track_collection(db, row.tmdb_id, monitored=row.monitored)
    return collection_progress(db, row)


@router.delete("/{collection_id}", status_code=204)
def delete_collection(collection_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    """Stop tracking the collection. Movies already in the library are kept,
    just unlinked from the saga."""
    row = db.get(Collection, collection_id)
    if not row:
        raise HTTPException(404, "Not found")
    for m in row.movies:
        m.collection_id = None
    db.delete(row)
    db.commit()
