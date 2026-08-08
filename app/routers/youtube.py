"""YouTube / Creator channel tracking."""
from __future__ import annotations
from datetime import datetime
from app.auth import require_permission
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.clients.youtube import youtube_client
from app.database import get_db
from app.models import YouTubeChannel, YouTubeVideo
from app.services.youtube import add_channel, download_video, refresh_channel

router = APIRouter(prefix="/youtube", tags=["youtube"])

class ChannelOut(BaseModel):
    id: int
    channel_id: str | None
    playlist_id: str | None
    feed_url: str
    title: str
    author: str | None
    thumbnail: str | None
    monitored: bool
    auto_download: bool
    quality: str | None
    download_window_days: int
    video_count: int
    last_checked_at: datetime | None
    created_at: datetime
    class Config:
        from_attributes = True

class VideoOut(BaseModel):
    id: int
    video_id: str
    title: str
    url: str
    published_at: str | None
    thumbnail: str | None
    status: str
    file_path: str | None
    downloaded_at: datetime | None
    class Config:
        from_attributes = True

@router.get("/search")
def search_channels(query: str):
    return youtube_client.search_channels(query)

@router.get("/resolve")
def resolve(query: str):
    data = youtube_client.resolve_channel(query)
    if not data:
        raise HTTPException(404, "Could not resolve channel/playlist")
    return {"channel_id": data.get("channel_id"), "playlist_id": data.get("playlist_id"),
            "title": data.get("title"), "author": data.get("author"), "feed_url": data.get("feed_url"),
            "video_count": len(data.get("videos") or [])}

@router.get("", response_model=list[ChannelOut])
def list_channels(db: Session = Depends(get_db)):
    return db.query(YouTubeChannel).order_by(YouTubeChannel.title).all()

class ChannelCreate(BaseModel):
    query: str
    monitored: bool = True
    auto_download: bool | None = None
    quality: str | None = None

@router.post("", response_model=ChannelOut)
def create_channel(payload: ChannelCreate, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    try:
        return add_channel(db, payload.query, monitored=payload.monitored,
                           auto_download=payload.auto_download, quality=payload.quality)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(400, f"Could not add channel: {exc}")

class ChannelUpdate(BaseModel):
    monitored: bool | None = None
    auto_download: bool | None = None
    quality: str | None = None
    download_window_days: int | None = None

@router.put("/{channel_id}", response_model=ChannelOut)
def update_channel(channel_id: int, payload: ChannelUpdate, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    row = db.get(YouTubeChannel, channel_id)
    if not row: raise HTTPException(404, "Not found")
    if payload.monitored is not None: row.monitored = payload.monitored
    if payload.auto_download is not None: row.auto_download = payload.auto_download
    if payload.quality is not None: row.quality = payload.quality
    if payload.download_window_days is not None: row.download_window_days = payload.download_window_days
    db.add(row); db.commit(); db.refresh(row)
    return row

@router.delete("/{channel_id}", status_code=204)
def delete_channel(channel_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    row = db.get(YouTubeChannel, channel_id)
    if not row: raise HTTPException(404, "Not found")
    db.delete(row); db.commit()

@router.get("/{channel_id}/videos", response_model=list[VideoOut])
def list_videos(channel_id: int, db: Session = Depends(get_db)):
    if not db.get(YouTubeChannel, channel_id): raise HTTPException(404, "Not found")
    return db.query(YouTubeVideo).filter(YouTubeVideo.channel_id_fk == channel_id).order_by(YouTubeVideo.added_at.desc()).all()

@router.post("/{channel_id}/refresh")
def refresh(channel_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    row = db.get(YouTubeChannel, channel_id)
    if not row: raise HTTPException(404, "Not found")
    try:
        return refresh_channel(db, row)
    except Exception as exc:
        raise HTTPException(502, f"Refresh failed: {exc}")

@router.post("/{channel_id}/videos/{video_id}/download", response_model=VideoOut)
def download(channel_id: int, video_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    vid = db.get(YouTubeVideo, video_id)
    if not vid or vid.channel_id_fk != channel_id:
        raise HTTPException(404, "Not found")
    try:
        return download_video(db, vid)
    except Exception as exc:
        raise HTTPException(502, f"Download failed: {exc}")


@router.post("/videos/{video_id}/download", response_model=VideoOut)
def download_by_id(video_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    vid = db.get(YouTubeVideo, video_id)
    if not vid:
        raise HTTPException(404, "Not found")
    try:
        return download_video(db, vid)
    except Exception as exc:
        raise HTTPException(502, f"Download failed: {exc}")


@router.get("/stream/{video_id}")
def stream_video(video_id: int, db: Session = Depends(get_db)):
    """Serve a downloaded video file for the in-app player (already SponsorBlock-cleaned)."""
    from fastapi.responses import FileResponse
    import os
    vid = db.get(YouTubeVideo, video_id)
    if not vid or not vid.file_path or not os.path.isfile(vid.file_path):
        raise HTTPException(404, "File not available")
    return FileResponse(
        vid.file_path,
        media_type="video/mp4",
        filename=os.path.basename(vid.file_path),
        headers={"Accept-Ranges": "bytes"},
    )


class CookiesPaste(BaseModel):
    content: str
    filename: str | None = "youtube-cookies.txt"


@router.post("/cookies")
def paste_cookies(payload: CookiesPaste, _perm: list = Depends(require_permission("download", "library.manage"))):
    """One-click paste: write Netscape cookies.txt for yt-dlp auth."""
    import os
    from pathlib import Path
    from app.config import settings
    
    raw = (payload.content or "").strip()
    if not raw or "netscape" not in raw.lower() and "# HTTP" not in raw and "youtube.com" not in raw.lower():
        # still allow if it looks like cookie lines
        if not raw or len(raw) < 20:
            raise HTTPException(400, "Paste a Netscape cookies.txt export (Get cookies.txt LOCALLY extension)")
    dest = (settings.youtube_cookies_path or "").strip()
    if not dest:
        dest = "/config/youtube-cookies.txt"
    path = Path(dest)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw if raw.endswith("\n") else raw + "\n", encoding="utf-8")
    except Exception as exc:
        # fallback under data/
        path = Path("data") / "youtube-cookies.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw if raw.endswith("\n") else raw + "\n", encoding="utf-8")
        dest = str(path.resolve())
    try:
        object.__setattr__(settings, "youtube_cookies_path", dest)
    except Exception:
        settings.youtube_cookies_path = dest  # type: ignore
    return {"ok": True, "path": dest, "bytes": path.stat().st_size}


@router.get("/cookies/status")
def cookies_status():
    import os
    from app.config import settings
    path = (settings.youtube_cookies_path or "").strip() or "/config/youtube-cookies.txt"
    exists = os.path.isfile(path)
    size = os.path.getsize(path) if exists else 0
    return {
        "path": path,
        "exists": exists,
        "size": size,
        "cookies_from_browser": settings.youtube_cookies_from_browser or "",
    }
