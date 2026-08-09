from fastapi import APIRouter, Depends
from app.auth import require_admin
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Activity, Blocklist
from app.services.blocklist import add_to_blocklist
from app.services.wanted import search_all_missing
from app.services.quality import (
    default_movie_profile,
    default_tv_profile,
    parse_release_title,
    score_release,
)
from pydantic import BaseModel

router = APIRouter(tags=["system"])


@router.get("/activity")
def list_activity(
    limit: int = 100,
    event: str | None = None,
    media_type: str | None = None,
    db: Session = Depends(get_db),
):
    """Sonarr/Radarr-style history feed."""
    q = db.query(Activity)
    if event:
        # allow comma-separated event names / prefixes
        parts = [e.strip() for e in event.split(",") if e.strip()]
        if parts:
            from sqlalchemy import or_
            q = q.filter(or_(*[Activity.event.ilike(f"%{p}%") for p in parts]))
    if media_type:
        q = q.filter(Activity.media_type == media_type)
    rows = q.order_by(Activity.created_at.desc()).limit(min(limit, 500)).all()
    out = []
    for r in rows:
        # normalize event for UI badges
        ev = (r.event or "").lower()
        if "grab" in ev:
            kind = "grabbed"
        elif "import" in ev or "organ" in ev:
            kind = "imported"
        elif "fail" in ev:
            kind = "failed"
        elif "block" in ev:
            kind = "blocked"
        elif "upgrade" in ev:
            kind = "upgraded"
        elif "search" in ev:
            kind = "searched"
        elif "delet" in ev:
            kind = "deleted"
        elif "rename" in ev:
            kind = "renamed"
        else:
            kind = ev or "event"
        out.append({
            "id": r.id,
            "event": r.event,
            "event_kind": kind,
            "message": r.message,
            "media_type": r.media_type,
            "media_item_id": r.media_item_id,
            "release_title": r.release_title or r.message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "data": {
                "releaseTitle": r.release_title or r.message,
                "eventType": kind,
                "sourceTitle": r.release_title,
            },
        })
    return out


@router.get("/blocklist")
def list_blocklist(db: Session = Depends(get_db)):
    rows = db.query(Blocklist).order_by(Blocklist.added_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "release_title": r.release_title,
            "reason": r.reason,
            "torrent_hash": r.torrent_hash,
            "added_at": r.added_at,
        }
        for r in rows
    ]


class BlocklistIn(BaseModel):
    release_title: str
    reason: str | None = None
    torrent_hash: str | None = None
    media_item_id: int | None = None


@router.post("/blocklist")
def create_blocklist(payload: BlocklistIn, db: Session = Depends(get_db)):
    row = add_to_blocklist(
        db,
        payload.release_title,
        reason=payload.reason,
        torrent_hash=payload.torrent_hash,
        media_item_id=payload.media_item_id,
    )
    return {"id": row.id, "release_title": row.release_title}


@router.get("/quality/profiles")
def list_profiles():
    movie = default_movie_profile()
    tv = default_tv_profile()
    return {
        "movie": {
            "name": movie.name,
            "cutoff": movie.cutoff,
            "resolutions": movie.resolutions,
            "preferred_sources": movie.preferred_sources,
            "formats": [{"name": f.name, "score": f.score, "reject": f.reject} for f in movie.custom_formats],
        },
        "tv": {
            "name": tv.name,
            "cutoff": tv.cutoff,
            "resolutions": tv.resolutions,
            "preferred_sources": tv.preferred_sources,
            "formats": [{"name": f.name, "score": f.score, "reject": f.reject} for f in tv.custom_formats],
        },
    }


class ScoreIn(BaseModel):
    title: str
    seeders: int | None = 0
    size: int | None = 0
    media_type: str = "movie"


