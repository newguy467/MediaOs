"""Live TV DVR — schedule recordings from EPG (Cinephage click-to-record)."""
from __future__ import annotations

import logging
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import LiveTvChannel, LiveTvRecording

log = logging.getLogger("mediaos.livetv_dvr")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _recordings_dir() -> Path:
    base = Path(getattr(settings, "downloads_path", "/downloads") or "/downloads") / "livetv-recordings"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _has_channel_conflict(
    db: Session,
    channel_id: int | None,
    starts_at: datetime | None,
    ends_at: datetime | None,
    exclude_id: int | None = None,
) -> list[dict]:
    """Return overlapping scheduled/recording jobs on the same channel (simple guide conflict)."""
    if not channel_id or not starts_at:
        return []
    q = (
        db.query(LiveTvRecording)
        .filter(
            LiveTvRecording.channel_id == channel_id,
            LiveTvRecording.status.in_(["scheduled", "recording"]),
        )
    )
    if exclude_id:
        q = q.filter(LiveTvRecording.id != exclude_id)
    conflicts = []
    for other in q.all():
        o_start = other.starts_at
        o_end = other.ends_at
        if not o_start:
            continue
        if ends_at and o_end:
            if starts_at < o_end and ends_at > o_start:
                conflicts.append({"id": other.id, "title": other.title, "starts_at": o_start.isoformat() if o_start else None})
        elif ends_at and o_start < ends_at and (not o_end or o_end > starts_at):
            conflicts.append({"id": other.id, "title": other.title, "starts_at": o_start.isoformat() if o_start else None})
        elif o_end and starts_at < o_end:
            conflicts.append({"id": other.id, "title": other.title, "starts_at": o_start.isoformat() if o_start else None})
    return conflicts


def schedule_recording(
    db: Session,
    *,
    channel_id: int | None,
    title: str,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    subtitle: str | None = None,
    tvg_id: str | None = None,
    stream_url: str | None = None,
    allow_conflict: bool = False,
) -> LiveTvRecording:
    ch = db.get(LiveTvChannel, channel_id) if channel_id else None
    url = stream_url or (ch.stream_url if ch else None)
    conflicts = _has_channel_conflict(db, channel_id, starts_at, ends_at)
    if conflicts and not allow_conflict:
        raise RuntimeError(
            f"Guide conflict on channel: {len(conflicts)} overlapping recording(s) — "
            f"e.g. '{conflicts[0].get('title')}' (id={conflicts[0].get('id')}). "
            "Pass allow_conflict=True to force."
        )
    # Multi-tuner / concurrent limit
    concurrent = _count_overlapping(db, starts_at, ends_at)
    limit = max_concurrent_recordings()
    if concurrent >= limit and not allow_conflict:
        raise RuntimeError(
            f"Multi-tuner limit reached: {concurrent} overlapping recording(s) "
            f"(max={limit}). Raise livetv_max_concurrent or pass allow_conflict=True."
        )
    rec = LiveTvRecording(
        channel_id=channel_id,
        channel_name=ch.name if ch else None,
        title=title or "Recording",
        subtitle=subtitle,
        tvg_id=tvg_id or (getattr(ch, "epg_tvg_id", None) or getattr(ch, "tvg_id", None) if ch else None),
        starts_at=starts_at,
        ends_at=ends_at,
        status="scheduled",
        stream_url=url,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # If already on-air (start in past / now), start immediately
    now = _utcnow()
    start = starts_at or now
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if start <= now + __import__("datetime").timedelta(seconds=30):
        threading.Thread(target=_run_recording, args=(rec.id,), daemon=True, name=f"dvr-{rec.id}").start()
    else:
        delay = (start - now).total_seconds()
        threading.Timer(max(1.0, delay), lambda: _run_recording(rec.id)).start()
    return rec


def _run_recording(rec_id: int) -> None:
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        rec = db.get(LiveTvRecording, rec_id)
        if not rec or rec.status in ("cancelled", "completed"):
            return
        url = rec.stream_url
        if not url and rec.channel_id:
            ch = db.get(LiveTvChannel, rec.channel_id)
            url = ch.stream_url if ch else None
        if not url:
            rec.status = "failed"
            rec.error = "No stream URL"
            db.commit()
            return
        rec.status = "recording"
        db.commit()

        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in (rec.title or "rec"))[:80].strip() or "rec"
        stamp = _utcnow().strftime("%Y%m%dT%H%M%S")
        out = _recordings_dir() / f"{safe}_{stamp}.ts"
        duration = 3600
        if rec.starts_at and rec.ends_at:
            try:
                duration = max(60, int((rec.ends_at - rec.starts_at).total_seconds()))
            except Exception:
                pass
        # Prefer ffmpeg; fallback message
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", url, "-t", str(duration), "-c", "copy", str(out),
        ]
        try:
            proc = subprocess.run(cmd, timeout=duration + 120, capture_output=True)
            if proc.returncode == 0 and out.exists():
                rec.status = "completed"
                rec.file_path = str(out)
                rec.error = None
            else:
                rec.status = "failed"
                rec.error = (proc.stderr or b"")[-500:].decode("utf-8", errors="ignore") or f"exit {proc.returncode}"
        except FileNotFoundError:
            rec.status = "failed"
            rec.error = "ffmpeg not installed in container"
        except Exception as e:
            rec.status = "failed"
            rec.error = str(e)
        db.commit()
    finally:
        db.close()


