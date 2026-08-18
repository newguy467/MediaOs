"""Built-in media player backend — direct file serve + ffmpeg transcode for full codec support.

Browsers only play a subset (H.264/AAC/VP9/AV1 in MP4/WebM). Library files are often
HEVC, AVC in MKV, AC3, DTS, TrueHD, etc. When the client requests transcode=1 (or
format is known-incompatible), we pipe ffmpeg → fragmented MP4 (H.264 + AAC) so the
HTML5 <video> element can play anything ffmpeg can decode.
"""
from __future__ import annotations

import logging
import mimetypes
import shutil
import subprocess
from pathlib import Path

from app.config import settings

log = logging.getLogger(__name__)

# Extensions we can often hand to the browser directly
_BROWSER_OK = {".mp4", ".webm", ".ogg", ".ogv", ".m4v", ".mp3", ".m4a", ".wav", ".flac", ".aac", ".opus"}
# Always prefer transcode for these containers/codecs-heavy types
_PREFER_TRANSCODE = {".mkv", ".avi", ".ts", ".m2ts", ".wmv", ".flv", ".mpg", ".mpeg", ".vob", ".mov"}


def ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def ffprobe_bin() -> str:
    return shutil.which("ffprobe") or "ffprobe"


def resolve_library_file(
    *,
    media_type: str | None = None,
    item_id: int | None = None,
    episode_id: int | None = None,
    video_id: int | None = None,
    path: str | None = None,
) -> Path:
    """Resolve a playable filesystem path from ids or an explicit path."""
    from app.database import SessionLocal
    from app.models import Episode, MediaItem, YouTubeVideo

    if path:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(path)
        _assert_under_library(p)
        return p

    db = SessionLocal()
    try:
        if video_id is not None:
            v = db.get(YouTubeVideo, video_id)
            if not v or not v.file_path:
                raise FileNotFoundError("YouTube video file not available")
            p = Path(v.file_path)
        elif episode_id is not None:
            ep = db.get(Episode, episode_id)
            if not ep or not ep.file_path:
                raise FileNotFoundError("Episode file not available")
            p = Path(ep.file_path)
        elif item_id is not None:
            item = db.get(MediaItem, item_id)
            if not item or not item.file_path:
                raise FileNotFoundError("Media file not available")
            p = Path(item.file_path)
        else:
            raise FileNotFoundError("No path or id provided")
        if not p.is_file():
            raise FileNotFoundError(str(p))
        _assert_under_library(p)
        return p
    finally:
        db.close()


def _library_roots() -> list[Path]:
    """Only media library mounts — never /config (credentials, tokens, backups)."""
    roots = []
    for attr in (
        "movies_library_path",
        "tv_library_path",
        "music_library_path",
        "books_library_path",
        "audiobooks_library_path",
        "podcasts_library_path",
        "comics_library_path",
        "manga_library_path",
        "youtube_library_path",
        "adult_library_path",
        "games_library_path",
        "downloads_path",
    ):
        v = getattr(settings, attr, None)
        if v:
            roots.append(Path(v).resolve())
    # relative data dir for logos/cache is NOT playable media
    return roots


def _assert_under_library(path: Path) -> None:
    resolved = path.resolve()
    for root in _library_roots():
        try:
            resolved.relative_to(root)
            return
        except ValueError:
            continue
    # last resort: if path exists and is under /movies etc common mounts
    for prefix in ("/movies", "/tv", "/music", "/books", "/audiobooks", "/podcasts", "/comics", "/manga", "/youtube", "/downloads", "/games", "/adult"):
        if str(resolved).startswith(prefix + "/") or str(resolved) == prefix:
            return
    raise PermissionError(f"Path outside library roots: {resolved}")


def needs_transcode(path: Path, force: bool = False) -> bool:
    if force:
        return True
    ext = path.suffix.lower()
    if ext in _PREFER_TRANSCODE:
        return True
    if ext in _BROWSER_OK:
        return False
    # unknown → transcode to be safe
    return True


def probe(path: Path) -> dict:
    """Lightweight ffprobe summary."""
    try:
        cmd = [
            ffprobe_bin(),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return {"ok": False, "error": (proc.stderr or "")[:300]}
        import json
        data = json.loads(proc.stdout or "{}")
        video = next((s for s in data.get("streams") or [] if s.get("codec_type") == "video"), None)
        audio = next((s for s in data.get("streams") or [] if s.get("codec_type") == "audio"), None)
        return {
            "ok": True,
            "format": (data.get("format") or {}).get("format_name"),
            "duration": float((data.get("format") or {}).get("duration") or 0) or None,
            "size": int((data.get("format") or {}).get("size") or 0) or None,
            "video_codec": (video or {}).get("codec_name"),
            "audio_codec": (audio or {}).get("codec_name"),
            "width": (video or {}).get("width"),
            "height": (video or {}).get("height"),
            "browser_direct": path.suffix.lower() in _BROWSER_OK and path.suffix.lower() not in _PREFER_TRANSCODE,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def build_transcode_cmd(path: Path, *, audio_only: bool = False) -> list[str]:
    """ffmpeg → fragmented MP4 over stdout (for StreamingResponse)."""
    cmd = [
        ffmpeg_bin(),
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(path),
    ]
    if audio_only:
        cmd += [
            "-vn",
            "-c:a", "aac",
            "-b:a", "192k",
            "-f", "adts",  # AAC stream
            "pipe:1",
        ]
    else:
        cmd += [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "160k",
            "-ac", "2",
            "-movflags", "frag_keyframe+empty_moov+default_base_moof",
            "-f", "mp4",
            "pipe:1",
        ]
    return cmd


def guess_media_type(path: Path) -> str:
    mt, _ = mimetypes.guess_type(str(path))
    return mt or "application/octet-stream"
