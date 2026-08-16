"""MediaOs overhaul APIs: stream mode, dashboard widgets, comics pull/arcs, trash import, multi-quality, external arr."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_permission, require_admin
from app.database import get_db
from app.models import (
    ExternalArrInstance,
    MediaQualityFile,
    StreamLink,
)

router = APIRouter(prefix="/overhaul", tags=["overhaul"])


# ── Dashboard (Prismarr-inspired) ───────────────────────────────────────────

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: list = Depends(require_permission("library.view", "calendar.view"))):
    from app.services.dashboard_widgets import dashboard_bundle
    return dashboard_bundle(db)


# ── Stream mode (Cinephage-inspired) ────────────────────────────────────────

class StreamIn(BaseModel):
    title: str
    stream_url: str
    media_item_id: int | None = None
    episode_id: int | None = None
    provider: str | None = None


@router.get("/streams")
def list_streams(db: Session = Depends(get_db), _: list = Depends(require_permission("library.view"))):
    from app.services.stream_mode import list_links
    rows = list_links(db)
    return [
        {
            "id": r.id,
            "title": r.title,
            "stream_url": r.stream_url,
            "strm_path": r.strm_path,
            "provider": r.provider,
            "media_item_id": r.media_item_id,
        }
        for r in rows
    ]


@router.post("/streams")
def add_stream(body: StreamIn, db: Session = Depends(get_db), _: list = Depends(require_permission("download"))):
    from app.services.stream_mode import create_stream_link
    row = create_stream_link(
        db,
        title=body.title,
        stream_url=body.stream_url,
        media_item_id=body.media_item_id,
        episode_id=body.episode_id,
        provider=body.provider,
    )
    return {"ok": True, "id": row.id, "strm_path": row.strm_path}


# NOTE (cleanup pass, this session): this router used to duplicate several
# endpoints that already exist as first-class implementations elsewhere:
#   - /epg/grid, /epg/sync            -> use GET/POST /api/livetv/epg/grid,
#                                         /api/livetv/epg/refresh instead
#                                         (livetv.py's /epg/refresh has proper
#                                         error handling; this one didn't)
#   - /music/incomplete,
#     /music/albums/{id}/completeness -> use /api/music/incomplete and the
#                                         equivalent in music.py instead
#   - /comics/pull-list (+ /sync),
#     /comics/story-arcs              -> use /api/comics/pull (+ /pull/sync)
#                                         and /api/comics/arcs instead —
#                                         comics.py's version also supports
#                                         PATCH on pull items, which this
#                                         router's copy never implemented.
# All of the above were removed here after confirming (by grepping the
# frontend) that nothing still calls the /api/overhaul/* paths for them.
# See todo.md for the session note.


# ── TRaSH import (Recyclarr-inspired) ───────────────────────────────────────

@router.post("/trash/import")
def trash_import(payload: dict, _: str = Depends(require_admin)):
    from app.services.trash_import import import_trash_payload
    return import_trash_payload(payload)


# ── Multi-quality files (Bobarr-inspired) ───────────────────────────────────

class QualityFileIn(BaseModel):
    media_item_id: int
    episode_id: int | None = None
    quality_label: str
    file_path: str
    size_bytes: int | None = None
    score: int | None = None
    is_primary: bool = False


@router.get("/quality-files/{media_item_id}")
def quality_files(media_item_id: int, db: Session = Depends(get_db),
                  _: list = Depends(require_permission("library.view"))):
    rows = db.query(MediaQualityFile).filter(MediaQualityFile.media_item_id == media_item_id).all()
    return [
        {
            "id": r.id,
            "quality_label": r.quality_label,
            "file_path": r.file_path,
            "size_bytes": r.size_bytes,
            "score": r.score,
            "is_primary": r.is_primary,
        }
        for r in rows
    ]


@router.post("/quality-files")
def quality_files_add(body: QualityFileIn, db: Session = Depends(get_db),
                      _: list = Depends(require_permission("library.edit"))):
    if body.is_primary:
        db.query(MediaQualityFile).filter(MediaQualityFile.media_item_id == body.media_item_id).update({"is_primary": False})
    row = MediaQualityFile(
        media_item_id=body.media_item_id,
        episode_id=body.episode_id,
        quality_label=body.quality_label,
        file_path=body.file_path,
        size_bytes=body.size_bytes,
        score=body.score,
        is_primary=body.is_primary,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


# ── External *arr instances (Prismarr-inspired) ─────────────────────────────

class ArrInstanceIn(BaseModel):
    name: str
    kind: str  # sonarr|radarr|lidarr
    base_url: str
    api_key: str
    enabled: bool = True


@router.get("/arr-instances")
def arr_instances(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    rows = db.query(ExternalArrInstance).all()
    return [
        {"id": r.id, "name": r.name, "kind": r.kind, "base_url": r.base_url, "enabled": r.enabled}
        for r in rows
    ]


@router.post("/arr-instances")
def arr_instances_add(body: ArrInstanceIn, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    row = ExternalArrInstance(
        name=body.name,
        kind=body.kind.lower(),
        base_url=body.base_url.rstrip("/"),
        api_key=body.api_key,
        enabled=body.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


@router.get("/arr-instances/{instance_id}/calendar")
def arr_instance_calendar(instance_id: int, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    """Proxy calendar from external Sonarr/Radarr (best-effort)."""
    import httpx
    row = db.get(ExternalArrInstance, instance_id)
    if not row or not row.enabled:
        raise HTTPException(404, "Instance not found")
    url = f"{row.base_url}/api/v3/calendar"
    try:
        r = httpx.get(url, headers={"X-Api-Key": row.api_key}, timeout=20, follow_redirects=True)
        r.raise_for_status()
        return {"instance": row.name, "kind": row.kind, "events": r.json()}
    except Exception as e:
        raise HTTPException(502, f"Upstream failed: {e}")


@router.post("/trash/fetch")
def trash_fetch_now(url: str | None = None, _: str = Depends(require_admin)):
    from app.services.trash_guide_fetch import fetch_and_apply
    return fetch_and_apply(url=url)


@router.get("/livetv/now-next")
def livetv_now_next(tvg_id: str | None = None, db: Session = Depends(get_db),
                    _: list = Depends(require_permission("library.view"))):
    from app.services.livetv import now_next_for_tvg, channel_lineup
    if tvg_id:
        return now_next_for_tvg(tvg_id)
    return channel_lineup(db)


@router.get("/external-arr")
def list_external_arr(db: Session = Depends(get_db), _: list = Depends(require_permission("library.view"))):
    rows = db.query(ExternalArrInstance).order_by(ExternalArrInstance.name).all()
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "kind": r.kind,
                "base_url": r.base_url,
                "enabled": r.enabled,
            }
            for r in rows
        ]
    }


@router.post("/external-arr")
def add_external_arr(body: dict, db: Session = Depends(get_db), _: list = Depends(require_permission("settings"))):
    row = ExternalArrInstance(
        name=body.get("name") or "arr",
        kind=body.get("kind") or "sonarr",
        base_url=body.get("base_url") or "",
        api_key=body.get("api_key") or "",
        enabled=bool(body.get("enabled", True)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


@router.get("/widget-layout")
def get_widget_layout(db: Session = Depends(get_db)):
    from app.models import AppSetting
    row = db.query(AppSetting).filter(AppSetting.key == "dashboard_widget_layout").first()
    if not row:
        return {"layout": ["activity", "queue", "calendar", "continue_watching", "wanted", "health"]}
    import json
    try:
        return {"layout": json.loads(row.value)}
    except Exception:
        return {"layout": []}


@router.put("/widget-layout")
def set_widget_layout(body: dict, db: Session = Depends(get_db), _: list = Depends(require_permission("settings"))):
    from app.models import AppSetting
    import json
    layout = body.get("layout") or []
    row = db.query(AppSetting).filter(AppSetting.key == "dashboard_widget_layout").first()
    if not row:
        row = AppSetting(key="dashboard_widget_layout", value=json.dumps(layout))
        db.add(row)
    else:
        row.value = json.dumps(layout)
    db.commit()
    return {"ok": True, "layout": layout}


@router.get("/external-arr/{instance_id}/status")
def external_arr_status(instance_id: int, db: Session = Depends(get_db), _: list = Depends(require_permission("library.view"))):
    """Live queue + calendar snapshot from remote Sonarr/Radarr/Lidarr."""
    import requests
    row = db.get(ExternalArrInstance, instance_id)
    if not row or not row.enabled:
        raise HTTPException(404, "Instance not found or disabled")
    base = (row.base_url or "").rstrip("/")
    headers = {"X-Api-Key": row.api_key}
    out = {"id": row.id, "name": row.name, "kind": row.kind, "ok": False, "queue": [], "calendar": [], "error": None}
    try:
        # Queue
        qpath = "/api/v3/queue" if row.kind in ("sonarr", "radarr", "lidarr") else "/api/queue"
        qr = requests.get(f"{base}{qpath}", headers=headers, params={"pageSize": 20}, timeout=12)
        if qr.ok:
            data = qr.json()
            records = data.get("records") if isinstance(data, dict) else data
            out["queue"] = [
                {
                    "title": r.get("title") or r.get("sourceTitle") or r.get("series", {}).get("title"),
                    "status": r.get("status"),
                    "tracked": r.get("trackedDownloadStatus"),
                    "sizeleft": r.get("sizeleft"),
                }
                for r in (records or [])[:20]
            ]
        # Calendar (sonarr/radarr)
        if row.kind in ("sonarr", "radarr"):
            from datetime import datetime, timedelta, timezone
            start = datetime.now(timezone.utc).date().isoformat()
            end = (datetime.now(timezone.utc).date() + timedelta(days=14)).isoformat()
            cr = requests.get(
                f"{base}/api/v3/calendar",
                headers=headers,
                params={"start": start, "end": end, "unmonitored": "false"},
                timeout=12,
            )
            if cr.ok:
                cal = cr.json() or []
                out["calendar"] = [
                    {
                        "title": c.get("title") or (c.get("series") or {}).get("title"),
                        "airDate": c.get("airDateUtc") or c.get("airDate") or c.get("inCinemas"),
                        "hasFile": c.get("hasFile"),
                    }
                    for c in cal[:30]
                ]
        # System status ping
        sr = requests.get(f"{base}/api/v3/system/status", headers=headers, timeout=8)
        out["ok"] = sr.ok or bool(out["queue"]) or bool(out["calendar"])
        if sr.ok:
            st = sr.json()
            out["version"] = st.get("version")
            out["appName"] = st.get("appName")
    except Exception as e:
        out["error"] = str(e)
    return out


@router.get("/external-arr/status-all")
def external_arr_status_all(db: Session = Depends(get_db), _: list = Depends(require_permission("library.view"))):
    rows = db.query(ExternalArrInstance).filter(ExternalArrInstance.enabled == True).all()
    results = []
    for r in rows:
        try:
            results.append(external_arr_status(r.id, db, _))
        except Exception as e:
            results.append({"id": r.id, "name": r.name, "ok": False, "error": str(e)})
    return {"items": results}
