"""YouTube channel tracking — RSS refresh + yt-dlp download."""
from __future__ import annotations
import logging, os, re, shutil, subprocess
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.clients.youtube import youtube_client
from app.config import settings
from app.models import ItemStatus, YouTubeChannel, YouTubeVideo
log = logging.getLogger(__name__)

def _utcnow(): return datetime.now(timezone.utc)
def _slugify(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name or "channel", flags=re.U).strip().lower()
    return (re.sub(r"[-\s]+", "-", s)[:80]) or "channel"

def add_channel(db: Session, query: str, *, monitored: bool = True, auto_download: bool | None = None, quality: str | None = None) -> YouTubeChannel:
    data = youtube_client.resolve_channel(query)
    if not data:
        raise ValueError("Could not resolve YouTube channel or playlist")
    feed_url = data["feed_url"]
    existing = db.query(YouTubeChannel).filter(YouTubeChannel.feed_url == feed_url).first()
    if existing: return existing
    row = YouTubeChannel(
        channel_id=data.get("channel_id"), playlist_id=data.get("playlist_id"), feed_url=feed_url,
        title=data.get("title") or "YouTube", author=data.get("author"), monitored=monitored,
        auto_download=settings.youtube_auto_download_default if auto_download is None else auto_download,
        quality=quality or settings.youtube_format,
    )
    db.add(row); db.commit(); db.refresh(row)
    refresh_channel(db, row, mark_existing_as_downloaded=not settings.youtube_backlog_download)
    return row

def refresh_channel(db: Session, channel: YouTubeChannel, *, mark_existing_as_downloaded: bool = False) -> dict:
    if channel.channel_id:
        data = youtube_client.fetch_channel_feed(channel.channel_id)
    elif channel.playlist_id:
        data = youtube_client.fetch_playlist_feed(channel.playlist_id)
    else:
        data = youtube_client._parse_feed(channel.feed_url)
    channel.title = data.get("title") or channel.title
    channel.author = data.get("author") or channel.author
    channel.last_checked_at = _utcnow()
    existing = {v.video_id for v in channel.videos}
    new_count = 0
    for v in data.get("videos") or []:
        if v["video_id"] in existing: continue
        db.add(YouTubeVideo(
            channel_id_fk=channel.id, video_id=v["video_id"], title=v["title"], url=v["url"],
            published_at=v.get("published_at"), thumbnail=v.get("thumbnail"), description=v.get("description"),
            status=ItemStatus.downloaded if mark_existing_as_downloaded else ItemStatus.wanted,
        ))
        new_count += 1
    channel.video_count = len(data.get("videos") or [])
    db.add(channel); db.commit()
    return {"new_videos": new_count, "total_in_feed": channel.video_count}

def _within_window(channel, published_at):
    if not channel.download_window_days or not published_at: return True
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    except Exception: return True
    return dt >= _utcnow() - timedelta(days=channel.download_window_days)

def download_video(db: Session, video: YouTubeVideo) -> YouTubeVideo:
    channel = video.channel
    show_dir = os.path.join(settings.youtube_library_path, _slugify(channel.title))
    os.makedirs(show_dir, exist_ok=True)
    ytdlp = settings.youtube_ytdlp_path or "yt-dlp"
    if not shutil.which(ytdlp) and ytdlp == "yt-dlp":
        raise RuntimeError("yt-dlp not found on PATH")
    fmt = channel.quality or settings.youtube_format or "best[height<=1080]"
    outtmpl = os.path.join(show_dir, "%(upload_date)s - %(title).200B [%(id)s].%(ext)s")
    cmd = [
        ytdlp, "-f", fmt, "--no-playlist",
        "-o", outtmpl,
        "--write-info-json", "--write-thumbnail",
        "--merge-output-format", "mp4",
        "--no-warnings",
    ]
    # Cookies / login support (age-restricted, members-only)
    cookies_path = (settings.youtube_cookies_path or "").strip()
    cookies_browser = (settings.youtube_cookies_from_browser or "").strip()
    if cookies_path and os.path.isfile(cookies_path):
        cmd.extend(["--cookies", cookies_path])
    elif cookies_browser:
        cmd.extend(["--cookies-from-browser", cookies_browser])
    # SponsorBlock + ad-like segment removal (native yt-dlp)
    sb_remove = (settings.youtube_sponsorblock_remove or "").strip()
    sb_mark = (settings.youtube_sponsorblock_mark or "").strip()
    if sb_remove:
        cmd.extend(["--sponsorblock-remove", sb_remove])
    if sb_mark:
        cmd.extend(["--sponsorblock-mark", sb_mark])
    cmd.append(video.url)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "")[-500:] or f"yt-dlp exit {proc.returncode}")
    dest = None
    for name in os.listdir(show_dir):
        if video.video_id in name and not name.endswith((".json", ".webp", ".jpg", ".png")):
            dest = os.path.join(show_dir, name)
            break
    video.file_path = dest
    video.status = ItemStatus.downloaded
    video.downloaded_at = _utcnow()
    db.add(video)
    db.commit()
    db.refresh(video)
    return video

def check_and_download_all(db: Session, *, limit_per_channel: int = 5) -> dict:
    channels = db.query(YouTubeChannel).filter(YouTubeChannel.monitored.is_(True)).all()
    summary = {"checked": 0, "downloaded": 0, "errors": []}
    for ch in channels:
        try:
            refresh_channel(db, ch)
            summary["checked"] += 1
            if not ch.auto_download: continue
            wanted = (db.query(YouTubeVideo).filter(YouTubeVideo.channel_id_fk == ch.id, YouTubeVideo.status == ItemStatus.wanted)
                      .order_by(YouTubeVideo.added_at.desc()).limit(limit_per_channel).all())
            for v in wanted:
                if not _within_window(ch, v.published_at): continue
                try:
                    download_video(db, v); summary["downloaded"] += 1
                except Exception as exc:
                    summary["errors"].append(f"{ch.title}/{v.title}: {exc}")
        except Exception as exc:
            summary["errors"].append(f"{ch.title}: {exc}")
    return summary
