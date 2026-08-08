from datetime import datetime

from app.auth import require_permission
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LiveTvChannel, LiveTvSource
from app.services.livetv import sync_source

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
    return query.order_by(LiveTvChannel.group_title, LiveTvChannel.name).limit(limit).all()


@router.get("/groups")
def list_groups(source_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(LiveTvChannel.group_title).filter(LiveTvChannel.enabled.is_(True))
    if source_id is not None:
        query = query.filter(LiveTvChannel.source_id == source_id)
    rows = query.distinct().all()
    return sorted({r[0] or "Other" for r in rows})


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
    from app.services.livetv import fetch_and_index_epg, now_next_for_tvg, _epg_cache
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
            nn = now_next_for_tvg(ch.tvg_id)
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
