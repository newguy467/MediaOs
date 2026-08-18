"""Runs one ffmpeg process per enabled virtual channel, reading its concat
playlist (see virtual_channels.write_concat_playlist) and writing a live HLS
feed to disk. Jellyfin's M3U/HLS tuner just requests the .m3u8 URL like any
other live channel — it doesn't know or care the source is a personal library.

Because the concat demuxer reads its file list once at start, "new" schedule
content only becomes visible to ffmpeg on (re)start. We handle that by
restarting each channel's process periodically (virtualtv_stream_restart_hours,
default 4h) using a freshly-written playlist — same trick tools like this
commonly use. Expect a ~1-2s reconnect blip at each rotation; there is no
frame-accurate gapless handoff in this version.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger("mediaos.virtualtv.stream")

# In-process registry: channel_id -> Popen. Not persisted — on app restart all
# channels are considered stopped and get relaunched by the scheduler tick.
_procs: dict[int, subprocess.Popen] = {}
_lock = threading.Lock()


def ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_running(channel_id: int) -> bool:
    with _lock:
        proc = _procs.get(channel_id)
        return bool(proc and proc.poll() is None)


def stop(channel_id: int) -> None:
    with _lock:
        proc = _procs.pop(channel_id, None)
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception as exc:
            log.warning("failed to stop virtual channel %s ffmpeg: %s", channel_id, exc)


def _read_seek_offset(out_dir: Path) -> float:
    try:
        return float((out_dir / "seek_offset.txt").read_text(encoding="utf-8").strip())
    except Exception:
        return 0.0


def start(channel) -> dict:
    """(Re)start the HLS feed for a channel from its current concat playlist."""
    from app.config import settings
    from app.services.virtual_channels import channel_data_dir

    out_dir = channel_data_dir(channel.id)
    playlist_path = out_dir / "playlist.txt"
    if not playlist_path.exists() or not playlist_path.read_text(encoding="utf-8").strip():
        return {"ok": False, "error": "no schedule/playlist yet"}

    stop(channel.id)  # ensure no stale process before relaunching

    # Clear old segments so stale/mismatched .ts files aren't served after a restart.
    for f in out_dir.glob("seg_*.ts"):
        try:
            f.unlink()
        except OSError:
            pass

    seek = _read_seek_offset(out_dir)
    seg_seconds = int(getattr(settings, "virtualtv_hls_segment_seconds", 6) or 6)
    list_size = int(getattr(settings, "virtualtv_hls_playlist_size", 10) or 10)

    cmd = [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error",
        "-re",
        "-f", "concat", "-safe", "0",
    ]
    if seek > 0:
        cmd += ["-ss", f"{seek:.2f}"]
    cmd += [
        "-i", str(playlist_path),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ac", "2",
        "-f", "hls",
        "-hls_time", str(seg_seconds),
        "-hls_list_size", str(list_size),
        "-hls_flags", "delete_segments+append_list+omit_endlist",
        "-hls_segment_filename", str(out_dir / "seg_%05d.ts"),
        str(out_dir / "stream.m3u8"),
    ]

    try:
        log_file = open(out_dir / "ffmpeg.log", "ab")
        proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)
    except FileNotFoundError:
        return {"ok": False, "error": "ffmpeg not installed in container"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}

    with _lock:
        _procs[channel.id] = proc
    return {"ok": True, "pid": proc.pid, "seek_offset": seek}


def ensure_running(db, channel) -> dict:
    """Idempotent: start if not running, restart if it's died, restart on the
    periodic schedule so newly-generated content gets picked up."""
    from app.config import settings

    restart_hours = float(getattr(settings, "virtualtv_stream_restart_hours", 4.0) or 4.0)
    running = is_running(channel.id)
    started = channel.stream_started_at
    if started and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    stale = bool(started) and _now() - started > timedelta(hours=restart_hours)

    if running and not stale:
        return {"ok": True, "status": "running", "restarted": False}

    result = start(channel)
    channel.stream_status = "running" if result.get("ok") else "error"
    channel.stream_error = None if result.get("ok") else result.get("error")
    channel.stream_started_at = _now()
    channel.stream_pid = result.get("pid")
    db.add(channel)
    db.commit()
    result["restarted"] = True
    return result


def stop_and_mark(db, channel) -> None:
    stop(channel.id)
    channel.stream_status = "stopped"
    channel.stream_pid = None
    db.add(channel)
    db.commit()


def hls_playlist_path(channel_id: int) -> Path:
    from app.services.virtual_channels import channel_data_dir
    return channel_data_dir(channel_id) / "stream.m3u8"


def hls_segment_path(channel_id: int, segment_name: str) -> Path:
    from app.services.virtual_channels import channel_data_dir
    # segment_name comes from the URL path — keep it to the expected pattern
    # to avoid any path traversal via crafted segment filenames.
    import re
    if not re.fullmatch(r"seg_\d{5}\.ts", segment_name):
        raise ValueError("invalid segment name")
    return channel_data_dir(channel_id) / segment_name