def list_recordings(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.query(LiveTvRecording).order_by(LiveTvRecording.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "channel_id": r.channel_id,
            "channel_name": r.channel_name,
            "title": r.title,
            "subtitle": r.subtitle,
            "starts_at": r.starts_at.isoformat() if r.starts_at else None,
            "ends_at": r.ends_at.isoformat() if r.ends_at else None,
            "status": r.status,
            "file_path": r.file_path,
            "error": r.error,
        }
        for r in rows
    ]


def cancel_recording(db: Session, rec_id: int) -> bool:
    rec = db.get(LiveTvRecording, rec_id)
    if not rec:
        return False
    if rec.status == "scheduled":
        rec.status = "cancelled"
        db.commit()
        return True
    return False


def max_concurrent_recordings() -> int:
    """Tunable multi-tuner limit (default 2)."""
    try:
        return max(1, int(getattr(settings, "livetv_max_concurrent", 2) or 2))
    except Exception:
        return 2


def _count_overlapping(
    db: Session,
    starts_at: datetime | None,
    ends_at: datetime | None,
) -> int:
    if not starts_at:
        return 0
    q = db.query(LiveTvRecording).filter(LiveTvRecording.status.in_(["scheduled", "recording"]))
    n = 0
    for other in q.all():
        o_start = other.starts_at
        o_end = other.ends_at
        if not o_start:
            continue
        if ends_at and o_end:
            if starts_at < o_end and ends_at > o_start:
                n += 1
        elif ends_at and o_start < ends_at:
            n += 1
        elif o_end and starts_at < o_end:
            n += 1
        elif not ends_at and not o_end:
            n += 1
    return n


# --- Series-record rules ---

def list_series_rules(db: Session) -> list[dict[str, Any]]:
    from app.models import LiveTvSeriesRule
    rows = db.query(LiveTvSeriesRule).order_by(LiveTvSeriesRule.priority.desc(), LiveTvSeriesRule.id).all()
    return [
        {
            "id": r.id,
            "title_match": r.title_match,
            "match_mode": r.match_mode,
            "channel_id": r.channel_id,
            "enabled": r.enabled,
            "keep_episodes": r.keep_episodes,
            "priority": r.priority,
            "only_new": r.only_new,
        }
        for r in rows
    ]


def create_series_rule(
    db: Session,
    *,
    title_match: str,
    match_mode: str = "contains",
    channel_id: int | None = None,
    keep_episodes: int = 0,
    priority: int = 50,
    only_new: bool = True,
    enabled: bool = True,
) -> dict[str, Any]:
    from app.models import LiveTvSeriesRule
    rule = LiveTvSeriesRule(
        title_match=title_match.strip(),
        match_mode=match_mode or "contains",
        channel_id=channel_id,
        keep_episodes=keep_episodes or 0,
        priority=priority or 50,
        only_new=bool(only_new),
        enabled=bool(enabled),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "title_match": rule.title_match, "enabled": rule.enabled}


def delete_series_rule(db: Session, rule_id: int) -> bool:
    from app.models import LiveTvSeriesRule
    rule = db.get(LiveTvSeriesRule, rule_id)
    if not rule:
        return False
    db.delete(rule)
    db.commit()
    return True


def _title_matches(rule_title: str, mode: str, epg_title: str) -> bool:
    a = (rule_title or "").strip().lower()
    b = (epg_title or "").strip().lower()
    if not a or not b:
        return False
    if mode == "exact":
        return a == b
    if mode == "startswith":
        return b.startswith(a)
    return a in b  # contains


def apply_series_rules_to_epg(
    db: Session,
    epg_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Given EPG programme dicts, schedule matching series rules.

    Each item: {title, channel_id, starts_at, ends_at, subtitle?, stream_url?, tvg_id?}
    Returns list of scheduled recording summaries.
    """
    from app.models import LiveTvSeriesRule
    rules = (
        db.query(LiveTvSeriesRule)
        .filter(LiveTvSeriesRule.enabled == True)  # noqa: E712
        .order_by(LiveTvSeriesRule.priority.desc())
        .all()
    )
    scheduled = []
    for item in epg_items or []:
        title = item.get("title") or ""
        ch_id = item.get("channel_id")
        for rule in rules:
            if rule.channel_id and ch_id and int(rule.channel_id) != int(ch_id):
                continue
            if not _title_matches(rule.title_match, rule.match_mode or "contains", title):
                continue
            # keep_episodes pruning is best-effort (completed count)
            if rule.keep_episodes and rule.keep_episodes > 0:
                done = (
                    db.query(LiveTvRecording)
                    .filter(
                        LiveTvRecording.series_rule_id == rule.id,
                        LiveTvRecording.status == "completed",
                    )
                    .count()
                )
                if done >= rule.keep_episodes:
                    continue
            try:
                starts = item.get("starts_at")
                ends = item.get("ends_at")
                if isinstance(starts, str):
                    starts = datetime.fromisoformat(starts.replace("Z", "+00:00"))
                if isinstance(ends, str):
                    ends = datetime.fromisoformat(ends.replace("Z", "+00:00"))
                rec = schedule_recording(
                    db,
                    channel_id=ch_id,
                    title=title,
                    starts_at=starts,
                    ends_at=ends,
                    subtitle=item.get("subtitle"),
                    tvg_id=item.get("tvg_id"),
                    stream_url=item.get("stream_url"),
                    allow_conflict=False,
                )
                try:
                    rec.series_rule_id = rule.id
                    db.add(rec)
                    db.commit()
                except Exception:
                    pass
                scheduled.append({"recording_id": rec.id, "title": title, "rule_id": rule.id})
            except Exception as e:
                log.debug("series-rule schedule skip %s: %s", title, e)
            break  # first matching rule wins
    return scheduled
