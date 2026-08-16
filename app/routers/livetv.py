from datetime import datetime
import logging

from app.auth import require_permission
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LiveTvChannel, LiveTvSource
from app.services.livetv import sync_source

log = logging.getLogger("mediaos.livetv")
router = APIRouter(prefix="/livetv", tags=["livetv"])


class SourceCreate(BaseModel):
    name: str
    kind: str = "m3u"  # m3u | xtream
    url: str | None = None
    xtream_host: str | None = None
    xtream_username: str | None = None
    xtream_password: str | None = None
    enabled: bool = True
    epg_url: str | None = None


class SourceOut(BaseModel):
    id: int
    name: str
    kind: str
    url: str | None
    xtream_host: str | None
    enabled: bool
    channel_count: int
    last_sync_at: datetime | None
    epg_url: str | None = None

    class Config:
        from_attributes = True


class ChannelOut(BaseModel):
    id: int
    source_id: int
    name: str
    group_title: str | None
    logo: str | None
    stream_url: str
    tvg_id: str | None
    enabled: bool
    sort_order: int = 0

    class Config:
        from_attributes = True


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    return db.query(LiveTvSource).order_by(LiveTvSource.name).all()


@router.post("/sources", response_model=SourceOut)
def add_source(payload: SourceCreate, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "settings"))):
    if payload.kind not in ("m3u", "xtream"):
        raise HTTPException(400, "kind must be m3u or xtream")
    src = LiveTvSource(
        name=payload.name,
        kind=payload.kind,
        url=payload.url,
        xtream_host=payload.xtream_host,
        xtream_username=payload.xtream_username,
        xtream_password=payload.xtream_password,
        enabled=payload.enabled,
        epg_url=getattr(payload, "epg_url", None),
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "settings"))):
    src = db.get(LiveTvSource, source_id)
    if not src:
        raise HTTPException(404, "Not found")
    db.query(LiveTvChannel).filter(LiveTvChannel.source_id == source_id).delete()
    db.delete(src)
    db.commit()


@router.post("/sources/{source_id}/sync")
def sync(source_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "settings"))):
    src = db.get(LiveTvSource, source_id)
    if not src:
        raise HTTPException(404, "Not found")
    try:
        n = sync_source(db, src)
    except Exception as exc:
        raise HTTPException(502, f"Sync failed: {exc}") from exc
    return {"synced": n, "source_id": source_id}


@router.get("/channels", response_model=list[ChannelOut])
def list_channels(
    q: str | None = None,
    group: str | None = None,
    source_id: int | None = None,
    limit: int = 500,
    db: Session = Depends(get_db),
):
    query = db.query(LiveTvChannel).filter(LiveTvChannel.enabled.is_(True))
    if source_id is not None:
        query = query.filter(LiveTvChannel.source_id == source_id)
    if group:
        query = query.filter(LiveTvChannel.group_title == group)
    if q:
        query = query.filter(LiveTvChannel.name.ilike(f"%{q}%"))
    try:
        return query.order_by(LiveTvChannel.sort_order, LiveTvChannel.group_title, LiveTvChannel.name).limit(limit).all()
    except Exception:
        return query.order_by(LiveTvChannel.group_title, LiveTvChannel.name).limit(limit).all()


