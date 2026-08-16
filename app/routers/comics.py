"""Comics (ComicVine) + Manga (MangaDex)."""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.clients.comicvine import comicvine_client
from app.clients.mangadex import mangadex_client
from app.auth import require_permission
from app.database import get_db
from app.models import ItemStatus, MediaItem, MediaType
from app.services.grab import grab_release
from app.services.search import find_best_comic_release, find_best_manga_release
from app.services import comic_arcs as arcsvc

router = APIRouter(
    prefix="/comics",
    tags=["comics"],
    dependencies=[Depends(require_permission("library.view", "library.manage"))],
)

class ComicCreate(BaseModel):
    external_id: int
    title: str
    year: int | None = None
    overview: str | None = None
    poster_path: str | None = None
    monitored: bool = True
    external_source: str = "comicvine"
    media_kind: str = "comic"
    artist_name: str | None = None  # publisher
    series_name: str | None = None  # series/volume family (ComicVine volume name)

class ComicOut(BaseModel):
    id: int
    external_id: int
    external_source: str | None
    title: str
    year: int | None
    status: str
    monitored: bool
    overview: str | None
    poster_path: str | None
    artist_name: str | None
    series_name: str | None = None
    media_type: str
    quality_profile: str | None = None
    added_at: datetime
    class Config:
        from_attributes = True


class ArcCreate(BaseModel):
    name: str
    description: str | None = None
    comicvine_id: int | None = None
    issues: list[dict] | None = None


class ArcIssueIn(BaseModel):
    series_name: str
    issue_number: str | None = None
    reading_order: int | None = None
    media_item_id: int | None = None
    comic_issue_id: int | None = None


class PullCreate(BaseModel):
    series_name: str
    issue_number: str | None = None
    publisher: str | None = None
    release_date: str | None = None
    comicvine_id: int | None = None
    watched: bool = True


class PullFlags(BaseModel):
    watched: bool | None = None
    grabbed: bool | None = None

@router.get("/search")
def search_comics(query: str, source: str = Query("all")):
    results = []
    if source in ("all", "comicvine") and comicvine_client.configured:
        results.extend(comicvine_client.search_volumes(query))
    if source in ("all", "mangadex"):
        results.extend(mangadex_client.search_manga(query))
    return results

@router.get("/profiles/list")
def comic_profiles(db: Session = Depends(get_db)):
    """Quality profiles for comics / manga."""
    try:
        from app.services.quality.store import list_profile_rows
        rows = list_profile_rows(db)
        out = []
        for r in rows:
            mt = (getattr(r, "media_type", None) or "").lower()
            if mt in ("comic", "comics", "manga", ""):
                out.append({"id": r.id, "name": r.name, "media_type": r.media_type, "is_default": getattr(r, "is_default", False)})
        if not out:
            out = [{"id": r.id, "name": r.name, "media_type": r.media_type} for r in rows]
        return out
    except Exception:
        from app.services.quality.profiles import (
            default_comic_profile, default_manga_profile,
            default_comic_digital_profile, default_comic_any_profile,
        )
        return [
            {"name": default_comic_profile().name, "media_type": "comic"},
            {"name": default_comic_digital_profile().name, "media_type": "comic"},
            {"name": default_comic_any_profile().name, "media_type": "comic"},
            {"name": default_manga_profile().name, "media_type": "manga"},
        ]


