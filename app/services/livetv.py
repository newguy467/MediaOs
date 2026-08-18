"""Live TV: M3U playlist parse + Xtream Codes live stream list."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
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

# Marker prefix stored in LiveTvChannel.stream_url for Stalker/MAG channels
# whose real playback link hasn't been resolved yet (resolved lazily on
# first play — see resolve_stalker_stream_url()).
STALKER_PENDING_PREFIX = "stalker-pending://"


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
        # tv_archive (0/1) + tv_archive_duration (days) flag Xtream catch-up support
        has_archive = str(row.get("tv_archive") or 0) in ("1", "true", "True")
        archive_days = int(row.get("tv_archive_duration") or 0) if has_archive else 0
        db.add(
            LiveTvChannel(
                source_id=source.id,
                name=str(name)[:500],
                group_title=(group or "")[:300] or None,
                logo=row.get("stream_icon") or None,
                stream_url=stream_url,
                tvg_id=str(row.get("epg_channel_id") or "") or None,
                enabled=True,
                catchup=has_archive and archive_days > 0,
                catchup_days=archive_days,
                external_id=str(stream_id),
            )
        )
        count += 1
    source.channel_count = count
    source.last_sync_at = datetime.now(timezone.utc)
    db.add(source)
    db.commit()
    return count


def sync_stalker_source(db: Session, source: LiveTvSource) -> int:
    """Scan a Stalker/MAG portal: handshake, walk genres, persist channels.

    Live stream links are resolved lazily (on first play) rather than during
    the scan — Stalker portals issue short-lived, single-use tokens via
    ``create_link``, so resolving all of them up front is both wasted work
    (they may expire before ever being played) and slow for large portals
    (one extra HTTP round-trip per channel). Instead ``stream_url`` stores a
    ``STALKER_PENDING_PREFIX``-marked placeholder; ``external_id`` stores the
    raw Stalker ``cmd`` needed to resolve a fresh link at play time via
    :func:`resolve_stalker_stream_url`.
    """
    from app.clients.stalker import StalkerClient

    portal_url = (source.url or source.xtream_host or "").strip()
    if not portal_url:
        raise ValueError("Stalker source missing portal URL")
    mac = source.stalker_mac or None
    client = StalkerClient(portal_url, mac)
    client.handshake()
    if not client.mac:
        raise RuntimeError("Stalker handshake failed")
    if mac is None:
        # persist the (possibly auto-generated) MAC so future syncs reuse it
        source.stalker_mac = client.mac

    genres = client.get_genres()
    genre_ids = [g.get("id") for g in genres if isinstance(g, dict) and g.get("id")] or ["*"]

    db.query(LiveTvChannel).filter(LiveTvChannel.source_id == source.id).delete()
    count = 0
    seen_cmds: set[str] = set()
    for genre_id in genre_ids:
        page = 1
        while True:
            try:
                items = client.get_ordered_list(genre=str(genre_id), page=page)
            except Exception as exc:  # portal hiccup on one genre/page shouldn't kill the whole scan
                log.info("Stalker genre %s page %s failed: %s", genre_id, page, exc)
                break
            if not items:
                break
            for it in items:
                cmd = it.get("cmd") or ""
                if not cmd or cmd in seen_cmds:
                    continue
                seen_cmds.add(cmd)
                name = it.get("name") or f"Channel {len(seen_cmds)}"
                has_archive = str(it.get("tv_archive") or 0) in ("1", "true", "True")
                archive_days = int(it.get("tv_archive_duration") or 0) if has_archive else 0
                db.add(
                    LiveTvChannel(
                        source_id=source.id,
                        name=str(name)[:500],
                        group_title=None,
                        logo=it.get("logo") or None,
                        stream_url=STALKER_PENDING_PREFIX + cmd,
                        tvg_id=str(it.get("xmltv_id") or "") or None,
                        enabled=True,
                        catchup=has_archive and archive_days > 0,
                        catchup_days=archive_days,
                        external_id=cmd,
                    )
                )
                count += 1
            if len(items) < 14:  # Stalker portals typically page in chunks of 14
                break
            page += 1
    source.channel_count = count
    source.last_sync_at = datetime.now(timezone.utc)
    db.add(source)
    db.commit()
    return count


def sync_source(db: Session, source: LiveTvSource) -> int:
    if source.kind == "xtream":
        return sync_xtream_source(db, source)
    if source.kind == "stalker":
        return sync_stalker_source(db, source)
    return sync_m3u_source(db, source)


def resolve_stalker_stream_url(source: LiveTvSource, channel: LiveTvChannel) -> str | None:
    """Resolve a fresh playback link for a Stalker channel synced lazily.

    Called on-demand (e.g. from the stream proxy) rather than at sync time,
    since portal-issued links are short-lived/single-use. Returns None if
    the channel isn't a pending Stalker channel or resolution fails.
    """
    if source.kind != "stalker":
        return None
    cmd = channel.external_id or ""
    if not cmd:
        return None
    from app.clients.stalker import StalkerClient

    portal_url = (source.url or source.xtream_host or "").strip()
    if not portal_url:
        return None
    client = StalkerClient(portal_url, source.stalker_mac)
    try:
        client.handshake()
        return client.create_link(cmd)
    except Exception as exc:
        log.info("Stalker link resolve failed for channel %s: %s", channel.id, exc)
        return None


def catchup_url_for_channel(source: LiveTvSource, channel: LiveTvChannel, start: datetime, end: datetime) -> str | None:
    """Build a catch-up/timeshift playback URL for a past program, or None if unsupported."""
    if not channel.catchup:
        return None
    duration_min = max(1, int((end - start).total_seconds() // 60))
    if source.kind == "xtream":
        host = (source.xtream_host or "").rstrip("/")
        user = source.xtream_username or ""
        pw = source.xtream_password or ""
        stream_id = channel.external_id or ""
        if not (host and user and stream_id):
            return None
        ts = start.strftime("%Y-%m-%d:%H-%M")
        return f"{host}/timeshift/{user}/{pw}/{duration_min}/{ts}/{stream_id}.ts"
    if source.kind == "stalker":
        from app.clients.stalker import StalkerClient

        portal_url = (source.url or source.xtream_host or "").strip()
        cmd = channel.external_id or ""
        if not (portal_url and cmd):
            return None
        client = StalkerClient(portal_url, source.stalker_mac)
        client.handshake()
        try:
            return client.create_timeshift_link(cmd, start, duration_min)
        except Exception as exc:
            log.info("Stalker catch-up link failed for channel %s: %s", channel.id, exc)
            return None
    return None


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



def effective_tvg_id(channel) -> str | None:
    """Prefer manual epg_tvg_id override, else playlist tvg_id."""
    override = getattr(channel, "epg_tvg_id", None)
    if override and str(override).strip():
        return str(override).strip()
    tvg = getattr(channel, "tvg_id", None)
    return str(tvg).strip() if tvg else None


def fetch_and_index_epg(db: Session) -> dict:
    """Pull XMLTV from all source epg_urls + global extra URLs; merge into one cache."""
    import httpx
    from app.clients.stalker import parse_epg_xmltv
    from app.config import settings
    from app.models import LiveTvSource

    global _epg_cache
    urls: list[str] = []
    for src in db.query(LiveTvSource).filter(LiveTvSource.enabled.is_(True)).all():
        u = (getattr(src, "epg_url", None) or "").strip()
        if u and u not in urls:
            urls.append(u)
    # Extra URLs from settings (comma-separated)
    extra = (getattr(settings, "livetv_epg_extra_urls", "") or "").strip()
    sidecar = (getattr(settings, "livetv_epg_sidecar_url", "") or "").strip()
    if sidecar and sidecar not in (extra or ""):
        extra = (extra + "," + sidecar) if extra else sidecar
    for part in extra.replace("\n", ",").split(","):
        u = part.strip()
        if u and u not in urls:
            urls.append(u)

    programmes = []
    errors = []
    fetched = 0
    for url in urls:
        try:
            with httpx.Client(timeout=90.0, follow_redirects=True, headers={
                "User-Agent": "MediaOs/4.9 LiveTV-EPG",
            }) as client:
                r = client.get(url)
                r.raise_for_status()
                text = r.text
                # gzip magic handled by httpx if Content-Encoding; some hosts serve .xml.gz raw
                if url.endswith(".gz") and not text.lstrip().startswith("<"):
                    import gzip
                    text = gzip.decompress(r.content).decode("utf-8", errors="replace")
                programmes.extend(parse_epg_xmltv(text) or [])
                fetched += 1
        except Exception as e:
            log.warning("EPG fetch failed %s: %s", url, e)
            errors.append({"url": url, "error": str(e)})

    by_tvg: dict = {}
    for p in programmes:
        tvg = (p.get("channel") or p.get("tvg_id") or "").strip()
        if not tvg:
            continue
        start = _parse_xmltv_dt(p.get("start") or "")
        stop = _parse_xmltv_dt(p.get("stop") or "")
        row = {
            "title": p.get("title") or p.get("name"),
            "start": p.get("start"),
            "stop": p.get("stop"),
            "start_dt": start,
            "stop_dt": stop,
            "desc": p.get("desc") or p.get("description"),
        }
        by_tvg.setdefault(tvg, []).append(row)

    for tvg, rows in by_tvg.items():
        rows.sort(key=lambda x: x.get("start") or "")

    _epg_cache = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "by_tvg": by_tvg,
        "programmes": programmes[:5],  # sample
        "urls": urls,
        "errors": errors,
    }
    return {
        "urls": len(urls),
        "fetched": fetched,
        "channels_with_guide": len(by_tvg),
        "programmes": sum(len(v) for v in by_tvg.values()),
        "errors": errors[:8],
        "fetched_at": _epg_cache["fetched_at"],
    }


def list_epg_channel_ids() -> list[dict]:
    """Channel ids present in the current EPG cache (for mapping UI)."""
    out = []
    for tvg, rows in (_epg_cache.get("by_tvg") or {}).items():
        sample = rows[0]["title"] if rows else None
        out.append({"tvg_id": tvg, "programmes": len(rows), "sample_title": sample})
    out.sort(key=lambda x: x["tvg_id"])
    return out


def suggest_tvg_match(channel_name: str, limit: int = 8) -> list[dict]:
    """Fuzzy-ish match channel name against EPG ids."""
    name = (channel_name or "").lower().strip()
    if not name:
        return []
    tokens = [t for t in re.split(r"[^a-z0-9]+", name) if len(t) > 1]
    scored = []
    for tvg, rows in (_epg_cache.get("by_tvg") or {}).items():
        tid = tvg.lower()
        score = 0
        if name in tid or tid in name:
            score += 50
        for t in tokens:
            if t in tid:
                score += 10
        if score:
            scored.append({"tvg_id": tvg, "score": score, "programmes": len(rows)})
    scored.sort(key=lambda x: -x["score"])
    return scored[:limit]


def check_channel_stream(url: str, timeout: float = 8.0) -> tuple[bool, str | None]:
    """Lightweight reachability probe (HEAD/GET first bytes)."""
    import httpx
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers={
            "User-Agent": "MediaOs/4.9 LiveTV-Health",
        }) as client:
            # Prefer GET range — many IPTV hosts ignore HEAD
            r = client.get(url, headers={"Range": "bytes=0-1024"})
            if r.status_code in (200, 206, 302, 301):
                return True, None
            if r.status_code in (401, 403):
                return True, f"auth {r.status_code}"  # reachable but gated
            return False, f"http {r.status_code}"
    except Exception as e:
        return False, str(e)[:200]


def run_channel_health_cycle(db: Session) -> dict:
    """Probe channels; mark failures; delete/disable if offline > 12 hours.

    Runs automatically server-side on a schedule (see app/scheduler.py,
    `mediaos_livetv_health` job) — no user action needed. Once a channel is
    deleted here it also disappears from the M3U/XMLTV export MediaOS serves
    to Jellyfin (only enabled channels are included), so Jellyfin's Live TV
    tuner drops it on its next guide/channel refresh automatically.

    Policy (settings):
      livetv_offline_hours (default 12)
      livetv_offline_action: delete | disable (default delete)
      livetv_health_batch (default 40 channels probed per cycle)
      livetv_health_interval_minutes (default 30, how often this cycle runs)
    """
    from app.config import settings
    from app.models import LiveTvChannel

    offline_h = float(getattr(settings, "livetv_offline_hours", 12) or 12)
    action = (getattr(settings, "livetv_offline_action", "delete") or "delete").lower()
    batch = int(getattr(settings, "livetv_health_batch", 40) or 40)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=offline_h)

    # Prefer never-checked, then oldest last_check
    channels = (
        db.query(LiveTvChannel)
        .filter(LiveTvChannel.enabled.is_(True))
        .order_by(LiveTvChannel.last_check_at.nullsfirst())
        .limit(batch)
        .all()
    )
    ok = fail = deleted = disabled = 0
    _stalker_source_cache: dict[int, LiveTvSource] = {}
    for ch in channels:
        probe_url = ch.stream_url
        if probe_url and probe_url.startswith(STALKER_PENDING_PREFIX):
            src = _stalker_source_cache.get(ch.source_id)
            if src is None:
                src = db.get(LiveTvSource, ch.source_id)
                if src:
                    _stalker_source_cache[ch.source_id] = src
            resolved = resolve_stalker_stream_url(src, ch) if src else None
            if not resolved:
                # Couldn't get a token this cycle — don't count it as a hard
                # failure (portal hiccup), just skip and retry next cycle.
                ch.last_check_at = now
                continue
            probe_url = resolved
        good, err = check_channel_stream(probe_url)
        ch.last_check_at = now
        if good:
            ch.last_ok_at = now
            ch.fail_count = 0
            ch.last_error = None
            ok += 1
        else:
            ch.fail_count = int(ch.fail_count or 0) + 1
            ch.last_error = err
            fail += 1
            last_ok = ch.last_ok_at
            # A channel is "dead" once it's been more than `offline_h` hours since we
            # last confirmed it was reachable. If it has never once succeeded, fall
            # back to when it was added (created_at) so brand-new-but-broken channels
            # still get cleaned up on the same 12h clock instead of lingering forever.
            reference = last_ok or ch.created_at
            if reference is None:
                # Legacy row from before created_at existed, never checked OK.
                # Anchor the clock to right now and persist it so this channel
                # still gets a full offline window before being swept, instead
                # of either being deleted immediately or never aging out.
                ch.created_at = now
                reference = now
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)
            stale = reference < cutoff
            if stale:
                if action == "disable":
                    ch.enabled = False
                    disabled += 1
                else:
                    db.delete(ch)
                    deleted += 1
                    continue
        db.add(ch)
    db.commit()
    return {
        "checked": ok + fail,
        "ok": ok,
        "failed": fail,
        "deleted": deleted,
        "disabled": disabled,
        "offline_hours": offline_h,
        "action": action,
    }



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
        tvg = effective_tvg_id(c)
        now_next = epg_now_next(tvg) if tvg else {"now": None, "next": None}
        programmes = []
        ch_catchup = bool(getattr(c, "catchup", False))
        # Mirrors the exact window check in the /catchup/{channel_id} endpoint
        # (router uses the same max(1, catchup_days or 1) floor) so a badge/menu
        # item shown here never offers a request the backend will then 400 on.
        oldest_allowed = now - timedelta(days=max(1, getattr(c, "catchup_days", 0) or 1))
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
                    catchup_available = bool(
                        ch_catchup
                        and start_dt <= now
                        and start_dt >= oldest_allowed
                    )
                    programmes.append({
                        "title": row.get("title"),
                        "start": row.get("start"),
                        "stop": row.get("stop"),
                        "start_dt": start_dt.isoformat() if hasattr(start_dt, "isoformat") else start_dt,
                        "stop_dt": stop_dt.isoformat() if stop_dt and hasattr(stop_dt, "isoformat") else stop_dt,
                        "catchup_available": catchup_available,
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
            "catchup": bool(getattr(c, "catchup", False)),
            "catchup_days": getattr(c, "catchup_days", 0) or 0,
        })
    # Mark programmes that overlap scheduled/active DVR recordings (same channel + time)
    try:
        from app.models import LiveTvRecording
        recs = (
            db.query(LiveTvRecording)
            .filter(LiveTvRecording.status.in_(["scheduled", "recording"]))
            .all()
        )
        def overlaps(a0, a1, b0, b1):
            if not a0 or not a1 or not b0 or not b1:
                return False
            return a0 < b1 and b0 < a1
        for ch in out_ch:
            cid = ch.get("id")
            for prog in ch.get("programmes") or []:
                ps = prog.get("start_dt") or prog.get("start")
                pe = prog.get("stop_dt") or prog.get("stop")
                try:
                    from datetime import datetime
                    if isinstance(ps, str):
                        ps = datetime.fromisoformat(ps.replace("Z", "+00:00"))
                    if isinstance(pe, str):
                        pe = datetime.fromisoformat(pe.replace("Z", "+00:00"))
                except Exception:
                    continue
                for rec in recs:
                    if getattr(rec, "channel_id", None) not in (None, cid) and rec.channel_id != cid:
                        continue
                    if overlaps(ps, pe, rec.starts_at, rec.ends_at):
                        prog["_conflict"] = True
                        break
    except Exception:
        pass
    return {
        "from": start_window.isoformat(),
        "to": end.isoformat(),
        "hours": hours,
        "slots": slots,
        "channels": out_ch,
        "count": len(out_ch),
    }



def build_xmltv_export(db: Session, base_url: str = "") -> str:
    """Build a minimal XMLTV document from channels + in-memory EPG cache if present."""
    from xml.sax.saxutils import escape, quoteattr
    from app.models import LiveTvChannel, LiveTvVirtualChannel, LiveTvVirtualScheduleItem

    channels = (
        db.query(LiveTvChannel)
        .filter(LiveTvChannel.enabled.is_(True))
        .order_by(LiveTvChannel.name)
        .all()
    )
    vchannels = (
        db.query(LiveTvVirtualChannel)
        .filter(LiveTvVirtualChannel.enabled.is_(True))
        .order_by(LiveTvVirtualChannel.number)
        .all()
    )
    # optional EPG cache from epg module
    by_tvg = {}
    try:
        from app.services import livetv as selfmod
        cache = getattr(selfmod, "_epg_cache", None) or {}
        by_tvg = cache.get("by_tvg") or {}
    except Exception:
        pass

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE tv SYSTEM "xmltv.dtd">',
        f'<tv generator-info-name="MediaOs" source-info-name="MediaOs Live TV">',
    ]
    for ch in channels:
        tvg = ch.tvg_id or str(ch.id)
        parts.append(f'  <channel id={quoteattr(tvg)}>')
        parts.append(f'    <display-name>{escape(ch.name or tvg)}</display-name>')
        if ch.logo:
            parts.append(f'    <icon src={quoteattr(ch.logo)} />')
        parts.append("  </channel>")
    for vc in vchannels:
        tvg = f"virtual-{vc.id}"
        parts.append(f'  <channel id={quoteattr(tvg)}>')
        parts.append(f'    <display-name>{escape(f"{vc.number} {vc.name}")}</display-name>')
        if vc.logo:
            parts.append(f'    <icon src={quoteattr(vc.logo)} />')
        parts.append("  </channel>")

    for ch in channels:
        tvg = ch.tvg_id or str(ch.id)
        rows = by_tvg.get(tvg) or []
        for row in rows[:50]:
            start = row.get("start") or ""
            stop = row.get("stop") or ""
            title = row.get("title") or "Programme"
            if not start:
                continue
            parts.append(f'  <programme start={quoteattr(str(start))} stop={quoteattr(str(stop))} channel={quoteattr(tvg)}>')
            parts.append(f'    <title>{escape(str(title))}</title>')
            parts.append("  </programme>")

    for vc in vchannels:
        tvg = f"virtual-{vc.id}"
        items = (
            db.query(LiveTvVirtualScheduleItem)
            .filter(LiveTvVirtualScheduleItem.virtual_channel_id == vc.id)
            .order_by(LiveTvVirtualScheduleItem.start_time.asc())
            .limit(100)
            .all()
        )
        for item in items:
            start = item.start_time
            stop = start + timedelta(seconds=item.duration_seconds)
            xstart = start.strftime("%Y%m%d%H%M%S +0000")
            xstop = stop.strftime("%Y%m%d%H%M%S +0000")
            parts.append(f'  <programme start={quoteattr(xstart)} stop={quoteattr(xstop)} channel={quoteattr(tvg)}>')
            parts.append(f'    <title>{escape(item.title)}</title>')
            parts.append("  </programme>")

    parts.append("</tv>")
    return '\n'.join(parts) + '\n'


def epg_programmes_for_rules(db: Session, hours: int = 48) -> list[dict]:
    """Flatten EPG grid + cache into series-rule input rows (production-safe)."""
    items: list[dict] = []
    try:
        grid = epg_grid(db, hours=hours)
        for ch in grid.get("channels") or []:
            ch_id = ch.get("id") or ch.get("channel_id")
            stream = ch.get("stream_url")
            tvg = ch.get("tvg_id") or ch.get("epg_tvg_id")
            for prog in ch.get("programmes") or ch.get("programs") or []:
                items.append({
                    "title": prog.get("title") or prog.get("name"),
                    "channel_id": ch_id,
                    "starts_at": prog.get("start") or prog.get("starts_at"),
                    "ends_at": prog.get("stop") or prog.get("ends_at"),
                    "subtitle": prog.get("desc") or prog.get("subtitle"),
                    "tvg_id": tvg,
                    "stream_url": stream,
                })
    except Exception:
        pass
    # Fallback: indexed cache by tvg
    try:
        from app.models import LiveTvChannel
        cache = globals().get("_epg_cache") or {}
        by_tvg = cache.get("by_tvg") or {}
        channels = { (c.epg_tvg_id or c.tvg_id): c for c in db.query(LiveTvChannel).all() if (getattr(c, "epg_tvg_id", None) or getattr(c, "tvg_id", None)) }
        for tvg, rows in by_tvg.items():
            ch = channels.get(tvg)
            for prog in rows or []:
                items.append({
                    "title": prog.get("title") or prog.get("name"),
                    "channel_id": ch.id if ch else None,
                    "starts_at": prog.get("start") or prog.get("starts_at"),
                    "ends_at": prog.get("stop") or prog.get("ends_at"),
                    "subtitle": prog.get("desc"),
                    "tvg_id": tvg,
                    "stream_url": ch.stream_url if ch else None,
                })
    except Exception:
        pass
    # Dedupe by title+start+channel
    seen = set()
    out = []
    for it in items:
        key = (it.get("title"), str(it.get("starts_at")), it.get("channel_id"))
        if key in seen or not it.get("title"):
            continue
        seen.add(key)
        out.append(it)
    return out
