from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.clients.openlibrary import openlibrary_client
from app.clients.audnexus import audnexus_client
from app.auth import require_permission
from app.database import get_db
from app.models import ItemStatus, MediaItem, MediaType
from app.services.grab import grab_release
from app.services.search import find_best_audiobook_release, search_audiobook_releases

router = APIRouter(prefix="/audiobooks", tags=["audiobooks"],
    dependencies=[Depends(require_permission("library.view", "library.manage"))],
)


class AudiobookCreate(BaseModel):
    external_id: int
    title: str
    year: int | None = None
    overview: str | None = None
    poster_path: str | None = None
    monitored: bool = True


class AudiobookOut(BaseModel):
    id: int
    external_id: int
    title: str
    year: int | None
    status: str
    monitored: bool
    overview: str | None
    poster_path: str | None
    file_path: str | None = None
    added_at: datetime

    class Config:
        from_attributes = True


@router.get("/search")
def search_audiobooks(query: str):
    """Open Library + Audnexus (ASIN) search."""
    rows = openlibrary_client.search_books(query)
    for r in rows:
        r["media_type"] = "audiobook"
    # If query looks like ASIN, prefer Audnexus metadata
    aq = audnexus_client.search(query)
    if aq:
        return aq + rows
    return rows


@router.get("/asin/{asin}")
def get_by_asin(asin: str):
    book = audnexus_client.get_book(asin)
    if not book:
        raise HTTPException(404, "ASIN not found on Audnexus")
    return book


@router.get("", response_model=list[AudiobookOut])
def list_audiobooks(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.view"))):
    return (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.audiobook)
        .order_by(MediaItem.title)
        .all()
    )


@router.post("", response_model=AudiobookOut)
def add_audiobook(payload: AudiobookCreate, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage", "download"))):
    existing = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.audiobook,
            MediaItem.external_id == payload.external_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(409, "Already in library")
    item = MediaItem(
        media_type=MediaType.audiobook,
        external_id=payload.external_id,
        external_source=getattr(payload, "external_source", None) or "openlibrary",
        title=payload.title,
        year=payload.year,
        overview=payload.overview,
        poster_path=payload.poster_path,
        monitored=payload.monitored,
        status=ItemStatus.wanted,
        series_name=getattr(payload, "series_name", None),
        artist_name=getattr(payload, "author_name", None) or getattr(payload, "artist_name", None),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item




class AudiobookBulkIn(BaseModel):
    ids: list[int]
    monitored: bool | None = None
    quality_profile: str | None = None


@router.post("/bulk")
def bulk_audiobooks(payload: AudiobookBulkIn, db: Session = Depends(get_db)):
    """Bulk monitor / quality-profile update — same shape as books/movies."""
    q = db.query(MediaItem).filter(
        MediaItem.media_type == MediaType.audiobook,
        MediaItem.id.in_(payload.ids),
    )
    n = 0
    for item in q.all():
        if payload.monitored is not None:
            item.monitored = payload.monitored
        if payload.quality_profile is not None:
            item.quality_profile = payload.quality_profile
        db.add(item)
        n += 1
    db.commit()
    return {"ok": True, "updated": n}

@router.delete("/{item_id}", status_code=204)
def delete_audiobook(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.audiobook:
        raise HTTPException(404, "Not found")
    db.delete(item)
    db.commit()




@router.post("/search-missing")
def search_all_missing_audiobooks(limit: int = 40, db: Session = Depends(get_db)):
    rows = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.audiobook,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .limit(limit)
        .all()
    )
    searched = grabbed = 0
    for item in rows:
        searched += 1
        item.last_searched_at = datetime.now(timezone.utc)
        db.add(item)
        try:
            rel = find_best_audiobook_release(item, db=db)
            if rel:
                grab_release(db, item, rel)
                grabbed += 1
        except Exception:
            continue
    db.commit()
    return {"searched": searched, "grabbed": grabbed}





@router.get("/wanted-hierarchy")
def audiobooks_wanted_hierarchy(db: Session = Depends(get_db)):
    rows = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.audiobook,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .order_by(MediaItem.title)
        .all()
    )
    tree: dict = {}
    for b in rows:
        author = (getattr(b, "artist_name", None) or b.overview or "Unknown").split(",")[0].strip() or "Unknown"
        tree.setdefault(author, []).append({
            "id": b.id,
            "title": b.title,
            "status": b.status.value if b.status else None,
        })
    return {
        "authors": [
            {"name": n, "wanted_count": len(items), "items": items}
            for n, items in sorted(tree.items(), key=lambda x: (-len(x[1]), x[0].lower()))
        ]
    }

@router.get("/{item_id}")
def get_audiobook(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.audiobook:
        raise HTTPException(404, "Not found")
    return item


@router.get("/{item_id}/interactive-search")
def interactive_search_audiobook(item_id: int, limit: int = 50, db: Session = Depends(get_db)):
    from app.services.interactive_search import interactive_audiobook_search
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.audiobook:
        raise HTTPException(404, "Not found")
    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    data = interactive_audiobook_search(item, db=db, limit=limit)
    return data


@router.post("/{item_id}/grab")
def grab_audiobook_release(item_id: int, payload: dict, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.audiobook:
        raise HTTPException(404, "Not found")
    release = payload.get("release") or payload
    if not release.get("download_url") and not release.get("magnet"):
        raise HTTPException(400, "download_url or magnet required")
    grab_release(db, item, release)
    return {"ok": True, "title": release.get("title")}


@router.patch("/{item_id}")
def update_audiobook(item_id: int, payload: dict, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.audiobook:
        raise HTTPException(404, "Not found")
    if "monitored" in payload and payload["monitored"] is not None:
        item.monitored = bool(payload["monitored"])
    if "quality_profile" in payload:
        item.quality_profile = payload["quality_profile"]
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.post("/{item_id}/search")
def search_and_grab_audiobook(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.audiobook:
        raise HTTPException(404, "Not found")
    release = find_best_audiobook_release(item, db=db)
    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    if not release:
        return {"found": False}
    grab_release(db, item, release)
    return {
        "found": True,
        "title": release.get("title"),
        "indexer": release.get("indexer"),
    }


