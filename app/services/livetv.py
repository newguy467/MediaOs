"""Live TV: M3U playlist parse + Xtream Codes live stream list."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from sqlalchemy.orm import Session

from app.clients.cf_bypass import cf_bypass_client
from app.clients.flaresolverr import flaresolverr_client
from app.models import LiveTvChannel, LiveTvSource

log = logging.getLogger(__name__)

_EXTINF = re.compile(
    r'#EXTINF:(-?\d+)\s*(.*?)\s*,\s*(.*)$',
    re.MULTILINE,
)
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def _fetch_text(url: str) -> str:
    """Fetch playlist: direct → built-in CF bypass → FlareSolverr."""
    try:
        r = httpx.get(url, timeout=60.0, follow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as exc:
        log.info("Direct M3U fetch failed (%s); trying built-in CF bypass", exc)
        try:
            return cf_bypass_client.get_text(url)
        except Exception as exc2:
            log.info("CF bypass failed (%s); FlareSolverr if enabled", exc2)
            if getattr(flaresolverr_client, "enabled", False):
                return flaresolverr_client.get_text(url)
            raise


def parse_m3u(text: str, base_url: str | None = None) -> list[dict]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    channels: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF:"):
            m = _EXTINF.match(line)
            attrs_raw = m.group(2) if m else ""
            name = (m.group(3) if m else line).strip()
            attrs = dict(_ATTR.findall(attrs_raw))
            url = ""
            if i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                url = lines[i + 1].strip()
                i += 1
            if url and base_url and not url.startswith(("http://", "https://", "rtmp")):
                url = urljoin(base_url, url)
            if url:
                channels.append(
                    {
                        "name": name or attrs.get("tvg-name") or "Unknown",
                        "group_title": attrs.get("group-title") or attrs.get("group") or None,
                        "logo": attrs.get("tvg-logo") or attrs.get("logo") or None,
                        "tvg_id": attrs.get("tvg-id") or None,
                        "stream_url": url,
                    }
                )
        i += 1
    return channels


def sync_m3u_source(db: Session, source: LiveTvSource) -> int:
    if not source.url:
        raise ValueError("M3U source missing url")
    text = _fetch_text(source.url)
    parsed = parse_m3u(text, base_url=source.url)
    # replace channels for this source
    db.query(LiveTvChannel).filter(LiveTvChannel.source_id == source.id).delete()
    for ch in parsed:
        db.add(
            LiveTvChannel(
                source_id=source.id,
                name=ch["name"][:500],
                group_title=(ch["group_title"] or "")[:300] or None,
                logo=ch.get("logo"),
                stream_url=ch["stream_url"],
                tvg_id=ch.get("tvg_id"),
                enabled=True,
            )
        )
    source.channel_count = len(parsed)
    source.last_sync_at = datetime.now(timezone.utc)
    db.add(source)
    db.commit()
    return len(parsed)


def sync_xtream_source(db: Session, source: LiveTvSource) -> int:
    host = (source.xtream_host or "").rstrip("/")
    user = source.xtream_username or ""
    pw = source.xtream_password or ""
    if not host or not user:
        raise ValueError("Xtream source missing host/username")
    # player_api live streams
    api = f"{host}/player_api.php"
    r = httpx.get(
        api,
        params={"username": user, "password": pw, "action": "get_live_streams"},
        timeout=60.0,
        follow_redirects=True,
    )
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("Unexpected Xtream response")

    # categories map optional
    cats: dict[str, str] = {}
    try:
        cr = httpx.get(
            api,
            params={"username": user, "password": pw, "action": "get_live_categories"},
            timeout=30.0,
        )
        if cr.status_code == 200:
            for c in cr.json() or []:
                cats[str(c.get("category_id"))] = c.get("category_name") or ""
    except Exception:
        pass

    db.query(LiveTvChannel).filter(LiveTvChannel.source_id == source.id).delete()
    count = 0
    for row in rows:
        stream_id = row.get("stream_id")
        if stream_id is None:
            continue
        # standard Xtream live URL
        stream_url = f"{host}/live/{user}/{pw}/{stream_id}.ts"
        name = row.get("name") or f"Channel {stream_id}"
        group = cats.get(str(row.get("category_id") or ""), None)
        db.add(
            LiveTvChannel(
                source_id=source.id,
                name=str(name)[:500],
                group_title=(group or "")[:300] or None,
                logo=row.get("stream_icon") or None,
                stream_url=stream_url,
                tvg_id=str(row.get("epg_channel_id") or "") or None,
                enabled=True,
            )
        )
        count += 1
    source.channel_count = count
    source.last_sync_at = datetime.now(timezone.utc)
    db.add(source)
    db.commit()
    return count


def sync_source(db: Session, source: LiveTvSource) -> int:
    if source.kind == "xtream":
        return sync_xtream_source(db, source)
    return sync_m3u_source(db, source)


# ── EPG (XMLTV) now/next ──────────────────────────────────────────────────

_epg_cache: dict = {"fetched_at": None, "by_tvg": {}, "programmes": []}


def _parse_xmltv_dt(s: str):
    """XMLTV times like 20260807120000 +0000 or 20260807120000."""
    from datetime import datetime, timezone, timedelta
    if not s:
        return None
    s = s.strip()
    try:
        if len(s) >= 14 and s[:14].isdigit():
            dt = datetime.strptime(s[:14], "%Y%m%d%H%M%S")
            # optional timezone +HHMM / -HHMM
            rest = s[14:].strip()
            if rest.startswith("+") or rest.startswith("-"):
                sign = 1 if rest[0] == "+" else -1
                hh = int(rest[1:3] or 0)
                mm = int(rest[3:5] or 0)
                dt = dt.replace(tzinfo=timezone(sign * timedelta(hours=hh, minutes=mm)))
            else:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except Exception:
        return None
    return None


def fetch_and_index_epg(db: Session) -> dict:
    """Pull XMLTV from all sources with epg_url and index by tvg_id."""
    import httpx
    from app.clients.stalker import parse_epg_xmltv
    from app.models import LiveTvSource
    global _epg_cache
    from datetime import datetime, timezone

    programmes = []
    sources = db.query(LiveTvSource).filter(LiveTvSource.enabled.is_(True)).all()
    for src in sources:
        url = getattr(src, "epg_url", None) or None
        if not url:
            continue
        try:
            r = httpx.get(url, timeout=90.0, follow_redirects=True)
            r.raise_for_status()
            programmes.extend(parse_epg_xmltv(r.text))
        except Exception as exc:
            log.warning("EPG fetch failed for source %s: %s", src.id, exc)

    by_tvg: dict[str, list] = {}
    for p in programmes:
        cid = p.get("channel_id") or ""
        start = _parse_xmltv_dt(p.get("start") or "")
        stop = _parse_xmltv_dt(p.get("stop") or "")
        row = {
            "title": p.get("title") or "Unknown",
            "start": start.isoformat() if start else None,
            "stop": stop.isoformat() if stop else None,
            "start_dt": start,
            "stop_dt": stop,
            "channel_id": cid,
            "channel_name": p.get("channel_name"),
        }
        by_tvg.setdefault(cid, []).append(row)
    for cid in by_tvg:
        by_tvg[cid].sort(key=lambda x: x["start_dt"] or datetime.min.replace(tzinfo=timezone.utc))

    _epg_cache = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "by_tvg": by_tvg,
        "programmes": programmes,
    }
    return {"channels": len(by_tvg), "programmes": len(programmes)}


def now_next_for_tvg(tvg_id: str | None) -> dict:
    """Return {now, next} programme dicts for a channel tvg_id."""
    from datetime import datetime, timezone
    if not tvg_id:
        return {"now": None, "next": None}
    rows = (_epg_cache.get("by_tvg") or {}).get(tvg_id) or []
    if not rows:
        # try without prefix variants
        for k, v in (_epg_cache.get("by_tvg") or {}).items():
            if k.endswith(tvg_id) or tvg_id.endswith(k):
                rows = v
                break
    now = datetime.now(timezone.utc)
    current = None
    nxt = None
    for i, row in enumerate(rows):
        start, stop = row.get("start_dt"), row.get("stop_dt")
        if start and stop and start <= now < stop:
            current = {"title": row["title"], "start": row["start"], "stop": row["stop"]}
            if i + 1 < len(rows):
                n = rows[i + 1]
                nxt = {"title": n["title"], "start": n["start"], "stop": n["stop"]}
            break
        if start and start > now:
            nxt = {"title": row["title"], "start": row["start"], "stop": row["stop"]}
            break
    return {"now": current, "next": nxt}


def channel_lineup(db=None) -> dict:
    """Summary lineup for Live TV UI (MediaOs-style)."""
    try:
        from app.models import LiveTvChannel, LiveTvSource
        from app.database import SessionLocal
        own = db is None
        if own:
            db = SessionLocal()
        try:
            sources = db.query(LiveTvSource).all() if hasattr(db, "query") else []
            channels = db.query(LiveTvChannel).limit(500).all() if hasattr(db, "query") else []
            return {
                "sources": len(sources) if not isinstance(sources, list) else len(sources),
                "channels": [
                    {
                        "id": getattr(c, "id", None),
                        "name": getattr(c, "name", None) or getattr(c, "title", None),
                        "logo": getattr(c, "logo_url", None) or getattr(c, "logo", None),
                        "group": getattr(c, "group_title", None) or getattr(c, "category", None),
                        "epg_id": getattr(c, "epg_channel_id", None) or getattr(c, "tvg_id", None),
                    }
                    for c in (channels or [])[:200]
                ],
            }
        finally:
            if own:
                db.close()
    except Exception as e:
        return {"sources": 0, "channels": [], "error": str(e)}


def resolve_logo_url(name: str | None) -> str | None:
    """Best-effort logo path under /app/data/channel-logos or static."""
    if not name:
        return None
    from pathlib import Path
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    roots = [Path("/app/data/channel-logos"), Path("data/channel-logos"), Path("app/static/logos")]
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.is_file() and slug[:6] in p.stem.lower():
                return str(p)
    return None


def epg_now_next(tvg_id: str | None) -> dict:
    if not tvg_id:
        return {"now": None, "next": None}
    rows = (_epg_cache.get("by_tvg") or {}).get(tvg_id) or []
    # rows: list of {start, stop, title}
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    now_p = next_p = None
    for prog in rows:
        try:
            start = prog.get("start")
            stop = prog.get("stop")
            if isinstance(start, str):
                start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if isinstance(stop, str):
                stop = datetime.fromisoformat(stop.replace("Z", "+00:00"))
            if start and stop and start <= now <= stop:
                now_p = prog
            elif start and start > now and next_p is None:
                next_p = prog
        except Exception:
            continue
    return {"now": now_p, "next": next_p}


def epg_grid(db: Session, *, hours: int = 6, group: str | None = None) -> dict:
    """Channel x time grid with programme blocks for horizontal EPG UI."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    start_window = now - timedelta(minutes=30)
    end = now + timedelta(hours=hours)
    # 15-minute slots for denser header
    slots = []
    cursor = start_window.replace(minute=(start_window.minute // 15) * 15, second=0, microsecond=0)
    while cursor < end:
        slots.append(cursor.isoformat())
        cursor += timedelta(minutes=15)

    channels = db.query(LiveTvChannel).limit(400).all()
    if group:
        channels = [
            c for c in channels
            if (getattr(c, "group_title", None) or getattr(c, "category", None) or "") == group
        ]
    out_ch = []
    for c in channels:
        tvg = getattr(c, "tvg_id", None) or getattr(c, "epg_channel_id", None)
        now_next = epg_now_next(tvg) if tvg else {"now": None, "next": None}
        programmes = []
        if tvg:
            rows = (_epg_cache.get("by_tvg") or {}).get(tvg) or []
            for row in rows:
                try:
                    start_dt = row.get("start_dt")
                    stop_dt = row.get("stop_dt")
                    if not start_dt:
                        continue
                    if stop_dt and stop_dt < start_window:
                        continue
                    if start_dt > end:
                        continue
                    programmes.append({
                        "title": row.get("title"),
                        "start": row.get("start"),
                        "stop": row.get("stop"),
                        "start_dt": start_dt.isoformat() if hasattr(start_dt, "isoformat") else start_dt,
                        "stop_dt": stop_dt.isoformat() if stop_dt and hasattr(stop_dt, "isoformat") else stop_dt,
                    })
                except Exception:
                    continue
        out_ch.append({
            "id": c.id,
            "name": c.name,
            "logo": getattr(c, "logo", None),
            "group": getattr(c, "group_title", None) or getattr(c, "category", None),
            "tvg_id": tvg,
            "now": now_next.get("now"),
            "next": now_next.get("next"),
            "programmes": programmes[:120],
        })
    return {
        "from": start_window.isoformat(),
        "to": end.isoformat(),
        "hours": hours,
        "slots": slots,
        "channels": out_ch,
        "count": len(out_ch),
    }