@router.get("/groups")
def list_groups(source_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(LiveTvChannel.group_title).filter(LiveTvChannel.enabled.is_(True))
    if source_id is not None:
        query = query.filter(LiveTvChannel.source_id == source_id)
    rows = query.distinct().all()
    return sorted({r[0] or "Other" for r in rows})


@router.get("/channels/editor")
def list_channels_editor(
    source_id: int | None = None,
    group: str | None = None,
    include_disabled: bool = True,
    limit: int = 2000,
    db: Session = Depends(get_db),
    _perm: list = Depends(require_permission("library.manage", "settings")),
):
    """Full channel list for the editor (includes disabled by default)."""
    q = db.query(LiveTvChannel)
    if source_id is not None:
        q = q.filter(LiveTvChannel.source_id == source_id)
    if group:
        q = q.filter(LiveTvChannel.group_title == group)
    if not include_disabled:
        q = q.filter(LiveTvChannel.enabled.is_(True))
    try:
        rows = q.order_by(LiveTvChannel.sort_order, LiveTvChannel.group_title, LiveTvChannel.name).limit(min(limit, 5000)).all()
    except Exception:
        rows = q.order_by(LiveTvChannel.group_title, LiveTvChannel.name).limit(min(limit, 5000)).all()
    return rows


# NOTE: "/channels/{channel_id}" below is a dynamic path segment, so literal
# routes under the same "/channels" prefix (like "/channels/editor" above)
# must be registered before it, or FastAPI/Starlette will try to parse the
# literal segment as channel_id first and 422 instead of matching correctly.
@router.get("/channels/{channel_id}", response_model=ChannelOut)
def get_channel(channel_id: int, db: Session = Depends(get_db)):
    ch = db.get(LiveTvChannel, channel_id)
    if not ch:
        raise HTTPException(404, "Not found")
    return ch


from fastapi import HTTPException, Query
from pydantic import BaseModel

@router.get("/epg")
def epg_guide(source_id: int | None = None, limit: int = 500, refresh: bool = False):
    """EPG now/next guide from stored channels + XMLTV on sources."""
    from app.database import SessionLocal
    from app.models import LiveTvChannel
    from app.services.livetv import effective_tvg_id, fetch_and_index_epg, now_next_for_tvg, _epg_cache
    db = SessionLocal()
    try:
        if refresh or not (_epg_cache.get("by_tvg")):
            try:
                fetch_and_index_epg(db)
            except Exception:
                pass
        channels = db.query(LiveTvChannel).order_by(LiveTvChannel.group_title, LiveTvChannel.name).limit(limit).all()
        out = []
        for ch in channels:
            nn = now_next_for_tvg(effective_tvg_id(ch))
            out.append({
                "id": ch.id,
                "name": ch.name,
                "group": ch.group_title,
                "logo": ch.logo,
                "tvg_id": ch.tvg_id,
                "stream_url": ch.stream_url,
                "now": nn.get("now"),
                "next": nn.get("next"),
            })
        return {"channels": out, "count": len(out), "epg_fetched_at": _epg_cache.get("fetched_at")}
    finally:
        db.close()


@router.post("/epg/refresh")
def epg_refresh(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "settings"))):
    from app.services.livetv import fetch_and_index_epg
    try:
        stats = fetch_and_index_epg(db)
        return {"ok": True, **stats}
    except Exception as exc:
        raise HTTPException(502, f"EPG refresh failed: {exc}")


class StalkerIn(BaseModel):
    portal_url: str
    mac: str | None = None
    discover: bool = False
    discover_attempts: int = 6


@router.post("/stalker/connect")
def stalker_connect(body: StalkerIn, _perm: list = Depends(require_permission("library.manage", "settings"))):
    from app.clients.stalker import StalkerClient
    client = StalkerClient(body.portal_url, body.mac)
    hs = client.handshake()
    profile = {}
    try:
        profile = client.get_profile()
    except Exception:
        pass
    macs = []
    if body.discover:
        macs = client.discover_macs(body.discover_attempts)
    genres = []
    try:
        genres = client.get_genres()
    except Exception:
        pass
    channels = []
    try:
        channels = client.get_ordered_list(page=1)[:50]
    except Exception:
        pass
    return {
        "handshake": hs,
        "profile_keys": list(profile.keys()) if isinstance(profile, dict) else [],
        "mac": client.mac,
        "token": bool(client.token),
        "discovered_macs": macs,
        "genres": genres[:30] if isinstance(genres, list) else genres,
        "channels_sample": channels,
    }