@router.get("", response_model=list[ComicOut])
def list_comics(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.view"))):
    return db.query(MediaItem).filter(MediaItem.media_type.in_([MediaType.comic, MediaType.manga])).order_by(MediaItem.title).all()


@router.get("/wanted/list")
def wanted_comics(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.view"))):
    return (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type.in_([MediaType.comic, MediaType.manga]),
            MediaItem.status == ItemStatus.wanted,
            MediaItem.monitored.is_(True),
        )
        .order_by(MediaItem.title)
        .all()
    )

@router.post("", response_model=ComicOut)
def add_comic(payload: ComicCreate, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage", "download"))):
    mtype = MediaType.manga if payload.media_kind == "manga" or payload.external_source == "mangadex" else MediaType.comic
    existing = db.query(MediaItem).filter(MediaItem.media_type == mtype, MediaItem.external_id == payload.external_id).first()
    if existing:
        raise HTTPException(409, "Already in library")
    # Prefer explicit series_name; fall back to volume title so badges/organize work
    series = (payload.series_name or "").strip() or payload.title
    item = MediaItem(
        media_type=mtype,
        external_id=payload.external_id,
        external_source=payload.external_source,
        title=payload.title,
        year=payload.year,
        overview=payload.overview,
        poster_path=payload.poster_path,
        monitored=payload.monitored,
        artist_name=payload.artist_name,  # publisher
        series_name=series,
        status=ItemStatus.wanted,
    )
    db.add(item); db.commit(); db.refresh(item)
    return item


class ComicBulkIn(BaseModel):
    ids: list[int]
    monitored: bool | None = None
    quality_profile: str | None = None


@router.post("/bulk")
def bulk_comics(payload: ComicBulkIn, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage"))):
    """Bulk monitor/quality for comic volumes — before /{item_id}."""
    n = 0
    for iid in payload.ids:
        item = db.get(MediaItem, iid)
        if not item or item.media_type not in (MediaType.comic, MediaType.manga):
            continue
        if payload.monitored is not None:
            item.monitored = payload.monitored
        if payload.quality_profile is not None:
            item.quality_profile = payload.quality_profile
        db.add(item)
        n += 1
    db.commit()
    return {"ok": True, "updated": n}



@router.delete("/{item_id}", status_code=204)
def delete_comic(item_id: int, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage"))):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type not in (MediaType.comic, MediaType.manga):
        raise HTTPException(404, "Not found")
    db.delete(item); db.commit()

@router.post("/{item_id}/search")
def search_and_grab(item_id: int, db: Session = Depends(get_db), _: list = Depends(require_permission("download", "library.manage"))):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type not in (MediaType.comic, MediaType.manga):
        raise HTTPException(404, "Not found")
    release = find_best_manga_release(item, db=db) if item.media_type == MediaType.manga else find_best_comic_release(item, db=db)
    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item); db.commit()
    if not release:
        return {"found": False}
    grab_release(db, item, release)
    return {"found": True, "title": release.get("title"), "indexer": release.get("indexer")}




@router.get("/manga")
def list_manga(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.view"))):
    """Comics tagged as manga (quality_profile or overview contains manga, or path)."""
    rows = db.query(MediaItem).filter(MediaItem.media_type == MediaType.comic).all()
    out = []
    for r in rows:
        blob = f"{r.quality_profile or ''} {r.overview or ''} {r.file_path or ''}".lower()
        if "manga" in blob or (r.quality_profile or "").lower() == "manga":
            out.append(r)
    return out


@router.post("/search-missing")
def search_all_missing_comics(limit: int = 40, db: Session = Depends(get_db), _: list = Depends(require_permission("download", "library.manage"))):
    from app.services.search import find_best_comic_release
    rows = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type.in_([MediaType.comic, MediaType.manga]),
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
            rel = find_best_comic_release(item, db=db)
            if rel:
                grab_release(db, item, rel)
                grabbed += 1
        except Exception:
            continue
    db.commit()
    return {"searched": searched, "grabbed": grabbed}


@router.get("/{item_id}/interactive-search")
def interactive_search_comic(item_id: int, limit: int = 50, db: Session = Depends(get_db), _: list = Depends(require_permission("download", "library.view"))):
    from app.services.interactive_search import interactive_comic_search, interactive_manga_search
    item = db.get(MediaItem, item_id)
    if not item or item.media_type not in (MediaType.comic, MediaType.manga):
        raise HTTPException(404, "Not found")
    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    if item.media_type == MediaType.manga:
        return interactive_manga_search(item, db=db, limit=limit)
    return interactive_comic_search(item, db=db, limit=limit)


@router.get("/arcs")
def list_story_arcs(db: Session = Depends(get_db)):
    return arcsvc.list_arcs(db)


@router.get("/arcs/{arc_id}")
def get_story_arc(arc_id: int, db: Session = Depends(get_db)):
    data = arcsvc.get_arc(db, arc_id)
    if not data:
        raise HTTPException(404, "Arc not found")
    return data


@router.post("/arcs")
def create_story_arc(body: ArcCreate, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage"))):
    return arcsvc.create_arc(
        db,
        name=body.name,
        description=body.description,
        comicvine_id=body.comicvine_id,
        issues=body.issues,
    )


@router.delete("/arcs/{arc_id}")
def delete_story_arc(arc_id: int, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage"))):
    if not arcsvc.delete_arc(db, arc_id):
        raise HTTPException(404, "Arc not found")
    return {"ok": True}


@router.post("/arcs/{arc_id}/issues")
def add_arc_issue(arc_id: int, body: ArcIssueIn, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage"))):
    try:
        return arcsvc.add_issue_to_arc(
            db,
            arc_id,
            series_name=body.series_name,
            issue_number=body.issue_number,
            reading_order=body.reading_order,
            media_item_id=body.media_item_id,
            comic_issue_id=body.comic_issue_id,
        )
    except ValueError:
        raise HTTPException(404, "Arc not found")


@router.get("/pull")
def list_pull_list(week: str | None = None, db: Session = Depends(get_db)):
    return arcsvc.list_pull(db, week=week)


@router.post("/pull")
def add_pull(body: PullCreate, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage"))):
    return arcsvc.add_pull_item(
        db,
        series_name=body.series_name,
        issue_number=body.issue_number,
        publisher=body.publisher,
        release_date=body.release_date,
        comicvine_id=body.comicvine_id,
        watched=body.watched,
    )


@router.patch("/pull/{pull_id}")
def patch_pull(pull_id: int, body: PullFlags, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage"))):
    row = arcsvc.set_pull_flags(db, pull_id, watched=body.watched, grabbed=body.grabbed)
    if not row:
        raise HTTPException(404, "Pull item not found")
    return row


@router.post("/pull/sync")
def sync_pull(db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage", "download"))):
    """Trigger weekly pull-list sync if comic_pull_sync service is available."""
    try:
        from app.services.comic_pull_sync import run_pull_list_sync
        return run_pull_list_sync(db)
    except ImportError:
        return {"ok": False, "message": "comic_pull_sync not available — use manual pull entries"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/{item_id}", response_model=ComicOut)
def get_comic(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type not in (MediaType.comic, MediaType.manga):
        raise HTTPException(404, "Not found")
    return item


class ComicUpdate(BaseModel):
    monitored: bool | None = None
    overview: str | None = None
    quality_profile: str | None = None


@router.put("/{item_id}", response_model=ComicOut)
def update_comic(item_id: int, payload: ComicUpdate, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage"))):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type not in (MediaType.comic, MediaType.manga):
        raise HTTPException(404, "Not found")
    if payload.monitored is not None:
        item.monitored = payload.monitored
    if payload.overview is not None:
        item.overview = payload.overview
    if payload.quality_profile is not None:
        item.quality_profile = payload.quality_profile or None
    db.add(item)
    db.commit()
    db.refresh(item)
    return item



@router.get("/{item_id}/releases")
def list_releases(item_id: int, db: Session = Depends(get_db), _: list = Depends(require_permission("download", "library.view"))):
    """Manual release picker — ranked list for the user to choose."""
    item = db.get(MediaItem, item_id)
    if not item or item.media_type not in (MediaType.comic, MediaType.manga):
        raise HTTPException(404, "Not found")
    from app.services.search import search_comic_releases, search_manga_releases
    if item.media_type == MediaType.manga:
        releases = search_manga_releases(item, db=db, limit=30)
    else:
        releases = search_comic_releases(item, db=db, limit=30)
    return releases


@router.post("/{item_id}/grab")
def grab_specific(item_id: int, body: dict, db: Session = Depends(get_db), _: list = Depends(require_permission("download"))):
    item = db.get(MediaItem, item_id)
    if not item or item.media_type not in (MediaType.comic, MediaType.manga):
        raise HTTPException(404, "Not found")
    release = body.get("release") or body
    if not release.get("title") and not release.get("download_url") and not release.get("magnet"):
        raise HTTPException(400, "release payload required")
    grab_release(db, item, release)
    return {"ok": True, "title": release.get("title")}




class IssueOut(BaseModel):
    id: int
    media_item_id: int
    external_id: int | None
    external_source: str | None
    issue_number: str | None
    title: str | None
    cover_date: str | None
    overview: str | None
    poster_path: str | None
    monitored: bool
    status: str
    file_path: str | None
    is_read: bool
    last_page_read: int | None

    class Config:
        from_attributes = True


class IssueProgressIn(BaseModel):
    last_page_read: int | None = None
    is_read: bool | None = None


@router.get("/{item_id}/issues", response_model=list[IssueOut])
def list_issues(item_id: int, db: Session = Depends(get_db), _: list = Depends(require_permission("library.view"))):
    from app.models import ComicIssue
    item = db.get(MediaItem, item_id)
    if not item or item.media_type not in (MediaType.comic, MediaType.manga):
        raise HTTPException(404, "Not found")
    return (
        db.query(ComicIssue)
        .filter(ComicIssue.media_item_id == item_id)
        .order_by(ComicIssue.issue_number)
        .all()
    )


@router.get("/{item_id}/pages")
def item_pages(item_id: int, db: Session = Depends(get_db), _: list = Depends(require_permission("library.view"))):
    """List of readable pages for a volume stored as a single file
    (one-shots, or issues that were never split out) — item.file_path
    rather than a per-issue file. See app/services/comic_reader.py."""
    from app.services.comic_reader import ComicReadError, list_pages
    item = db.get(MediaItem, item_id)
    if not item or item.media_type not in (MediaType.comic, MediaType.manga):
        raise HTTPException(404, "Not found")
    if not item.file_path:
        raise HTTPException(400, "No file on disk for this item")
    try:
        return list_pages(item.file_path)
    except ComicReadError as e:
        raise HTTPException(400, str(e))


@router.get("/{item_id}/page/{index}")
def item_page(item_id: int, index: int, db: Session = Depends(get_db), _: list = Depends(require_permission("library.view"))):
    from app.services.comic_reader import ComicReadError, read_page
    item = db.get(MediaItem, item_id)
    if not item or item.media_type not in (MediaType.comic, MediaType.manga):
        raise HTTPException(404, "Not found")
    if not item.file_path:
        raise HTTPException(400, "No file on disk for this item")
    try:
        data, mime = read_page(item.file_path, index)
    except ComicReadError as e:
        raise HTTPException(400, str(e))
    return Response(content=data, media_type=mime)


@router.post("/{item_id}/issues/sync")
def sync_issues(item_id: int, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage"))):
    """Pull issue/chapter list from ComicVine or MangaDex into comic_issues."""
    from app.models import ComicIssue
    item = db.get(MediaItem, item_id)
    if not item or item.media_type not in (MediaType.comic, MediaType.manga):
        raise HTTPException(404, "Not found")
    rows: list[dict] = []
    if item.media_type == MediaType.comic and item.external_source in (None, "comicvine"):
        if not comicvine_client.configured:
            raise HTTPException(400, "ComicVine API key not configured")
        rows = comicvine_client.volume_issues(int(item.external_id))
    elif item.media_type == MediaType.manga:
        uuid = None
        # Prefer stored overview metadata; resolve UUID via title search
        uuid = mangadex_client.resolve_uuid_from_stable_id(int(item.external_id), item.title)
        if not uuid:
            raise HTTPException(502, "Could not resolve MangaDex UUID for this title")
        rows = mangadex_client.list_chapters(uuid)
    else:
        raise HTTPException(400, "Unsupported source for issue sync")

    existing = {
        (str(i.issue_number or ""), i.external_id)
        for i in db.query(ComicIssue).filter(ComicIssue.media_item_id == item_id).all()
    }
    added = 0
    for r in rows:
        key = (str(r.get("issue_number") or ""), r.get("external_id"))
        if key in existing:
            continue
        db.add(
            ComicIssue(
                media_item_id=item_id,
                external_id=r.get("external_id"),
                external_source=r.get("external_source"),
                issue_number=str(r.get("issue_number") or "") or None,
                title=r.get("title"),
                cover_date=r.get("cover_date"),
                overview=r.get("overview"),
                poster_path=r.get("poster_path"),
                monitored=True,
                status=ItemStatus.wanted,
            )
        )
        added += 1
    db.commit()
    total = db.query(ComicIssue).filter(ComicIssue.media_item_id == item_id).count()
    return {"added": added, "total": total}


@router.post("/{item_id}/issues/{issue_id}/search")
def search_issue(item_id: int, issue_id: int, db: Session = Depends(get_db), _: list = Depends(require_permission("download", "library.view"))):
    from app.models import ComicIssue
    from app.services.search import search_comic_releases, search_manga_releases
    item = db.get(MediaItem, item_id)
    issue = db.get(ComicIssue, issue_id)
    if not item or not issue or issue.media_item_id != item_id:
        raise HTTPException(404, "Not found")
    # temporarily bias query with issue number
    orig = item.title
    item.title = f"{orig} {issue.issue_number or ''} {issue.title or ''}".strip()
    try:
        if item.media_type == MediaType.manga:
            releases = search_manga_releases(item, db=db, limit=20)
        else:
            releases = search_comic_releases(item, db=db, limit=20)
    finally:
        item.title = orig
    return releases



@router.post("/{item_id}/issues/{issue_id}/grab")
def grab_issue(item_id: int, issue_id: int, body: dict, db: Session = Depends(get_db), _: list = Depends(require_permission("download"))):
    """Grab a specific release for a single comic/manga issue."""
    from app.models import ComicIssue
    item = db.get(MediaItem, item_id)
    issue = db.get(ComicIssue, issue_id)
    if not item or not issue or issue.media_item_id != item_id:
        raise HTTPException(404, "Not found")
    release = body.get("release") or body
    if not release.get("title") and not release.get("download_url") and not release.get("magnet"):
        raise HTTPException(400, "release payload required")
    # Bias title so organize can match issue number from filename
    release = dict(release)
    num = issue.issue_number or ""
    if num and num not in (release.get("title") or ""):
        release["title"] = f"{item.title} #{num} {release.get('title') or ''}".strip()
    grab_release(db, item, release)
    issue.status = ItemStatus.downloading
    db.add(issue)
    db.commit()
    return {"ok": True, "issue_id": issue.id, "title": release.get("title")}


@router.put("/issues/{issue_id}/monitor")
def toggle_issue_monitor(issue_id: int, body: dict, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage"))):
    from app.models import ComicIssue
    issue = db.get(ComicIssue, issue_id)
    if not issue:
        raise HTTPException(404, "Not found")
    if "monitored" in body:
        issue.monitored = bool(body["monitored"])
    db.add(issue)
    db.commit()
    return {"id": issue.id, "monitored": issue.monitored}


@router.post("/issues/{issue_id}/progress")
def update_issue_progress(issue_id: int, body: IssueProgressIn, db: Session = Depends(get_db), _: list = Depends(require_permission("library.view"))):
    """Persist reading progress for a single issue. Called by the reader
    (ComicReader in comics.jsx) on a debounced page-change and again on
    close, mirroring how music's /track/{id}/played is called from a
    passive playback trigger rather than a library-management action —
    library.view is enough, this isn't editing library content.

    last_page_read is the 0-based index of the page currently on screen.
    is_read is left for the caller to set explicitly (the reader marks it
    true once the last page has been viewed, or the person can revert it
    from the issues table) rather than inferred here from a page number,
    since "reached the last page" and "read" aren't quite the same thing
    for a caller that doesn't send a total page count in the same request.
    """
    from datetime import datetime, timezone
    from app.models import ComicIssue
    issue = db.get(ComicIssue, issue_id)
    if not issue:
        raise HTTPException(404, "Not found")
    if body.last_page_read is not None:
        issue.last_page_read = max(0, body.last_page_read)
    if body.is_read is not None:
        issue.is_read = body.is_read
    # Always stamp last_read_at on any progress write so Continue Reading
    # can order by "most recently opened", even for unfinished issues.
    issue.last_read_at = datetime.now(timezone.utc)
    db.add(issue)
    # Soft tracking writeback on parent series when reading issues
    try:
        from app.models import TrackedItem, MediaItem
        series_id = getattr(issue, "media_item_id", None) or getattr(issue, "comic_id", None)
        if series_id:
            tracked = db.query(TrackedItem).filter(TrackedItem.media_item_id == series_id).first()
            now = datetime.now(timezone.utc)
            pct = 100.0 if body.is_read else max(1.0, float(issue.last_page_read or 0))
            # crude progress signal; refined when total pages known
            if tracked:
                tracked.progress_percent = max(tracked.progress_percent or 0, min(99.0, pct) if not body.is_read else max(tracked.progress_percent or 0, 5.0))
                if (tracked.status or "planned") in ("planned", "on_hold", ""):
                    tracked.status = "in_progress"
                    tracked.started_at = tracked.started_at or now
                tracked.updated_at = now
                db.add(tracked)
            else:
                db.add(TrackedItem(
                    media_item_id=series_id,
                    status="in_progress",
                    progress_percent=min(99.0, pct) if not body.is_read else 5.0,
                    started_at=now,
                ))
    except Exception:
        pass
    db.commit()
    return {
        "id": issue.id,
        "last_page_read": issue.last_page_read,
        "is_read": issue.is_read,
        "last_read_at": issue.last_read_at.isoformat() if issue.last_read_at else None,
    }


@router.get("/issues/{issue_id}/pages")
def issue_pages(issue_id: int, db: Session = Depends(get_db), _: list = Depends(require_permission("library.view"))):
    """List of readable pages for a single issue's file — see
    app/services/comic_reader.py for the format-by-format breakdown."""
    from app.models import ComicIssue
    from app.services.comic_reader import ComicReadError, list_pages
    issue = db.get(ComicIssue, issue_id)
    if not issue:
        raise HTTPException(404, "Not found")
    if not issue.file_path:
        raise HTTPException(400, "Issue has no file on disk")
    try:
        return list_pages(issue.file_path)
    except ComicReadError as e:
        raise HTTPException(400, str(e))


@router.get("/issues/{issue_id}/page/{index}")
def issue_page(issue_id: int, index: int, db: Session = Depends(get_db), _: list = Depends(require_permission("library.view"))):
    """A single rendered page image, addressed by the 0-based index
    returned from issue_pages() above."""
    from app.models import ComicIssue
    from app.services.comic_reader import ComicReadError, read_page
    issue = db.get(ComicIssue, issue_id)
    if not issue:
        raise HTTPException(404, "Not found")
    if not issue.file_path:
        raise HTTPException(400, "Issue has no file on disk")
    try:
        data, mime = read_page(issue.file_path, index)
    except ComicReadError as e:
        raise HTTPException(400, str(e))
    return Response(content=data, media_type=mime)



@router.patch("/{item_id}/tag-manga")
def tag_manga(item_id: int, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage"))):
    item = db.get(MediaItem, item_id)
    if not item:
        raise HTTPException(404)
    item.quality_profile = "manga"
    db.add(item)
    db.commit()
    return {"ok": True, "id": item_id, "quality_profile": "manga"}


@router.get("/arcs/{arc_id}/reading-order")
def arc_reading_order(arc_id: int, db: Session = Depends(get_db)):
    """Ordered issues for a story arc (Mylar-style reading order)."""
    data = arcsvc.get_arc(db, arc_id)
    if not data:
        raise HTTPException(404, "arc not found")
    issues = data.get("issues") or data.get("items") or []
    # ensure sorted by reading_order / sequence if present
    def _key(x):
        return (
            x.get("reading_order")
            if isinstance(x, dict) and x.get("reading_order") is not None
            else x.get("sequence")
            if isinstance(x, dict)
            else 0,
            x.get("issue_number") if isinstance(x, dict) else 0,
        )
    try:
        issues = sorted(issues, key=_key)
    except Exception:
        pass
    return {"arc_id": arc_id, "title": data.get("title") or data.get("name"), "issues": issues, "count": len(issues)}


@router.post("/{item_id}/metatag")
def metatag_comic(item_id: int, body: dict | None = None, db: Session = Depends(get_db), _: list = Depends(require_permission("library.manage"))):
    """Apply ComicInfo-style metadata to the on-disk comic.

    Embeds ComicInfo.xml as a zip member for .cbz/.zip (what
    ComicTagger/Kavita/ComicRack actually read) via
    app/services/comic_metadata.embed_comicinfo(); falls back to a
    sidecar file for formats that can't be rewritten in place
    (.cbr/.rar — see that module's docstring for why) or any other
    extension. Both paths go through _assert_under_library first —
    unlike the version this replaced, a path outside the library
    roots or a write failure is a 400, not a silently-swallowed
    "ok": true with a failure note buried in `path`.
    """
    item = db.get(MediaItem, item_id)
    if not item:
        raise HTTPException(404, "not found")
    body = body or {}
    meta = {
        "title": body.get("title") or item.title,
        "series": body.get("series") or item.title,
        "number": body.get("number") or body.get("issue_number"),
        "year": body.get("year") or item.year,
        "summary": body.get("summary") or item.overview,
        "publisher": body.get("publisher"),
        "web": body.get("web"),
    }
    path = item.file_path
    written = False
    embedded = False
    note = "metadata stored on item"
    if path:
        from pathlib import Path as P
        from app.services.comic_metadata import ComicMetaError, EMBEDDABLE_EXTENSIONS, embed_comicinfo, write_sidecar
        try:
            if P(path).suffix.lower() in EMBEDDABLE_EXTENSIONS:
                member = embed_comicinfo(path, meta)
                written = True
                embedded = True
                note = f"{path} (embedded: {member})"
            else:
                note = write_sidecar(path, meta)
                written = True
        except ComicMetaError as e:
            raise HTTPException(400, str(e))
    # persist overview if provided
    if body.get("summary"):
        item.overview = body["summary"]
        db.add(item)
        db.commit()
    return {"ok": True, "item_id": item_id, "written": written, "embedded": embedded, "path": note, "meta": meta}
