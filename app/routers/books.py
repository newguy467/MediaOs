from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.clients.openlibrary import openlibrary_client
from app.auth import require_permission
from app.database import get_db
from app.models import ItemStatus, MediaItem, MediaType
from app.services.grab import grab_release
from app.services.search import find_best_book_release, search_book_releases

router = APIRouter(prefix="/books", tags=["books"],
    dependencies=[Depends(require_permission("library.view", "library.manage"))],
)


class BookCreate(BaseModel):
    series_name: str | None = None
    author_name: str | None = None
    external_id: int
    title: str
    year: int | None = None
    overview: str | None = None
    poster_path: str | None = None
    monitored: bool = True


class BookOut(BaseModel):
    id: int
    external_id: int
    title: str
    year: int | None
    status: str
    monitored: bool
    overview: str | None
    poster_path: str | None
    series_name: str | None = None
    artist_name: str | None = None
    file_path: str | None = None
    added_at: datetime

    class Config:
        from_attributes = True


@router.get("/search")
def search_books(query: str):
    return openlibrary_client.search_books(query)


@router.get("", response_model=list[BookOut])
def list_books(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.view"))):
    return (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.book)
        .order_by(MediaItem.title)
        .all()
    )


@router.post("", response_model=BookOut)
def add_book(payload: BookCreate, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage", "download"))):
    existing = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.book,
            MediaItem.external_id == payload.external_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(409, "Already in library")
    series_name = getattr(payload, "series_name", None)
    author = getattr(payload, "author_name", None) or getattr(payload, "artist_name", None)
    item = MediaItem(
        media_type=MediaType.book,
        external_id=payload.external_id,
        external_source="openlibrary",
        title=payload.title,
        year=payload.year,
        overview=payload.overview,
        poster_path=payload.poster_path,
        monitored=payload.monitored,
        status=ItemStatus.wanted,
        series_name=series_name,
        artist_name=author,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_book(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.book:
        raise HTTPException(404, "Not found")
    db.delete(item)
    db.commit()


@router.post("/{item_id}/search")
def search_and_grab_book(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.book:
        raise HTTPException(404, "Not found")
    release = find_best_book_release(item, db=db)
    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    if not release:
        return {"found": False}
    grab_release(db, item, release)
    return {"found": True, "title": release.get("title"), "indexer": release.get("indexer")}





@router.get("/{item_id}")
def get_book(item_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.view"))):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.book:
        raise HTTPException(404, "Not found")
    return item


@router.get("/{item_id}/interactive-search")
def interactive_search_book(item_id: int, limit: int = 50, db: Session = Depends(get_db)):
    from app.services.interactive_search import interactive_book_search
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.book:
        raise HTTPException(404, "Not found")
    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    return interactive_book_search(item, db=db, limit=limit)


@router.post("/{item_id}/grab")
def grab_book_release(item_id: int, payload: dict, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.book:
        raise HTTPException(404, "Not found")
    release = payload.get("release") or payload
    if not release.get("download_url") and not release.get("magnet"):
        raise HTTPException(400, "download_url or magnet required")
    grab_release(db, item, release)
    return {"ok": True, "title": release.get("title")}




class BookUpdate(BaseModel):
    title: str | None = None
    year: int | None = None
    overview: str | None = None
    poster_path: str | None = None
    monitored: bool | None = None
    quality_profile: str | None = None


class BookFileIn(BaseModel):
    path: str | None = None
    clear: bool = False


class BookBulkIn(BaseModel):
    ids: list[int]
    monitored: bool | None = None
    quality_profile: str | None = None


@router.patch("/{item_id}", response_model=BookOut)
def update_book(item_id: int, payload: BookUpdate, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.book:
        raise HTTPException(404, "Not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/refresh")
def refresh_book(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.book:
        raise HTTPException(404, "Not found")
    # Soft refresh — OpenLibrary optional enrichment later
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/file")
def manage_book_file(item_id: int, payload: BookFileIn, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type != MediaType.book:
        raise HTTPException(404, "Not found")
    if payload.clear:
        item.file_path = None
        item.status = ItemStatus.missing
    elif payload.path:
        item.file_path = payload.path
        item.status = ItemStatus.downloaded
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/search-missing")
def search_missing_books(limit: int = 40, db: Session = Depends(get_db)):
    items = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.book,
            MediaItem.monitored.is_(True),
            MediaItem.status.in_([ItemStatus.wanted, ItemStatus.missing, ItemStatus.failed]),
        )
        .order_by(MediaItem.last_searched_at.nullsfirst())
        .limit(limit)
        .all()
    )
    searched = grabbed = 0
    for item in items:
        searched += 1
        try:
            rel = find_best_book_release(item, db=db)
            item.last_searched_at = datetime.now(timezone.utc)
            db.add(item)
            if rel:
                grab_release(db, item, rel)
                grabbed += 1
            db.commit()
        except Exception:
            db.rollback()
    return {"searched": searched, "grabbed": grabbed}


@router.post("/bulk")
def bulk_books(payload: BookBulkIn, db: Session = Depends(get_db)):
    q = db.query(MediaItem).filter(MediaItem.media_type == MediaType.book, MediaItem.id.in_(payload.ids))
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


@router.get("/authors/search")
def search_authors(query: str):
    return openlibrary_client.search_authors(query)


@router.get("/authors/{author_key:path}/works")
def author_works(author_key: str, limit: int = 50):
    return openlibrary_client.author_works(author_key, limit=limit)


@router.get("/works/{work_key:path}/editions")
def work_editions(work_key: str, limit: int = 20):
    return openlibrary_client.work_editions(work_key, limit=limit)


@router.post("/add-author")
def add_author_works(
    author_key: str,
    limit: int = 30,
    monitored: bool = True,
    db: Session = Depends(get_db),
):
    works = openlibrary_client.author_works(author_key, limit=limit)
    added, skipped = [], 0
    for w in works:
        exists = (
            db.query(MediaItem)
            .filter(
                MediaItem.media_type == MediaType.book,
                MediaItem.external_id == w["external_id"],
            )
            .first()
        )
        if exists:
            skipped += 1
            continue
        item = MediaItem(
            media_type=MediaType.book,
            external_id=w["external_id"],
            external_source="openlibrary",
            title=w.get("title") or "Unknown",
            overview=author_key,
            monitored=monitored,
            status=ItemStatus.wanted,
        )
        db.add(item)
        added.append(item.title)
    db.commit()
    return {"author_key": author_key, "added": len(added), "skipped": skipped, "titles": added}


@router.get("/library/authors")
def library_authors(db: Session = Depends(get_db)):
    """Group library books by author (overview field)."""
    rows = db.query(MediaItem).filter(MediaItem.media_type == MediaType.book).all()
    tree: dict = {}
    for b in rows:
        author = (b.overview or "Unknown Author").split(",")[0].strip() or "Unknown Author"
        tree.setdefault(author, []).append({
            "id": b.id,
            "title": b.title,
            "year": b.year,
            "status": b.status.value if b.status else None,
            "monitored": b.monitored,
            "poster_path": b.poster_path,
        })
    return {
        "authors": [
            {"name": n, "book_count": len(books), "books": books}
            for n, books in sorted(tree.items(), key=lambda x: x[0].lower())
        ]
    }