@router.get("/portal/health")
def portal_health(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.view", "settings"))):
    """Lightweight Live TV health: channel counts, EPG cache age, sample stream URL presence."""
    from app.models import LiveTvChannel
    from app.services.livetv import _epg_cache
    channels = db.query(LiveTvChannel).all() if hasattr(db, "query") else []
    try:
        channels = db.query(LiveTvChannel).all()
    except Exception:
        channels = []
    total = len(channels)
    with_stream = sum(1 for c in channels if getattr(c, "stream_url", None))
    enabled = sum(1 for c in channels if getattr(c, "enabled", True))
    epg_at = _epg_cache.get("fetched_at") if isinstance(_epg_cache, dict) else None
    epg_channels = len((_epg_cache or {}).get("by_tvg") or {}) if isinstance(_epg_cache, dict) else 0
    return {
        "ok": total > 0 and with_stream > 0,
        "channels": total,
        "enabled": enabled,
        "with_stream_url": with_stream,
        "epg_fetched_at": epg_at,
        "epg_tvg_ids": epg_channels,
        "hints": [] if total and with_stream else [
            "Import an M3U or connect a portal",
            "Map EPG / refresh XMLTV",
            "Enable channels in the lineup editor",
        ],
    }


@router.get("/guide")
def guide_grid():
    """Channel grid payload for full EPG UX."""
    data = epg_guide(limit=800)
    groups: dict[str, list] = {}
    for ch in data["channels"]:
        g = ch.get("group") or "Other"
        groups.setdefault(g, []).append(ch)
    return {"groups": groups, "group_names": sorted(groups.keys()), "total": data["count"]}


@router.get("/lineup")
def get_lineup(db: Session = Depends(get_db)):
    from app.services.livetv import channel_lineup
    return channel_lineup(db)


@router.get("/logos/index")
def logos_index():
    from app.services.livetv_logos import index_logos, logo_root
    return {"root": str(logo_root()), "logos": index_logos()}


@router.post("/logos/import")
async def logos_import(request: Request, db: Session = Depends(get_db)):
    """Import logo pack from uploaded zip (multipart field `file`) or JSON `{ "path": "..." }`."""
    from app.services.livetv_logos import import_logo_pack, match_logos_to_channels
    import tempfile
    from pathlib import Path as P

    content_type = request.headers.get("content-type", "")
    overwrite = False
    if "multipart" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None:
            return {"ok": False, "error": "file required"}
        data = await upload.read()
        tmp = P(tempfile.gettempdir()) / "mediaos-logos.zip"
        tmp.write_bytes(data)
        result = import_logo_pack(tmp)
        overwrite = str(form.get("overwrite") or "").lower() in ("1", "true", "yes")
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        path = (body or {}).get("path")
        if not path:
            return {"ok": False, "error": "path or multipart file required"}
        overwrite = bool((body or {}).get("overwrite"))
        result = import_logo_pack(path)

    if result.get("ok"):
        result["match"] = match_logos_to_channels(db, overwrite=overwrite)
    return result


@router.post("/logos/match")
def logos_match(overwrite: bool = False, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "settings"))):
    from app.services.livetv_logos import match_logos_to_channels
    return match_logos_to_channels(db, overwrite=overwrite)


@router.get("/logos/{logo_path:path}")
def serve_logo(logo_path: str):
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    from app.services.livetv_logos import logo_root
    root = logo_root().resolve()
    target = (root / logo_path).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(404, "logo not found")
    return FileResponse(target)


@router.get("/epg/grid")
def get_epg_grid(hours: int = 6, group: str | None = None, db: Session = Depends(get_db)):
    from app.services.livetv import epg_grid
    return epg_grid(db, hours=hours, group=group)


@router.get("/presets/iptv-org")
def iptv_org_presets():
    """List official iptv-org playlist URLs (auto-updated upstream)."""
    from app.services.livetv_defaults import list_presets
    return {"presets": list_presets(), "docs": "https://github.com/iptv-org/iptv"}


@router.post("/presets/iptv-org/seed")
def iptv_org_seed(
    keys: list[str] | None = None,
    sync: bool = True,
    db: Session = Depends(get_db),
    _perm: list = Depends(require_permission("library.manage", "settings")),
):
    """Add iptv-org M3U sources and sync channels. Default: US + Entertainment."""
    from app.services.livetv_defaults import seed_default_sources
    return seed_default_sources(db, sync=sync, keys=keys)


@router.post("/presets/iptv-org/resync")
def iptv_org_resync(
    db: Session = Depends(get_db),
    _perm: list = Depends(require_permission("library.manage", "settings")),
):
    from app.services.livetv_defaults import resync_iptv_org_sources
    return resync_iptv_org_sources(db)


@router.post("/logos/install-remote")
def logos_install_remote(
    limit: int = 500,
    db: Session = Depends(get_db),
    _perm: list = Depends(require_permission("library.manage", "settings")),
):
    """Cache channel tvg-logo HTTP URLs locally under data/channel-logos/remote/."""
    from app.services.livetv_logos import install_remote_logos
    return install_remote_logos(db, limit=max(1, min(limit, 2000)))


