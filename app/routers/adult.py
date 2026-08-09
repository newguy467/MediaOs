"""Adult library (Whisparr-class) — full Movies-parity pipeline + passcode gate."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.config import settings
from app.database import get_db
from app.models import ItemStatus, MediaItem, MediaType
from app.services import adult_gate
from app.services.adult_gate import require_adult_unlock
from app.services.grab import grab_release
from app.services.search import find_best_adult_release, search_adult_releases


def _tpdb_int_id(raw) -> int:
    """Map TPDB string/int id to stable positive int for MediaItem.external_id."""
    if raw is None:
        raise ValueError("missing id")
    if isinstance(raw, int):
        return abs(raw) % (2**31 - 1) or 1
    s = str(raw).strip()
    if s.isdigit():
        return int(s) % (2**31 - 1) or 1
    # stable hash
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) % (2**31 - 1)
    return h or 1

router = APIRouter(
    prefix="/adult",
    tags=["adult"],
    dependencies=[Depends(require_permission("library.view", "library.manage"))],
)


class UnlockBody(BaseModel):
    passcode: str = Field(..., min_length=1, max_length=128)


class SetPasscodeBody(BaseModel):
    passcode: str = Field(..., min_length=4, max_length=128)
    current_passcode: str | None = None


class AdultCreate(BaseModel):
    title: str | None = None
    year: int | None = None
    external_id: str | int | None = None  # TPDB id when available
    overview: str | None = None
    poster_path: str | None = None
    monitored: bool = True
    quality_profile: str | None = None
    search_now: bool = False  # grab best release after add


class AdultUpdate(BaseModel):
    title: str | None = None
    year: int | None = None
    overview: str | None = None
    poster_path: str | None = None
    monitored: bool | None = None
    quality_profile: str | None = None
    status: str | None = None


class AdultOut(BaseModel):
    id: int
    title: str
    year: int | None = None
    status: str | None = None
    monitored: bool = True
    poster_path: str | None = None
    overview: str | None = None
    file_path: str | None = None
    quality_profile: str | None = None
    external_id: str | None = None
    quality_score: int | None = None

    class Config:
        from_attributes = True


class GrabReleaseIn(BaseModel):
    title: str | None = None
    download_url: str = ""
    indexer: str | None = None
    size: int | None = None
    seeders: int | None = None
    protocol: str | None = None
    quality_score: int | None = None
    info_hash: str | None = None


class AdultFileIn(BaseModel):
    path: str | None = None
    clear: bool = False


class BulkIn(BaseModel):
    ids: list[int]
    monitored: bool | None = None
    quality_profile: str | None = None


def _out(item: MediaItem) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "year": item.year,
        "status": item.status.value if item.status else None,
        "monitored": bool(item.monitored),
        "poster_path": item.poster_path,
        "overview": item.overview,
        "file_path": item.file_path,
        "quality_profile": item.quality_profile,
        "external_id": item.external_id,
        "external_source": getattr(item, "external_source", None),
        "quality_score": getattr(item, "quality_score", None),
    }


# ── Passcode ───────────────────────────────────────────────────────────────

@router.get("/status")
def adult_status():
    return {
        "module": "adult",
        "passcode_enabled": bool(getattr(settings, "adult_passcode_enabled", True)),
        "passcode_set": adult_gate.passcode_is_set(),
        "library_path": getattr(settings, "adult_library_path", "/adult"),
        "unlock_ttl_minutes": int(getattr(settings, "adult_unlock_ttl_minutes", 60) or 60),
        "locked": bool(
            getattr(settings, "adult_passcode_enabled", True) and adult_gate.passcode_is_set()
        ),
    }



@router.get("/metadata/search")
def metadata_search(
    query: str,
    _unlock=Depends(require_adult_unlock),
):
    """TPDB metadata lookup (requires TPDB_API_KEY). Empty list if key missing."""
    from app.clients.tpdb import tpdb_client
    if not query.strip():
        return []
    try:
        return tpdb_client.search_movies(query.strip())
    except Exception as e:
        raise HTTPException(502, f"TPDB search failed: {e}") from e


@router.get("/metadata/status")
def metadata_status(_unlock=Depends(require_adult_unlock)):
    from app.clients.tpdb import tpdb_client
    return {
        "provider": "tpdb",
        "configured": tpdb_client.configured(),
        "hint": "Set TPDB_API_KEY in Settings → Adult / .env for metadata search-add",
    }

@router.post("/unlock")
def unlock(body: UnlockBody, request: Request):
    if not adult_gate.passcode_is_set():
        raise HTTPException(400, "No passcode configured. Set one in Settings → Adult first.")
    from app.services import rate_limit

    client_ip = request.client.host if request.client else "unknown"
    rl_key = f"adult_unlock:{client_ip}"
    remaining = rate_limit.remaining_backoff(rl_key)
    if remaining > 0:
        raise HTTPException(
            429,
            f"Too many failed passcode attempts. Try again in {int(remaining)}s.",
            headers={"Retry-After": str(int(remaining) + 1)},
        )
    if not adult_gate.verify_passcode(body.passcode):
        rate_limit.record_failure(rl_key, "invalid passcode", base_seconds=20.0)
        raise HTTPException(403, "Invalid passcode")
    rate_limit.record_success(rl_key)
    return adult_gate.issue_unlock_token()


@router.post("/passcode")
def set_passcode(body: SetPasscodeBody, _=Depends(require_permission("settings"))):
    if adult_gate.passcode_is_set():
        if not body.current_passcode or not adult_gate.verify_passcode(body.current_passcode):
            raise HTTPException(403, "Current passcode required to change it")
    h = adult_gate.set_passcode(body.passcode)
    try:
        from app.database import SessionLocal
        from app.models import AppSetting
        db = SessionLocal()
        try:
            row = db.query(AppSetting).filter(AppSetting.key == "adult_passcode_hash").one_or_none()
            if row:
                row.value = h
            else:
                db.add(AppSetting(key="adult_passcode_hash", value=h))
            db.commit()
        finally:
            db.close()
    except Exception:
        pass
    return {"ok": True, "passcode_set": True}


# ── Library ────────────────────────────────────────────────────────────────

@router.get("")
def list_adult(db: Session = Depends(get_db), _unlock=Depends(require_adult_unlock)):
    rows = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.adult)
        .order_by(MediaItem.title.asc())
        .all()
    )
    return [_out(r) for r in rows]


@router.post("")
def add_adult(
    payload: AdultCreate,
    db: Session = Depends(get_db),
    _unlock=Depends(require_adult_unlock),
    _=Depends(require_permission("library.manage", "download")),
):
    from app.clients.tpdb import tpdb_client

    title = (payload.title or "").strip()
    overview = payload.overview
    poster = payload.poster_path
    year = payload.year
    external_id = payload.external_id

    # Prefer TPDB details when external_id is a TPDB id
    if external_id and tpdb_client.configured():
        try:
            details = tpdb_client.get_movie(external_id)
            title = details.get("title") or title
            year = details.get("year") if details.get("year") is not None else year
            overview = details.get("overview") or overview
            poster = details.get("poster_path") or poster
            external_id = details.get("external_id") or external_id
        except Exception:
            pass

    if not title:
        raise HTTPException(400, "title or TPDB external_id required")

    if external_id:
        existing = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.adult, MediaItem.external_id == str(external_id))
            .one_or_none()
        )
        if existing:
            raise HTTPException(409, "Already in adult library")

    item = MediaItem(
        media_type=MediaType.adult,
        external_id=str(external_id) if external_id else f"adult:{title}:{year or ''}",
        external_source="tpdb" if external_id and tpdb_client.configured() else None,
        title=title,
        year=year,
        overview=overview,
        poster_path=poster,
        monitored=payload.monitored,
        quality_profile=payload.quality_profile,
        status=ItemStatus.wanted,
    )
    # external_source may not exist on model — soft set
    try:
        if hasattr(item, "external_source") and external_id and tpdb_client.configured():
            item.external_source = "tpdb"
    except Exception:
        pass

    db.add(item)
    db.commit()
    db.refresh(item)

    if payload.search_now:
        try:
            rel = find_best_adult_release(item, db=db)
            if rel:
                grab_release(db, item, rel)
            db.refresh(item)
        except Exception:
            pass
    return _out(item)


@router.post("/search-missing")
def search_all_missing_adult(
    limit: int = 40,
    db: Session = Depends(get_db),
    _unlock=Depends(require_adult_unlock),
    _=Depends(require_permission("download")),
):
    items = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.adult,
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
            rel = find_best_adult_release(item, db=db)
            item.last_searched_at = datetime.now(timezone.utc)
            db.add(item)
            if rel:
                grab_release(db, item, rel)
                grabbed += 1
            db.commit()
        except Exception:
            db.rollback()
    return {"searched": searched, "grabbed": grabbed}


@router.get("/{item_id}")
def get_adult(item_id: int, db: Session = Depends(get_db), _unlock=Depends(require_adult_unlock)):
    item = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.media_type == MediaType.adult).one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    return _out(item)


@router.patch("/{item_id}")
def update_adult(
    item_id: int,
    payload: AdultUpdate,
    db: Session = Depends(get_db),
    _unlock=Depends(require_adult_unlock),
):
    item = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.media_type == MediaType.adult).one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"]:
        try:
            data["status"] = ItemStatus(data["status"])
        except Exception:
            data.pop("status", None)
    for k, v in data.items():
        setattr(item, k, v)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _out(item)


@router.delete("/{item_id}", status_code=204)
def delete_adult(item_id: int, db: Session = Depends(get_db), _unlock=Depends(require_adult_unlock)):
    item = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.media_type == MediaType.adult).one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    db.delete(item)
    db.commit()
    return None


@router.post("/{item_id}/search")
def search_and_grab(
    item_id: int,
    db: Session = Depends(get_db),
    _unlock=Depends(require_adult_unlock),
    _=Depends(require_permission("download")),
):
    item = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.media_type == MediaType.adult).one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    rel = find_best_adult_release(item, db=db)
    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    if not rel:
        return None
    grab_release(db, item, rel)
    return {"title": rel.get("title"), "indexer": rel.get("indexer"), "score": rel.get("score")}


@router.get("/{item_id}/interactive-search")
def interactive_search_adult(
    item_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    _unlock=Depends(require_adult_unlock),
):
    from app.services.interactive_search import interactive_adult_search

    item = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.media_type == MediaType.adult).one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    item.last_searched_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    data = interactive_adult_search(item, db=db, limit=limit)

    def _map(rows):
        out = []
        for r in rows:
            out.append({
                "title": r.get("title") or "",
                "indexer": r.get("indexer"),
                "size": r.get("size"),
                "seeders": r.get("seeders"),
                "download_url": r.get("download_url") or r.get("magnet") or "",
                "score": r.get("_score") or r.get("score"),
                "matched_formats": list(r.get("_matched_formats") or []),
                "protocol": r.get("protocol"),
                "age_hours": r.get("age_hours") or r.get("age"),
                "rejected": bool(r.get("rejected")),
                "rejections": list(r.get("rejections") or []),
                "parsed_resolution": (r.get("_parsed") or {}).get("resolution"),
                "parsed_codec": (r.get("_parsed") or {}).get("codec"),
                "parsed_source": (r.get("_parsed") or {}).get("source"),
                "parsed_group": (r.get("_parsed") or {}).get("group"),
            })
        return out

    return {
        "media_type": "adult",
        "queries": data.get("queries") or [],
        "results": _map(data.get("results") or data.get("accepted") or []),
        "rejected": _map(data.get("rejected") or []),
        "indexer_results": data.get("indexer_stats") or data.get("indexer_results") or [],
        "total_raw": data.get("total_raw") or 0,
        "search_time_ms": data.get("search_time_ms") or 0,
        "rejection_breakdown": data.get("rejection_breakdown") or data.get("breakdown") or {},
        "accepted_count": len(data.get("results") or data.get("accepted") or []),
        "rejected_count": len(data.get("rejected") or []),
    }


@router.post("/{item_id}/grab")
def grab_selected(
    item_id: int,
    payload: GrabReleaseIn,
    db: Session = Depends(get_db),
    _unlock=Depends(require_adult_unlock),
    _=Depends(require_permission("download")),
):
    item = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.media_type == MediaType.adult).one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    release = {
        "title": payload.title,
        "download_url": payload.download_url,
        "indexer": payload.indexer,
        "size": payload.size,
        "seeders": payload.seeders,
        "protocol": payload.protocol or "torrent",
        "score": payload.quality_score,
        "info_hash": payload.info_hash,
    }
    if not release["download_url"]:
        raise HTTPException(400, "download_url required")
    dl = grab_release(db, item, release)
    return {"ok": True, "download_id": getattr(dl, "id", None), "title": release.get("title")}


@router.post("/{item_id}/refresh")
def refresh_adult(item_id: int, db: Session = Depends(get_db), _unlock=Depends(require_adult_unlock)):
    item = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.media_type == MediaType.adult).one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    # Title-based module: refresh is a no-op metadata touch (TPDB optional later)
    item.updated_at = datetime.now(timezone.utc) if hasattr(item, "updated_at") else None
    db.add(item)
    db.commit()
    return _out(item)


@router.post("/{item_id}/file")
def manage_file(
    item_id: int,
    payload: AdultFileIn,
    db: Session = Depends(get_db),
    _unlock=Depends(require_adult_unlock),
):
    item = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.media_type == MediaType.adult).one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    if payload.clear:
        item.file_path = None
        item.status = ItemStatus.missing
    elif payload.path:
        item.file_path = payload.path
        item.status = ItemStatus.downloaded
    db.add(item)
    db.commit()
    return _out(item)


@router.post("/bulk")
def bulk_update(
    payload: BulkIn,
    db: Session = Depends(get_db),
    _unlock=Depends(require_adult_unlock),
):
    q = db.query(MediaItem).filter(MediaItem.media_type == MediaType.adult, MediaItem.id.in_(payload.ids))
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


@router.post("/search")
def search_by_title(
    q: str,
    db: Session = Depends(get_db),
    _unlock=Depends(require_adult_unlock),
):
    class _Tmp:
        title = q
        year = None
        quality_profile = None
    results = search_adult_releases(_Tmp(), db=db)
    return {"query": q, "results": results[:40]}
