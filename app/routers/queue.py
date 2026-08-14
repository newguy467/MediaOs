"""Download queue + history (Radarr/Sonarr Activity equivalent)."""
from __future__ import annotations

from datetime import datetime

from app.auth import require_permission
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.clients.qbittorrent import qbittorrent_client
from app.database import get_db
from app.models import Activity, Download, Episode, ItemStatus, MediaItem, Game
from app.services.sse import publish as sse_publish

router = APIRouter(prefix="/queue", tags=["queue"],
    dependencies=[Depends(require_permission("queue.view", "queue.manage", "download"))],
)


class QueueItem(BaseModel):
    download_id: int
    media_item_id: int | None = None
    game_id: int | None = None
    title: str
    media_type: str | None
    status: str
    release_title: str | None
    quality_score: int | None
    indexer: str | None
    progress: float | None = None
    qbit_state: str | None = None
    torrent_hash: str | None = None
    added_at: datetime | None = None
    episode: str | None = None
    category: str | None = None
    priority: int | None = None


@router.get("", response_model=list[QueueItem])
def get_queue(db: Session = Depends(get_db)):
    """Active downloads (grabbed / downloading) merged with qB progress."""
    rows = (
        db.query(Download)
        .options(joinedload(Download.media_item), joinedload(Download.episode))
        .filter(Download.status.in_(["grabbed", "downloading"]))
        .order_by(Download.added_at.desc())
        .limit(100)
        .all()
    )
    torrents = {}
    try:
        from app.services.download_clients import list_torrents as _list_all
        for t in _list_all() or []:
            h = (t.get("hash") or t.get("hashString") or t.get("infoHash") or t.get("gid") or "").lower()
            if not h:
                continue
            # normalize progress 0..1
            prog = t.get("progress")
            if prog is None and t.get("percentDone") is not None:
                prog = float(t["percentDone"])
            if prog is None and t.get("completedLength") and t.get("totalLength"):
                try:
                    prog = float(t["completedLength"]) / max(1, float(t["totalLength"]))
                except Exception:
                    prog = None
            if isinstance(prog, (int, float)) and prog > 1:
                prog = prog / 100.0
            state = t.get("state") or t.get("status") or t.get("qbit_state")
            torrents[h] = {**t, "progress": prog, "state": state, "hash": h}
    except Exception:
        try:
            for cat in (None, "mediaos", "mediaos-tv", "mediaos-music", "mediaos-books", "mediaos-audiobooks", "mediaos-games"):
                for tt in qbittorrent_client.list_torrents(category=cat):
                    h = (tt.get("hash") or "").lower()
                    if h:
                        torrents[h] = tt
        except Exception:
            pass

    out: list[QueueItem] = []
    for d in rows:
        item = d.media_item
        ep = d.episode
        game = None
        if getattr(d, "game_id", None) and not item:
            game = db.get(Game, d.game_id)
        title = item.title if item else (game.title if game else (d.release_title or "?"))
        ep_label = None
        if ep:
            ep_label = f"S{ep.season_number:02d}E{ep.episode_number:02d}"
            title = f"{title} {ep_label}"
        progress = None
        state = None
        cat = None
        prio = None
        h = (d.torrent_hash or "").lower()
        if h and h in torrents:
            progress = torrents[h].get("progress")
            state = torrents[h].get("state")
            cat = torrents[h].get("category")
            prio = torrents[h].get("priority")
        out.append(
            QueueItem(
                download_id=d.id,
                media_item_id=d.media_item_id,
                game_id=getattr(d, "game_id", None),
                title=title,
                media_type=(item.media_type.value if item else ("game" if getattr(d, "game_id", None) else None)),
                status=d.status,
                release_title=d.release_title,
                quality_score=d.quality_score,
                indexer=d.indexer,
                progress=progress,
                qbit_state=state,
                torrent_hash=d.torrent_hash,
                added_at=d.added_at,
                episode=ep_label,
                category=cat,
                priority=prio,
            )
        )
    try:
        sse_publish("queue", {
            "items": [
                {
                    "download_id": q.download_id,
                    "title": q.title,
                    "progress": q.progress,
                    "status": q.status,
                    "qbit_state": q.qbit_state,
                }
                for q in out
            ]
        })
    except Exception:
        pass
    return out