@router.get("/export/playlist.m3u")
def export_m3u_playlist(
    request: Request,
    source_id: int | None = None,
    db: Session = Depends(get_db),
):
    """M3U for Jellyfin Live TV / other players.

    Channel URLs point at MediaOs proxy so Jellyfin pulls through us:
      /api/livetv/stream/{channel_id}
    Set Jellyfin → Live TV → M3U Tuner → this playlist URL.
    """
    from fastapi.responses import PlainTextResponse
    from app.models import LiveTvVirtualChannel as VC

    base = str(request.base_url).rstrip("/")
    q = db.query(LiveTvChannel).filter(LiveTvChannel.enabled.is_(True))
    if source_id is not None:
        q = q.filter(LiveTvChannel.source_id == source_id)
    channels = q.order_by(LiveTvChannel.group_title, LiveTvChannel.name).all()
    lines = ["#EXTM3U"]
    for ch in channels:
        group = ch.group_title or "MediaOs"
        logo = ch.logo or ""
        tvg = ch.tvg_id or str(ch.id)
        name = (ch.name or f"Channel {ch.id}").replace("\n", " ")
        lines.append(
            f'#EXTINF:-1 tvg-id="{tvg}" tvg-name="{name}" '
            f'tvg-logo="{logo}" group-title="{group}",{name}'
        )
        lines.append(f"{base}/api/livetv/stream/{ch.id}")

    if source_id is None:
        vchannels = db.query(VC).filter(VC.enabled.is_(True)).order_by(VC.number).all()
        for vc in vchannels:
            group = vc.group_title or "Personal Media"
            logo = vc.logo or ""
            tvg = f"virtual-{vc.id}"
            name = (vc.name or f"Channel {vc.number}").replace("\n", " ")
            lines.append(
                f'#EXTINF:-1 tvg-id="{tvg}" tvg-name="{name}" tvg-chno="{vc.number}" '
                f'tvg-logo="{logo}" group-title="{group}",{name}'
            )
            lines.append(f"{base}/api/livetv/virtual/stream/{vc.id}/stream.m3u8")

    body = '\n'.join(lines) + '\n'
    return PlainTextResponse(
        body,
        media_type="application/x-mpegURL",
        headers={"Content-Disposition": 'attachment; filename="mediaos-livetv.m3u"'},
    )


@router.get("/export/guide.xml")
def export_xmltv_guide(
    request: Request,
    db: Session = Depends(get_db),
):
    """XMLTV guide export for Jellyfin (pair with playlist.m3u)."""
    from fastapi.responses import Response
    from app.services.livetv import build_xmltv_export

    xml = build_xmltv_export(db, base_url=str(request.base_url).rstrip("/"))
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="mediaos-guide.xml"'},
    )


@router.get("/stream/{channel_id}")
def proxy_channel_stream(channel_id: int, request: Request, db: Session = Depends(get_db)):
    """Proxy live stream — used by in-app player and Jellyfin M3U tuner."""
    from fastapi.responses import StreamingResponse, RedirectResponse
    import httpx

    ch = db.get(LiveTvChannel, channel_id)
    if not ch or not ch.enabled:
        raise HTTPException(404, "Channel not found")
    url = (ch.stream_url or "").strip()
    if not url:
        raise HTTPException(404, "No stream URL")

    # HLS playlists: redirect so clients follow upstream
    if ".m3u8" in url.lower() or url.lower().endswith(".m3u"):
        return RedirectResponse(url, status_code=302)

    def gen():
        try:
            with httpx.stream("GET", url, timeout=60.0, follow_redirects=True, headers={
                "User-Agent": "MediaOs/4.8 LiveTV",
            }) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_bytes(64 * 1024):
                    yield chunk
        except Exception as e:
            log = __import__("logging").getLogger("mediaos.livetv")
            log.warning("stream proxy failed ch=%s: %s", channel_id, e)
            return

    media = "video/mp2t"
    if url.endswith(".mp4"):
        media = "video/mp4"
    return StreamingResponse(gen(), media_type=media, headers={"Cache-Control": "no-cache"})


@router.get("/jellyfin-setup")
def jellyfin_livetv_setup(request: Request):
    """Instructions + URLs for wiring MediaOs Live TV into Jellyfin."""
    base = str(request.base_url).rstrip("/")
    return {
        "playlist_url": f"{base}/api/livetv/export/playlist.m3u",
        "guide_url": f"{base}/api/livetv/export/guide.xml",
        "steps": [
            "In Jellyfin Dashboard → Live TV → Add tuner → M3U Tuner",
            f"Playlist URL: {base}/api/livetv/export/playlist.m3u",
            "Add guide data provider → XMLTV",
            f"Guide URL: {base}/api/livetv/export/guide.xml",
            "Refresh guide data in Jellyfin after MediaOs EPG sync",
        ],
        "note": "Channel streams are proxied through MediaOs so one auth/network path serves both apps. "
                "Personal-media virtual channels (Settings > Live TV > Virtual Channels) are automatically "
                "included in this same playlist/guide — Jellyfin sees one unified lineup.",
    }



@router.get("/epg/presets")
def epg_presets():
    """iptv-org/epg (epg-grabber) published XMLTV guide presets."""
    from app.services.livetv_defaults import list_epg_presets
    return {
        "presets": list_epg_presets(),
        "docs": "https://github.com/iptv-org/epg",
        "note": "These are XMLTV files produced by epg-grabber / iptv-org grabbers. MediaOs consumes them; it does not scrape sites itself.",
    }


