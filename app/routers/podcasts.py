from __future__ import annotations

from datetime import datetime

from app.auth import require_permission
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.clients.podcast_rss import podcast_rss_client
from app.database import get_db
from app.models import Podcast, PodcastEpisode
from app.services.podcasts import add_podcast, download_episode, refresh_podcast

router = APIRouter(prefix="/podcasts", tags=["podcasts"])


class PodcastOut(BaseModel):
    id: int
    feed_url: str
    title: str
    author: str | None
    description: str | None
    image: str | None
    monitored: bool
    auto_download: bool
    download_window_days: int
    episode_count: int
    last_checked_at: datetime | None
    added_at: datetime

    class Config:
        from_attributes = True


class EpisodeOut(BaseModel):
    id: int
    title: str
    audio_url: str
    pub_date: str | None
    duration_seconds: int | None
    episode_number: int | None
    status: str
    file_path: str | None
    downloaded_at: datetime | None

    class Config:
        from_attributes = True


@router.get("/search")
def search_podcasts(query: str):
    return podcast_rss_client.search(query)


@router.get("", response_model=list[PodcastOut])
def list_podcasts(db: Session = Depends(get_db)):
    return db.query(Podcast).order_by(Podcast.title).all()



class PodcastBulkIn(BaseModel):
    ids: list[int]
    monitored: bool | None = None
    auto_download: bool | None = None


@router.post("/bulk")
def bulk_podcasts(payload: PodcastBulkIn, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "download"))):
    """Bulk monitor / auto_download for podcast subscriptions."""
    q = db.query(Podcast).filter(Podcast.id.in_(payload.ids))
    n = 0
    for row in q.all():
        if payload.monitored is not None:
            row.monitored = payload.monitored
        if payload.auto_download is not None:
            row.auto_download = payload.auto_download
        db.add(row)
        n += 1
    db.commit()
    return {"ok": True, "updated": n}


@router.get("/{podcast_id}", response_model=PodcastOut)
def get_podcast(podcast_id: int, db: Session = Depends(get_db)):
    row = db.get(Podcast, podcast_id)
    if not row:
        raise HTTPException(404, "Not found")
    return row


class PodcastCreate(BaseModel):
    feed_url: str
    monitored: bool = True
    auto_download: bool | None = None


@router.post("", response_model=PodcastOut)
def create_podcast(payload: PodcastCreate, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "download"))):
    existing = db.query(Podcast).filter(Podcast.feed_url == payload.feed_url).first()
    if existing:
        raise HTTPException(409, "Already subscribed")
    try:
        return add_podcast(
            db, payload.feed_url, monitored=payload.monitored, auto_download=payload.auto_download
        )
    except Exception as exc:
        raise HTTPException(400, f"Could not read feed: {exc}")


class PodcastUpdate(BaseModel):
    monitored: bool | None = None
    auto_download: bool | None = None
    download_window_days: int | None = None


@router.put("/{podcast_id}", response_model=PodcastOut)
def update_podcast(podcast_id: int, payload: PodcastUpdate, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "download"))):
    row = db.get(Podcast, podcast_id)
    if not row:
        raise HTTPException(404, "Not found")
    if payload.monitored is not None:
        row.monitored = payload.monitored
    if payload.auto_download is not None:
        row.auto_download = payload.auto_download
    if payload.download_window_days is not None:
        row.download_window_days = payload.download_window_days
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{podcast_id}", status_code=204)
def delete_podcast(podcast_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "download"))):
    row = db.get(Podcast, podcast_id)
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row)
    db.commit()


@router.get("/{podcast_id}/episodes", response_model=list[EpisodeOut])
def list_episodes(podcast_id: int, db: Session = Depends(get_db)):
    row = db.get(Podcast, podcast_id)
    if not row:
        raise HTTPException(404, "Not found")
    return (
        db.query(PodcastEpisode)
        .filter(PodcastEpisode.podcast_id == podcast_id)
        .order_by(PodcastEpisode.added_at.desc())
        .all()
    )


@router.post("/{podcast_id}/refresh")
def refresh(podcast_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "download"))):
    row = db.get(Podcast, podcast_id)
    if not row:
        raise HTTPException(404, "Not found")
    try:
        return refresh_podcast(db, row)
    except Exception as exc:
        raise HTTPException(502, f"Feed refresh failed: {exc}")


@router.post("/{podcast_id}/episodes/{episode_id}/download", response_model=EpisodeOut)
def download(podcast_id: int, episode_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "download"))):
    ep = db.get(PodcastEpisode, episode_id)
    if not ep or ep.podcast_id != podcast_id:
        raise HTTPException(404, "Not found")
    try:
        return download_episode(db, ep)
    except Exception as exc:
        raise HTTPException(502, f"Download failed: {exc}")


@router.get("/{podcast_id}/episodes/{episode_id}")
def get_episode(podcast_id: int, episode_id: int, db: Session = Depends(get_db)):
    import json
    ep = db.get(PodcastEpisode, episode_id)
    if not ep or ep.podcast_id != podcast_id:
        raise HTTPException(404, "Episode not found")
    chapters = []
    if ep.chapters_json:
        try:
            chapters = json.loads(ep.chapters_json)
        except Exception:
            chapters = []
    return {
        "id": ep.id,
        "title": ep.title,
        "audio_url": ep.audio_url,
        "duration_seconds": ep.duration_seconds,
        "status": ep.status.value if hasattr(ep.status, "value") else str(ep.status),
        "file_path": ep.file_path,
        "chapters": chapters,
        "pub_date": ep.pub_date,
    }
