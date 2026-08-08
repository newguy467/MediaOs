"""Built-in media player API — probe, direct stream, ffmpeg transcode."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.auth import require_permission
from fastapi import Depends, APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.services.media_player import (
    build_transcode_cmd,
    guess_media_type,
    needs_transcode,
    probe,
    resolve_library_file,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/player", tags=["player"], dependencies=[Depends(require_permission("player.view", "library.view"))])


def _resolve(
    item_id: int | None,
    episode_id: int | None,
    video_id: int | None,
    path: str | None,
) -> Path:
    try:
        return resolve_library_file(
            item_id=item_id, episode_id=episode_id, video_id=video_id, path=path
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.get("/probe")
def player_probe(
    item_id: int | None = None,
    episode_id: int | None = None,
    video_id: int | None = None,
    path: str | None = None,
    podcast_episode_id: int | None = None,
):
    p = _resolve(item_id, episode_id, video_id, path)
    info = probe(p)
    info["path"] = str(p)
    info["name"] = p.name
    info["needs_transcode"] = needs_transcode(p)
    info["chapters"] = []
    # Podcast chapter markers (skip intro/ads)
    if podcast_episode_id:
        try:
            import json
            from app.database import SessionLocal
            from app.models import PodcastEpisode
            db = SessionLocal()
            try:
                ep = db.get(PodcastEpisode, podcast_episode_id)
                if ep and ep.chapters_json:
                    ch = json.loads(ep.chapters_json)
                    if isinstance(ch, list):
                        info["chapters"] = ch
            finally:
                db.close()
        except Exception:
            pass
    return info


@router.get("/stream")
def player_stream(
    request: Request,
    item_id: int | None = None,
    episode_id: int | None = None,
    video_id: int | None = None,
    path: str | None = None,
    transcode: int = Query(0, description="1 = force ffmpeg H.264/AAC fMP4"),
    audio: int = Query(0, description="1 = audio-only AAC"),
):
    """
    Stream a library file.
    - Direct FileResponse (with Range) when browser-friendly
    - ffmpeg pipe when transcode=1 or container needs it
    """
    p = _resolve(item_id, episode_id, video_id, path)
    force = bool(transcode) or bool(audio)
    if not force and not needs_transcode(p):
        return FileResponse(
            p,
            media_type=guess_media_type(p),
            filename=p.name,
            headers={"Accept-Ranges": "bytes", "Cache-Control": "no-cache"},
        )

    # Transcode path
    cmd = build_transcode_cmd(p, audio_only=bool(audio))
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1024 * 64,
        )
    except FileNotFoundError:
        raise HTTPException(500, "ffmpeg not found — install ffmpeg in the image")

    media = "audio/aac" if audio else "video/mp4"

    def gen():
        try:
            assert proc.stdout is not None
            while True:
                chunk = proc.stdout.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

    return StreamingResponse(
        gen(),
        media_type=media,
        headers={
            "Cache-Control": "no-cache",
            "X-Transcode": "ffmpeg",
            "Content-Disposition": f'inline; filename="{p.stem}.{"aac" if audio else "mp4"}"',
        },
    )


@router.get("/status")
def player_status():
    import shutil
    return {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "direct_ext": sorted([".mp4", ".webm", ".ogg", ".m4v", ".mp3", ".m4a", ".wav", ".flac", ".aac", ".opus"]),
        "transcode_ext": sorted([".mkv", ".avi", ".ts", ".m2ts", ".wmv", ".flv", ".mpg", ".mpeg", ".mov"]),
        "note": "Unsupported codecs are transcoded on the fly to H.264/AAC fMP4 via ffmpeg",
    }