@router.post("/epg/presets/{key}/bind")
def bind_epg_preset(
    key: str,
    source_id: int | None = None,
    db: Session = Depends(get_db),
    _perm: list = Depends(require_permission("library.manage", "settings")),
):
    """Attach an EPG preset URL to a source (or all iptv-org sources)."""
    from app.services.livetv_defaults import _epg_by_key
    from app.models import LiveTvSource

    ep = _epg_by_key(key)
    if not ep:
        raise HTTPException(404, "Unknown EPG preset")
    q = db.query(LiveTvSource)
    if source_id is not None:
        q = q.filter(LiveTvSource.id == source_id)
    updated = 0
    for src in q.all():
        src.epg_url = ep["url"]
        db.add(src)
        updated += 1
    db.commit()
    return {"ok": True, "updated": updated, "epg_url": ep["url"]}


@router.get("/epg/channels")
def epg_channel_list():
    from app.services.livetv import list_epg_channel_ids, _epg_cache
    return {
        "channels": list_epg_channel_ids()[:5000],
        "fetched_at": (_epg_cache or {}).get("fetched_at"),
        "urls": (_epg_cache or {}).get("urls") or [],
    }


@router.get("/channels/{channel_id}/suggest-epg")
def suggest_epg(channel_id: int, db: Session = Depends(get_db)):
    from app.services.livetv import suggest_tvg_match
    ch = db.get(LiveTvChannel, channel_id)
    if not ch:
        raise HTTPException(404, "Not found")
    return {"channel_id": channel_id, "name": ch.name, "suggestions": suggest_tvg_match(ch.name)}


class ChannelPatch(BaseModel):
    enabled: bool | None = None
    tvg_id: str | None = None
    epg_tvg_id: str | None = None
    name: str | None = None
    group_title: str | None = None
    logo: str | None = None
    sort_order: int | None = None


