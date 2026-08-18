"""Integrations: jdupes, cross-seed status, unpack settings."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.config import settings
from app.database import get_db
from app.services.jdupes import scan_duplicates
from app.services.crossseed import notify_cross_seed

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/integrations")
def integrations_status():
    return {
        "jellyseerr": {
            "radarr_host": "mediaos base URL (same as Sonarr host)",
            "sonarr_host": "mediaos base URL",
            "api_key_env": "ARR_API_KEY or AUTH_API_KEY",
            "endpoints": [
                "POST /api/v3/movie",
                "POST /api/v3/series",
                "GET /api/v3/movie/lookup",
                "GET /api/v3/series/lookup",
                "GET /api/v3/qualityprofile",
                "GET /api/v3/rootfolder",
                "GET /api/v3/languageprofile",
            ],
            "note": "In Jellyseerr Settings → Services, add Radarr + Sonarr both pointing at mediaos",
        },
        "lunasea": {
            "arr_api": "/api/v3/*",
            "api_key_env": "ARR_API_KEY or AUTH_API_KEY",
            "note": "Point LunaSea Sonarr/Radarr host at mediaos; partial v3 shim",
        },
        "cross_seed": {
            "configured": bool(settings.cross_seed_url),
            "url": settings.cross_seed_url or None,
            "notifies_on": "movie/episode organize",
        },
        "unpack": {
            "enabled": settings.unpack_enabled,
            "delete_archive": settings.unpack_delete_archive,
            "formats": ["zip", "rar", "7z", "tar"],
        },
        "jdupes": {
            "enabled": settings.jdupes_enabled,
            "binary": settings.jdupes_path,
            "hardlink_mode": settings.jdupes_hardlink,
        },
    }


class JdupesIn(BaseModel):
    paths: list[str] | None = None
    apply_hardlinks: bool = False


@router.post("/jdupes/scan")
def jdupes_scan(payload: JdupesIn, _: str = Depends(require_permission("settings"))):
    paths = payload.paths or [
        settings.movies_library_path,
        settings.tv_library_path,
        settings.music_library_path,
    ]
    return scan_duplicates(paths, apply_hardlinks=payload.apply_hardlinks)


@router.post("/cross-seed/notify")
def cross_seed_manual(info_hash: str | None = None, path: str | None = None, _: str = Depends(require_permission("settings"))):
    ok = notify_cross_seed(info_hash=info_hash, path=path)
    return {"ok": ok}


@router.get("/library-watch")
def library_watch_status():
    from app.services.library_watch import status, poll_once
    return {**status(), "poll": poll_once()}


@router.get("/cleanup/status")
def cleanup_status():
    return {
        "enabled": bool(getattr(settings, "cleanup_enabled", True)),
        "max_strikes": int(getattr(settings, "cleanup_max_strikes", 3) or 3),
        "stall_minutes": int(getattr(settings, "cleanup_stall_minutes", 30) or 30),
        "min_speed_kb": float(getattr(settings, "cleanup_min_speed_kb", 20) or 20),
        "auto_search": bool(getattr(settings, "cleanup_auto_search", True)),
        "orphans": bool(getattr(settings, "cleanup_orphans", True)),
        "orphans_delete": bool(getattr(settings, "cleanup_orphans_delete", False)),
        "interval_minutes": int(getattr(settings, "cleanup_interval_minutes", 5) or 5),
        "seed_enabled": bool(getattr(settings, "cleanup_seed_enabled", True)),
        "seed_ratio": float(getattr(settings, "cleanup_seed_ratio", 2.0) or 2.0),
        "seed_minutes": int(getattr(settings, "cleanup_seed_minutes", 10080) or 10080),
        "seed_require_both": bool(getattr(settings, "cleanup_seed_require_both", False)),
        "skip_private": bool(getattr(settings, "cleanup_skip_private", True)),
        "inspired_by": "https://github.com/Cleanuparr/Cleanuparr",
    }


@router.post("/cleanup/run")
def cleanup_run(_: str = Depends(require_permission("settings"))):
    """Run one Cleanuparr-style queue + orphan cleaner tick."""
    from app.database import SessionLocal
    from app.services.cleanup import run_cleanup_cycle

    db = SessionLocal()
    try:
        return run_cleanup_cycle(db)
    finally:
        db.close()


@router.post("/cleanup/queue")
def cleanup_queue_only(_: str = Depends(require_permission("settings"))):
    from app.database import SessionLocal
    from app.services.cleanup import run_queue_cleaner

    db = SessionLocal()
    try:
        return run_queue_cleaner(db)
    finally:
        db.close()


@router.get("/download-clients")
def download_clients_status():
    from app.services.download_clients import list_clients, active_torrent_client_id
    return {"active": active_torrent_client_id(), "clients": list_clients()}


@router.get("/wanted-subtitles")
def wanted_subtitles(limit: int = 100, db: Session = Depends(get_db)):
    from app.services.subtitles import list_wanted_subtitles
    return list_wanted_subtitles(db, limit=limit)


@router.get("/subtitle-providers")
def subtitle_providers_status():
    from app.services.subtitles import provider_status
    return provider_status()


@router.get("/subtitle-profiles")
def subtitle_language_profiles():
    from app.services.subtitle_profiles import list_profiles, get_default_profile_id, resolve_languages
    return {
        "profiles": list_profiles(),
        "default_profile_id": get_default_profile_id(),
        "active": resolve_languages(),
    }


@router.put("/subtitle-profiles/default")
def set_subtitle_default_profile(body: dict):
    from app.services.subtitle_profiles import set_default_profile_id, resolve_languages, get_profile
    pid = int(body.get("profile_id") or body.get("id") or 1)
    get_profile(pid)  # validate exists
    set_default_profile_id(pid)
    return {"ok": True, "active": resolve_languages(pid)}

@router.post("/clients/apply")
def clients_apply(body: dict, _=Depends(require_permission("settings"))):
    """One-shot qB/SAB category + path Apply."""
    from app.services.client_apply import apply_clients
    return apply_clients(
        qbit_url=body.get("qbit_url"),
        qbit_user=body.get("qbit_user") or body.get("qbit_username"),
        qbit_pass=body.get("qbit_pass") or body.get("qbit_password"),
        sab_url=body.get("sab_url") or body.get("sabnzbd_url"),
        sab_api_key=body.get("sab_api_key") or body.get("sabnzbd_api_key"),
        categories=body.get("categories"),
        push_qb_categories=bool(body.get("push_qb_categories", True)),
    )


@router.get("/clients/plan")
def clients_plan(_=Depends(require_permission("settings"))):
    from app.services.client_apply import planned_categories
    from app.services.settings_help import CLIENT_HELP
    return {"categories": planned_categories(), "help": CLIENT_HELP}


@router.get("/settings-help")
def settings_help_all(_=Depends(require_permission("settings"))):
    from app.services.settings_help import PATH_HELP, CLIENT_HELP, QUALITY_HELP, FIELD_HELP
    return {"paths": PATH_HELP, "clients": CLIENT_HELP, "quality": QUALITY_HELP, "fields": FIELD_HELP}
