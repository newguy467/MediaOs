"""Personal media → 24/7 virtual TV channels.

This is the "your Jellyfin library becomes a channel" engine: given a
LiveTvVirtualChannel definition (content filters + scheduling rules), it
builds and continuously tops up a LiveTvVirtualScheduleItem timeline, and
writes an ffmpeg concat playlist that the stream engine (see
virtual_stream_engine.py) turns into a real HLS live feed.

Design notes / known limits (v1):
  - Duration comes from ffprobe (media_player.probe) and is cached on the
    generated schedule row so a file is only probed once.
  - "Genre" filtering is a plain substring match against MediaItem.overview
    (MediaOS doesn't store structured genre tags today) — good enough for
    "sci-fi", "christmas", etc. but not a real taxonomy yet.
  - No bumpers/trailers/commercials/dayparting injection yet — pure
    back-to-back scheduling. Tracked as a follow-up.
"""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

log = logging.getLogger("mediaos.virtualtv")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def channel_data_dir(channel_id: int) -> Path:
    from app.config import settings
    p = Path(getattr(settings, "virtualtv_data_path", "data/livetv/virtual")) / str(channel_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _probe_duration(file_path: str) -> float | None:
    from app.services.media_player import probe
    try:
        info = probe(Path(file_path))
        if info.get("ok") and info.get("duration"):
            return float(info["duration"])
    except Exception as exc:
        log.debug("probe failed for %s: %s", file_path, exc)
    return None


def _fallback_duration(media_type: str) -> float:
    # Used only if ffprobe fails outright (missing/corrupt file, no ffmpeg) so
    # scheduling can still make forward progress instead of stalling.
    return 5400.0 if media_type == "movie" else 1320.0  # 90 min movie / 22 min episode


def eligible_pool(db: Session, channel) -> list[dict]:
    """Return candidate {kind, media_item_id, episode_id, title, file_path, media_type} rows."""
    from app.models import MediaItem, Episode, MediaType

    types = json.loads(channel.media_types or "[]") or ["movie"]
    explicit_ids = json.loads(channel.media_item_ids) if channel.media_item_ids else None
    genre_terms = [g.strip().lower() for g in (channel.genre_filter or "").split(",") if g.strip()]
    title_term = (channel.title_filter or "").strip().lower()

    pool: list[dict] = []

    if "movie" in types:
        q = db.query(MediaItem).filter(
            MediaItem.media_type == MediaType.movie,
            MediaItem.file_path.isnot(None),
        )
        if explicit_ids:
            q = q.filter(MediaItem.id.in_(explicit_ids))
        for item in q.all():
            if not item.file_path or not Path(item.file_path).is_file():
                continue
            if channel.year_min and (item.year or 0) < channel.year_min:
                continue
            if channel.year_max and (item.year or 9999) > channel.year_max:
                continue
            if title_term and title_term not in (item.title or "").lower():
                continue
            if genre_terms:
                hay = f"{item.overview or ''} {item.title or ''}".lower()
                if not any(g in hay for g in genre_terms):
                    continue
            pool.append({
                "kind": "movie",
                "media_item_id": item.id,
                "episode_id": None,
                "title": item.title,
                "file_path": item.file_path,
                "media_type": "movie",
            })

    if "tv" in types:
        q = db.query(Episode).join(MediaItem, Episode.media_item_id == MediaItem.id).filter(
            Episode.file_path.isnot(None),
        )
        if explicit_ids:
            q = q.filter(MediaItem.id.in_(explicit_ids))
        for ep in q.all():
            if not ep.file_path or not Path(ep.file_path).is_file():
                continue
            series = ep.series
            if not series:
                continue
            if title_term and title_term not in (series.title or "").lower():
                continue
            if genre_terms:
                hay = f"{series.overview or ''} {series.title or ''}".lower()
                if not any(g in hay for g in genre_terms):
                    continue
            label = f"{series.title} S{ep.season_number:02d}E{ep.episode_number:02d}"
            if ep.title:
                label += f" - {ep.title}"
            pool.append({
                "kind": "episode",
                "media_item_id": series.id,
                "episode_id": ep.id,
                "title": label,
                "file_path": ep.file_path,
                "media_type": "tv",
                "_series_id": series.id,
                "_season": ep.season_number,
                "_episode": ep.episode_number,
            })
        # Keep series in air order by default so "continuous episodes" feels right
        # even when randomize is off; randomize (below) shuffles at the series level.
        pool.sort(key=lambda r: (r.get("_series_id", 0), r.get("_season", 0), r.get("_episode", 0)))

    return pool


def _recently_played_keys(db: Session, channel_id: int, since: datetime) -> set[tuple]:
    from app.models import LiveTvVirtualScheduleItem as SI
    rows = (
        db.query(SI)
        .filter(SI.virtual_channel_id == channel_id, SI.start_time >= since)
        .all()
    )
    keys = set()
    for r in rows:
        keys.add((r.media_item_id, r.episode_id))
    return keys


def extend_schedule(db: Session, channel, horizon_hours: int | None = None) -> dict:
    """Top the channel's schedule up to `horizon_hours` from now. Idempotent —
    safe to call repeatedly (e.g. every 15 min from the scheduler)."""
    from app.config import settings
    from app.models import LiveTvVirtualScheduleItem as SI

    horizon_hours = horizon_hours or int(getattr(settings, "virtualtv_schedule_horizon_hours", 12) or 12)
    now = _now()
    horizon = now + timedelta(hours=horizon_hours)

    last = (
        db.query(SI)
        .filter(SI.virtual_channel_id == channel.id)
        .order_by(SI.start_time.desc())
        .first()
    )
    cursor = _aware(last.start_time) + timedelta(seconds=last.duration_seconds) if last else now
    if cursor < now:
        # Big gap (channel was off / server was down) — resume from now rather
        # than trying to "catch up" a dead air gap.
        cursor = now

    pool = eligible_pool(db, channel)
    if not pool:
        return {"added": 0, "reason": "no eligible content", "filled_until": cursor.isoformat()}

    protect_days = int(channel.repeat_protection_days or 0)
    recent_keys = _recently_played_keys(db, channel.id, now - timedelta(days=max(protect_days, 1))) if protect_days else set()

    order = list(pool)
    if channel.randomize:
        random.shuffle(order)

    added = 0
    guard = 0
    idx = 0
    n = len(order)
    while cursor < horizon and guard < 5000:
        guard += 1
        if n == 0:
            break
        candidate = order[idx % n]
        idx += 1
        key = (candidate["media_item_id"], candidate["episode_id"])
        if protect_days and key in recent_keys and n > 1:
            continue  # try next candidate on the following loop iteration
        duration = _probe_duration(candidate["file_path"]) or _fallback_duration(candidate["media_type"])
        row = SI(
            virtual_channel_id=channel.id,
            media_item_id=candidate["media_item_id"],
            episode_id=candidate["episode_id"],
            title=candidate["title"],
            file_path=candidate["file_path"],
            start_time=cursor,
            duration_seconds=duration,
        )
        db.add(row)
        recent_keys.add(key)
        cursor += timedelta(seconds=duration)
        added += 1
        if idx % n == 0 and channel.randomize:
            random.shuffle(order)

    channel.schedule_filled_until = cursor
    db.add(channel)
    db.commit()

    if added:
        write_concat_playlist(db, channel)

    return {"added": added, "filled_until": cursor.isoformat()}


def prune_old_schedule(db: Session, channel_id: int, keep_hours: int = 24) -> int:
    """Drop schedule rows that finished more than `keep_hours` ago (keeps the table small)."""
    from app.models import LiveTvVirtualScheduleItem as SI
    cutoff = _now() - timedelta(hours=keep_hours)
    q = db.query(SI).filter(SI.virtual_channel_id == channel_id, SI.start_time < cutoff)
    n = q.delete(synchronize_session=False)
    db.commit()
    return n


def get_now_and_next(db: Session, channel_id: int) -> dict:
    from app.models import LiveTvVirtualScheduleItem as SI
    now = _now()
    current = (
        db.query(SI)
        .filter(SI.virtual_channel_id == channel_id, SI.start_time <= now)
        .order_by(SI.start_time.desc())
        .first()
    )
    result = {"now": None, "next": None, "offset_seconds": None}
    if current:
        start = _aware(current.start_time)
        end = start + timedelta(seconds=current.duration_seconds)
        if now < end:
            result["now"] = {
                "title": current.title,
                "start": start.isoformat(),
                "stop": end.isoformat(),
                "file_path": current.file_path,
            }
            result["offset_seconds"] = max(0.0, (now - start).total_seconds())
        nxt = (
            db.query(SI)
            .filter(SI.virtual_channel_id == channel_id, SI.start_time >= end)
            .order_by(SI.start_time.asc())
            .first()
        )
        if nxt:
            nstart = _aware(nxt.start_time)
            result["next"] = {
                "title": nxt.title,
                "start": nstart.isoformat(),
                "stop": (nstart + timedelta(seconds=nxt.duration_seconds)).isoformat(),
            }
    return result


def write_concat_playlist(db: Session, channel) -> Path:
    """Write an ffmpeg concat-demuxer file covering [now .. schedule_filled_until].

    The stream engine seeks into the first entry with -ss so playback joins
    mid-program at the correct live position, then plays straight through.
    """
    from app.models import LiveTvVirtualScheduleItem as SI

    now = _now()
    rows = (
        db.query(SI)
        .filter(
            SI.virtual_channel_id == channel.id,
            SI.start_time >= now - timedelta(hours=6),
        )
        .order_by(SI.start_time.asc())
        .all()
    )
    # Keep only rows that are current or upcoming (the query above is a coarse
    # pre-filter; refine precisely here since SQLite can't do the interval math).
    rows = [r for r in rows if _aware(r.start_time) + timedelta(seconds=r.duration_seconds) > now]

    out_dir = channel_data_dir(channel.id)
    playlist_path = out_dir / "playlist.txt"
    offset_path = out_dir / "seek_offset.txt"

    lines = []
    seek_offset = 0.0
    for i, r in enumerate(rows):
        p = str(Path(r.file_path).resolve()).replace("'", "'\\''")
        lines.append(f"file '{p}'")
        if i == 0:
            start = _aware(r.start_time)
            seek_offset = max(0.0, (now - start).total_seconds())

    playlist_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    offset_path.write_text(f"{seek_offset:.2f}\n", encoding="utf-8")
    return playlist_path


def ensure_channel_ready(db: Session, channel) -> dict:
    """Make sure a channel has schedule + an up-to-date concat playlist. Called
    before (re)starting its stream and periodically from the scheduler."""
    from app.config import settings
    horizon = int(getattr(settings, "virtualtv_schedule_horizon_hours", 12) or 12)
    filled_until = _aware(channel.schedule_filled_until)
    if not filled_until or filled_until < _now() + timedelta(hours=1):
        result = extend_schedule(db, channel, horizon_hours=horizon)
    else:
        write_concat_playlist(db, channel)
        result = {"added": 0, "filled_until": filled_until.isoformat()}
    prune_old_schedule(db, channel.id)
    return result


def regenerate_all(db: Session) -> dict:
    from app.models import LiveTvVirtualChannel as VC
    channels = db.query(VC).filter(VC.enabled.is_(True)).all()
    summary = {}
    for ch in channels:
        try:
            summary[ch.id] = ensure_channel_ready(db, ch)
        except Exception as exc:
            log.exception("virtual channel %s schedule extend failed: %s", ch.id, exc)
            summary[ch.id] = {"error": str(exc)}
    return summary