@router.patch("/channels/{channel_id}")
def patch_channel(channel_id: int, payload: ChannelPatch, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "settings"))):
    ch = db.get(LiveTvChannel, channel_id)
    if not ch:
        raise HTTPException(404, "Not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        if hasattr(ch, k):
            setattr(ch, k, v)
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return {
        "id": ch.id,
        "name": ch.name,
        "tvg_id": ch.tvg_id,
        "epg_tvg_id": getattr(ch, "epg_tvg_id", None),
        "enabled": ch.enabled,
        "logo": ch.logo,
        "group_title": ch.group_title,
        "sort_order": getattr(ch, "sort_order", 0) or 0,
    }


@router.post("/health/run")
def run_health(db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage", "settings"))):
    from app.services.livetv import run_channel_health_cycle
    return run_channel_health_cycle(db)


@router.get("/health/status")
def health_status(db: Session = Depends(get_db)):
    from app.models import LiveTvChannel
    from sqlalchemy import func
    total = db.query(LiveTvChannel).count()
    enabled = db.query(LiveTvChannel).filter(LiveTvChannel.enabled.is_(True)).count()
    with_err = db.query(LiveTvChannel).filter(LiveTvChannel.fail_count > 0).count()
    return {"total": total, "enabled": enabled, "with_failures": with_err}


# ── Virtual channels (personal media → 24/7 channels) ───────────────────────

class VirtualChannelCreate(BaseModel):
    number: int
    name: str
    group_title: str | None = "Personal Media"
    logo: str | None = None
    enabled: bool = True
    media_types: list[str] = ["movie"]
    media_item_ids: list[int] | None = None
    genre_filter: str | None = None
    title_filter: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    randomize: bool = True
    repeat_protection_days: int = 7
    prime_time_movies: bool = False


class VirtualChannelUpdate(BaseModel):
    number: int | None = None
    name: str | None = None
    group_title: str | None = None
    logo: str | None = None
    enabled: bool | None = None
    media_types: list[str] | None = None
    media_item_ids: list[int] | None = None
    genre_filter: str | None = None
    title_filter: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    randomize: bool | None = None
    repeat_protection_days: int | None = None
    prime_time_movies: bool | None = None


def _vc_out(ch) -> dict:
    import json as _json
    return {
        "id": ch.id,
        "number": ch.number,
        "name": ch.name,
        "group_title": ch.group_title,
        "logo": ch.logo,
        "enabled": ch.enabled,
        "media_types": _json.loads(ch.media_types or "[]"),
        "media_item_ids": _json.loads(ch.media_item_ids) if ch.media_item_ids else None,
        "genre_filter": ch.genre_filter,
        "title_filter": ch.title_filter,
        "year_min": ch.year_min,
        "year_max": ch.year_max,
        "randomize": ch.randomize,
        "repeat_protection_days": ch.repeat_protection_days,
        "prime_time_movies": ch.prime_time_movies,
        "schedule_filled_until": ch.schedule_filled_until,
        "stream_status": ch.stream_status,
        "stream_error": ch.stream_error,
        "stream_started_at": ch.stream_started_at,
    }


@router.get("/virtual/channels")
def list_virtual_channels(db: Session = Depends(get_db)):
    from app.models import LiveTvVirtualChannel as VC
    rows = db.query(VC).order_by(VC.number).all()
    return [_vc_out(r) for r in rows]


@router.post("/virtual/channels")
def create_virtual_channel(
    payload: VirtualChannelCreate,
    db: Session = Depends(get_db),
    _perm: list = Depends(require_permission("library.manage", "settings")),
):
    import json as _json
    from app.models import LiveTvVirtualChannel as VC

    if db.query(VC).filter(VC.number == payload.number).first():
        raise HTTPException(400, f"Channel number {payload.number} already in use")
    if not payload.media_types:
        raise HTTPException(400, "media_types must include at least one of: movie, tv")

    ch = VC(
        number=payload.number,
        name=payload.name,
        group_title=payload.group_title,
        logo=payload.logo,
        enabled=payload.enabled,
        media_types=_json.dumps(payload.media_types),
        media_item_ids=_json.dumps(payload.media_item_ids) if payload.media_item_ids else None,
        genre_filter=payload.genre_filter,
        title_filter=payload.title_filter,
        year_min=payload.year_min,
        year_max=payload.year_max,
        randomize=payload.randomize,
        repeat_protection_days=payload.repeat_protection_days,
        prime_time_movies=payload.prime_time_movies,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)

    from app.services.virtual_channels import ensure_channel_ready
    try:
        ensure_channel_ready(db, ch)
    except Exception as exc:
        log.warning("initial schedule build failed for new virtual channel %s: %s", ch.id, exc)

    return _vc_out(ch)


@router.patch("/virtual/channels/{channel_id}")
def update_virtual_channel(
    channel_id: int,
    payload: VirtualChannelUpdate,
    db: Session = Depends(get_db),
    _perm: list = Depends(require_permission("library.manage", "settings")),
):
    import json as _json
    from app.models import LiveTvVirtualChannel as VC

    ch = db.get(VC, channel_id)
    if not ch:
        raise HTTPException(404, "Virtual channel not found")

    data = payload.model_dump(exclude_unset=True)
    if "number" in data and data["number"] != ch.number:
        if db.query(VC).filter(VC.number == data["number"], VC.id != channel_id).first():
            raise HTTPException(400, f"Channel number {data['number']} already in use")
    if "media_types" in data:
        data["media_types"] = _json.dumps(data["media_types"] or ["movie"])
    if "media_item_ids" in data:
        data["media_item_ids"] = _json.dumps(data["media_item_ids"]) if data["media_item_ids"] else None

    for k, v in data.items():
        setattr(ch, k, v)
    db.add(ch)
    db.commit()
    db.refresh(ch)

    # Content/filter changes invalidate the existing schedule's premise — the
    # simplest correct fix is to drop unplayed future rows and rebuild.
    filter_keys = {"media_types", "media_item_ids", "genre_filter", "title_filter", "year_min", "year_max"}
    if filter_keys & set(data.keys()):
        from app.models import LiveTvVirtualScheduleItem as SI
        from datetime import datetime, timezone
        db.query(SI).filter(SI.virtual_channel_id == ch.id, SI.start_time > datetime.now(timezone.utc)).delete(synchronize_session=False)
        ch.schedule_filled_until = None
        db.add(ch)
        db.commit()
        from app.services.virtual_channels import ensure_channel_ready
        ensure_channel_ready(db, ch)

    return _vc_out(ch)


@router.delete("/virtual/channels/{channel_id}")
def delete_virtual_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    _perm: list = Depends(require_permission("library.manage", "settings")),
):
    from app.models import LiveTvVirtualChannel as VC, LiveTvVirtualScheduleItem as SI
    from app.services import virtual_stream_engine as engine

    ch = db.get(VC, channel_id)
    if not ch:
        raise HTTPException(404, "Virtual channel not found")
    engine.stop(channel_id)
    db.query(SI).filter(SI.virtual_channel_id == channel_id).delete(synchronize_session=False)
    db.delete(ch)
    db.commit()

    import shutil as _shutil
    from app.services.virtual_channels import channel_data_dir
    _shutil.rmtree(channel_data_dir(channel_id), ignore_errors=True)
    return {"ok": True}


@router.get("/virtual/channels/{channel_id}/schedule")
def virtual_channel_schedule(
    channel_id: int,
    hours: int = 12,
    db: Session = Depends(get_db),
):
    from app.models import LiveTvVirtualScheduleItem as SI
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    rows = (
        db.query(SI)
        .filter(SI.virtual_channel_id == channel_id, SI.start_time >= now - timedelta(hours=1))
        .filter(SI.start_time <= now + timedelta(hours=max(1, hours)))
        .order_by(SI.start_time.asc())
        .all()
    )
    return [
        {
            "title": r.title,
            "start_time": r.start_time,
            "duration_seconds": r.duration_seconds,
            "media_item_id": r.media_item_id,
            "episode_id": r.episode_id,
        }
        for r in rows
    ]


@router.get("/virtual/channels/{channel_id}/now-next")
def virtual_channel_now_next(channel_id: int, db: Session = Depends(get_db)):
    from app.services.virtual_channels import get_now_and_next
    return get_now_and_next(db, channel_id)


@router.post("/virtual/channels/{channel_id}/rebuild")
def rebuild_virtual_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    _perm: list = Depends(require_permission("library.manage", "settings")),
):
    """Force a schedule top-up + stream (re)start right now, instead of waiting
    for the next scheduler tick."""
    from app.models import LiveTvVirtualChannel as VC
    from app.services.virtual_channels import ensure_channel_ready
    from app.services import virtual_stream_engine as engine

    ch = db.get(VC, channel_id)
    if not ch:
        raise HTTPException(404, "Virtual channel not found")
    sched = ensure_channel_ready(db, ch)
    stream = engine.ensure_running(db, ch) if ch.enabled else {"ok": False, "status": "disabled"}
    return {"schedule": sched, "stream": stream}