@router.get("/history")
def get_history(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    """Recent downloads of any status + activity events."""
    downloads = (
        db.query(Download)
        .options(joinedload(Download.media_item), joinedload(Download.episode))
        .order_by(Download.added_at.desc())
        .limit(limit)
        .all()
    )
    dl_out = []
    for d in downloads:
        item = d.media_item
        dl_out.append(
            {
                "download_id": d.id,
                "title": item.title if item else d.release_title,
                "media_type": item.media_type.value if item else None,
                "status": d.status,
                "release_title": d.release_title,
                "quality_score": d.quality_score,
                "indexer": d.indexer,
                "added_at": d.added_at,
            }
        )
    events = (
        db.query(Activity)
        .order_by(Activity.created_at.desc())
        .limit(limit)
        .all()
    )
    ev_out = [
        {
            "id": e.id,
            "event": e.event,
            "message": e.message,
            "media_type": e.media_type,
            "created_at": e.created_at,
            "release_title": e.release_title,
        }
        for e in events
    ]
    return {"downloads": dl_out, "events": ev_out}


@router.delete("/{download_id}", status_code=204)
def remove_queue_item(
    download_id: int,
    delete_files: bool = Query(False),
    blocklist: bool = Query(False),
    db: Session = Depends(get_db),
):
    d = db.get(Download, download_id)
    if not d:
        return
    if blocklist and d.release_title:
        try:
            from app.models import Blocklist
            bl = Blocklist(
                release_title=d.release_title,
                torrent_hash=d.torrent_hash,
                reason="manual queue remove",
                media_item_id=d.media_item_id,
            )
            db.add(bl)
        except Exception:
            pass
    if d.torrent_hash:
        try:
            qbittorrent_client.delete_torrent(d.torrent_hash, delete_files=delete_files)
        except Exception:
            pass
    if d.episode_id:
        ep = db.get(Episode, d.episode_id)
        if ep and ep.status in (ItemStatus.downloading, ItemStatus.wanted):
            if not blocklist:
                ep.status = ItemStatus.wanted
            db.add(ep)
    elif d.media_item_id:
        item = db.get(MediaItem, d.media_item_id)
        if item and item.status in (ItemStatus.downloading, ItemStatus.wanted):
            if not blocklist:
                item.status = ItemStatus.wanted
            db.add(item)
    db.delete(d)
    db.commit()
    try:
        sse_publish("queue", {"action": "removed", "download_id": download_id})
    except Exception:
        pass


@router.post("/{download_id}/blocklist")
def blocklist_download(download_id: int, db: Session = Depends(get_db)):
    """Remove from queue and blocklist the release title."""
    d = db.get(Download, download_id)
    if not d:
        return {"ok": False, "error": "not found"}
    if d.release_title:
        try:
            from app.models import Blocklist
            exists = (
                db.query(Blocklist)
                .filter(Blocklist.release_title == d.release_title)
                .first()
            )
            if not exists:
                db.add(
                    Blocklist(
                        release_title=d.release_title,
                        torrent_hash=d.torrent_hash,
                        reason="queue blocklist",
                        media_item_id=d.media_item_id,
                    )
                )
        except Exception as e:
            return {"ok": False, "error": str(e)}
    remove_queue_item(download_id, delete_files=False, blocklist=True, db=db)
    return {"ok": True}


@router.post("/{download_id}/retry")
def retry_download(download_id: int, db: Session = Depends(get_db)):
    """Mark parent as wanted again and clear last_searched so scheduler re-searches."""
    d = db.get(Download, download_id)
    if not d:
        return {"ok": False, "error": "not found"}
    if d.episode_id:
        ep = db.get(Episode, d.episode_id)
        if ep:
            ep.status = ItemStatus.wanted
            ep.last_searched_at = None
            db.add(ep)
    elif d.media_item_id:
        item = db.get(MediaItem, d.media_item_id)
        if item:
            item.status = ItemStatus.wanted
            item.last_searched_at = None
            db.add(item)
    d.status = "failed"
    db.add(d)
    db.commit()
    try:
        sse_publish("queue", {"action": "retry", "download_id": download_id})
    except Exception:
        pass
    return {"ok": True}


@router.post("/torrent/{torrent_hash}/pause")
def queue_pause(torrent_hash: str):
    from app.services.download_clients import pause_torrent
    return pause_torrent(torrent_hash)


@router.post("/torrent/{torrent_hash}/resume")
def queue_resume(torrent_hash: str):
    from app.services.download_clients import resume_torrent
    return resume_torrent(torrent_hash)


@router.post("/torrent/{torrent_hash}/recheck")
def queue_recheck(torrent_hash: str):
    from app.services.download_clients import recheck_torrent
    return recheck_torrent(torrent_hash)


@router.post("/torrent/{torrent_hash}/priority")
def queue_priority(torrent_hash: str, priority: int = Query(3, ge=1, le=5)):
    """Set queue priority band: 1=top 2=high 3=normal 4=low 5=bottom."""
    from app.services.download_clients import set_torrent_priority
    return set_torrent_priority(torrent_hash, priority)


@router.post("/torrent/{torrent_hash}/category")
def queue_category(torrent_hash: str, category: str = Query("mediaos")):
    from app.services.download_clients import set_torrent_category
    return set_torrent_category(torrent_hash, category)


@router.post("/torrent/{torrent_hash}/force-start")
def queue_force_start(torrent_hash: str, value: bool = Query(True)):
    from app.services.download_clients import force_start_torrent
    return force_start_torrent(torrent_hash, value)