@router.post("/quality/score")
def score_title(payload: ScoreIn):
    profile = default_tv_profile() if payload.media_type == "tv" else default_movie_profile()
    result = score_release(
        payload.title,
        seeders=payload.seeders,
        size=payload.size,
        profile=profile,
    )
    parsed = result.parsed
    return {
        "accepted": result.accepted,
        "score": result.score,
        "rejection_reason": result.rejection_reason,
        "matched_formats": result.matched_formats,
        "parsed": {
            "resolution": parsed.resolution if parsed else None,
            "source": parsed.source if parsed else None,
            "codec": parsed.codec if parsed else None,
            "hdr": parsed.hdr if parsed else [],
            "audio": parsed.audio if parsed else [],
            "release_group": parsed.release_group if parsed else None,
        },
    }


@router.post("/search-all-missing")
def api_search_all_missing(limit: int = 40, db: Session = Depends(get_db)):
    """Global wanted search across movies, TV episodes, and music."""
    return search_all_missing(db, limit=limit)


@router.get("/storage")
def storage_stats():
    """Library disk usage + largest files (MediaOs storage maintenance parity)."""
    from app.services.storage import library_storage
    return library_storage()


@router.delete("/blocklist/{item_id}")
def delete_blocklist(item_id: int, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    row = db.get(Blocklist, item_id)
    if not row:
        from fastapi import HTTPException
        raise HTTPException(404)
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/logs")
def list_logs(_: str = Depends(require_admin)):
    """List available log files under the log directory."""
    from app.logging_config import list_log_files, log_dir
    return {"dir": str(log_dir()), "files": list_log_files()}


@router.get("/logs/tail")
def tail_logs(file: str = "mediaos.log", lines: int = 200, level: str | None = None, _: str = Depends(require_admin)):
    """Tail a log file for the debug UI."""
    from app.logging_config import tail_log
    lines = max(10, min(lines, 2000))
    return tail_log(file, lines=lines, level=level)


@router.get("/logs/search")
def search_logs(q: str, file: str = "mediaos.log", limit: int = 100, _: str = Depends(require_admin)):
    from app.logging_config import search_log
    return search_log(file, query=q, limit=max(1, min(limit, 500)))


@router.post("/logs/level")
def set_log_level(level: str = "INFO", _: str = Depends(require_admin)):
    """Runtime log level change for mediaos.* loggers."""
    import logging
    lv = getattr(logging, level.upper(), None)
    if lv is None:
        from fastapi import HTTPException
        raise HTTPException(400, "Invalid level")
    logging.getLogger().setLevel(lv)
    logging.getLogger("mediaos").setLevel(lv)
    return {"ok": True, "level": level.upper()}


@router.get("/cf-bypass")
def cf_bypass_status():
    """Status of builtin CF bypass + optional FlareSolverr sidecar."""
    from app.clients.cf_bypass import cf_bypass_client
    return cf_bypass_client.status()

@router.get("/rate-limit")
def rate_limit_status():
    """Indexer delay/backoff registry snapshot (interactive search health)."""
    from app.services import rate_limit
    return rate_limit.snapshot()


@router.post("/rate-limit/clear")
def rate_limit_clear(key: str | None = None):
    from app.services import rate_limit
    rate_limit.clear_backoff(key)
    return {"ok": True, "snapshot": rate_limit.snapshot()}

@router.get("/indexer-capabilities")
def indexer_capabilities():
    """Per-indexer search-type capability matrix."""
    from app.services.indexer_capabilities import matrix
    return {"indexers": matrix()}



# ── Homelab Links (Organizr-lite) ──────────────────────────────────────────

class HomelabLinksBody(BaseModel):
    links: list[dict]


@router.get("/homelab-links")
def homelab_links_get(db: Session = Depends(get_db)):
    from app.services.homelab_links import get_links
    return {"links": get_links(db)}


@router.put("/homelab-links")
def homelab_links_put(body: HomelabLinksBody, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    from app.services.homelab_links import save_links
    saved = save_links(db, body.links)
    return {"links": saved, "ok": True}


@router.get("/now-playing")
def now_playing():
    """Plex/Tautulli now-playing for the dashboard widget."""
    from app.services.now_playing import get_now_playing
    return get_now_playing()