@router.get("/virtual/stream/{channel_id}/stream.m3u8")
def virtual_channel_hls_playlist(channel_id: int, db: Session = Depends(get_db)):
    """HLS master/media playlist Jellyfin (or any HLS client) polls for a
    virtual channel. Starts the ffmpeg feed on first request if it isn't
    already running, same as tuning in to a real live channel."""
    from fastapi.responses import FileResponse
    from app.models import LiveTvVirtualChannel as VC
    from app.services import virtual_stream_engine as engine

    ch = db.get(VC, channel_id)
    if not ch or not ch.enabled:
        raise HTTPException(404, "Virtual channel not found")
    if not engine.is_running(channel_id):
        engine.ensure_running(db, ch)
    path = engine.hls_playlist_path(channel_id)
    if not path.exists():
        raise HTTPException(503, "Stream is starting — retry in a few seconds")
    return FileResponse(path, media_type="application/vnd.apple.mpegurl", headers={"Cache-Control": "no-cache"})


@router.get("/virtual/stream/{channel_id}/{segment_name}")
def virtual_channel_hls_segment(channel_id: int, segment_name: str):
    from fastapi.responses import FileResponse
    from app.services import virtual_stream_engine as engine

    try:
        path = engine.hls_segment_path(channel_id, segment_name)
    except ValueError:
        raise HTTPException(400, "Invalid segment name")
    if not path.exists():
        raise HTTPException(404, "Segment not found")
    return FileResponse(path, media_type="video/mp2t", headers={"Cache-Control": "no-cache"})


# ── Channel editor (enable / order / logos / groups) ────────────────────────

class ChannelReorderBody(BaseModel):
    """Ordered list of channel ids — position in list = sort_order."""
    channel_ids: list[int]


@router.post("/channels/reorder")
def reorder_channels(
    body: ChannelReorderBody,
    db: Session = Depends(get_db),
    _perm: list = Depends(require_permission("library.manage", "settings")),
):
    """Set sort_order from list order (0..n)."""
    updated = 0
    for idx, cid in enumerate(body.channel_ids[:5000]):
        ch = db.get(LiveTvChannel, cid)
        if ch is None:
            continue
        ch.sort_order = idx
        updated += 1
    db.commit()
    return {"ok": True, "updated": updated}


@router.post("/channels/bulk")
def bulk_channels(
    body: dict,
    db: Session = Depends(get_db),
    _perm: list = Depends(require_permission("library.manage", "settings")),
):
    """
    Bulk enable/disable or set group.
    body: { "channel_ids": [1,2], "enabled": true } or { "channel_ids": [...], "group_title": "Sports" }
    """
    ids = body.get("channel_ids") or []
    if not isinstance(ids, list) or not ids:
        raise HTTPException(400, "channel_ids required")
    enabled = body.get("enabled")
    group_title = body.get("group_title")
    n = 0
    for cid in ids[:5000]:
        ch = db.get(LiveTvChannel, int(cid))
        if not ch:
            continue
        if enabled is not None:
            ch.enabled = bool(enabled)
        if group_title is not None:
            ch.group_title = str(group_title)[:120] or None
        n += 1
    db.commit()
    return {"ok": True, "updated": n}


# ── DVR / click-to-record (Cinephage EPG parity) ─────────────────────────────

class RecordIn(BaseModel):
    channel_id: int | None = None
    title: str
    subtitle: str | None = None
    tvg_id: str | None = None
    starts_at: str | None = None  # ISO
    ends_at: str | None = None
    stream_url: str | None = None


@router.post("/recordings")
def create_recording(body: RecordIn, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    from datetime import datetime
    from app.services.livetv_dvr import schedule_recording

    def _parse(s: str | None):
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    rec = schedule_recording(
        db,
        channel_id=body.channel_id,
        title=body.title,
        subtitle=body.subtitle,
        tvg_id=body.tvg_id,
        starts_at=_parse(body.starts_at),
        ends_at=_parse(body.ends_at),
        stream_url=body.stream_url,
    )
    return {
        "ok": True,
        "id": rec.id,
        "status": rec.status,
        "title": rec.title,
        "starts_at": rec.starts_at.isoformat() if rec.starts_at else None,
        "ends_at": rec.ends_at.isoformat() if rec.ends_at else None,
    }


@router.get("/recordings")
def get_recordings(limit: int = 50, db: Session = Depends(get_db)):
    from app.services.livetv_dvr import list_recordings
    return {"items": list_recordings(db, limit=limit)}


@router.delete("/recordings/{rec_id}")
def delete_recording(rec_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    from app.services.livetv_dvr import cancel_recording
    from app.models import LiveTvRecording
    if cancel_recording(db, rec_id):
        return {"ok": True, "cancelled": True}
    rec = db.get(LiveTvRecording, rec_id)
    if not rec:
        raise HTTPException(404, "Not found")
    db.delete(rec)
    db.commit()
    return {"ok": True, "deleted": True}


@router.post("/epg/record")
def epg_click_record(body: dict, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    """One-shot from EPG grid cell: channel_id + programme title/times."""
    from datetime import datetime
    from app.services.livetv_dvr import schedule_recording

    def _parse(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        except Exception:
            return None

    try:
        rec = schedule_recording(
            db,
            channel_id=body.get("channel_id"),
            title=body.get("title") or body.get("programme") or "EPG Recording",
            subtitle=body.get("subtitle") or body.get("desc"),
            tvg_id=body.get("tvg_id"),
            starts_at=_parse(body.get("starts_at") or body.get("start")),
            ends_at=_parse(body.get("ends_at") or body.get("stop")),
            stream_url=body.get("stream_url"),
            allow_conflict=bool(body.get("allow_conflict")),
        )
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    return {"ok": True, "id": rec.id, "status": rec.status, "title": rec.title}


# ── Series-record rules ──────────────────────────────────────────────────────

@router.get("/series-rules")
def get_series_rules(db: Session = Depends(get_db)):
    from app.services.livetv_dvr import list_series_rules
    return {"items": list_series_rules(db)}


@router.post("/series-rules")
def post_series_rule(body: dict, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    from app.services.livetv_dvr import create_series_rule
    title = (body.get("title_match") or body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title_match required")
    return create_series_rule(
        db,
        title_match=title,
        match_mode=body.get("match_mode") or "contains",
        channel_id=body.get("channel_id"),
        keep_episodes=int(body.get("keep_episodes") or 0),
        priority=int(body.get("priority") or 50),
        only_new=bool(body.get("only_new", True)),
        enabled=bool(body.get("enabled", True)),
    )


@router.delete("/series-rules/{rule_id}")
def remove_series_rule(rule_id: int, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    from app.services.livetv_dvr import delete_series_rule
    if not delete_series_rule(db, rule_id):
        raise HTTPException(404, "Rule not found")
    return {"ok": True}


@router.post("/series-rules/apply")
def apply_series_rules(body: dict, db: Session = Depends(get_db), _perm: list = Depends(require_permission("download", "library.manage"))):
    """Apply enabled series rules to a batch of EPG programme dicts."""
    from app.services.livetv_dvr import apply_series_rules_to_epg
    items = body.get("items") or body.get("programmes") or []
    scheduled = apply_series_rules_to_epg(db, items)
    return {"ok": True, "scheduled": scheduled, "count": len(scheduled)}
