"""First-run setup wizard — multi-step, extensible."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.auth import require_permission
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/setup", tags=["setup"])

FLAG = Path(os.environ.get("MEDIAOS_DATA", "/config")) / ".setup_complete"
_LOCAL = Path("data") / ".setup_complete"


def _flag_paths() -> list[Path]:
    return [FLAG, _LOCAL, Path("/tmp/mediaos_setup_complete")]


def is_setup_complete() -> bool:
    return any(p.exists() for p in _flag_paths())


def mark_complete() -> None:
    for p in _flag_paths():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("ok\n", encoding="utf-8")
            return
        except Exception:
            continue


# Fields the wizard may write (key → settings attribute). Extra keys ignored.
WIZARD_FIELDS: dict[str, type] = {
    # metadata
    "tmdb_api_key": str,
    "tvdb_api_key": str,
    "tvdb_pin": str,
    "comicvine_api_key": str,
    "trakt_client_id": str,
    "trakt_access_token": str,
    # library paths
    "movies_library_path": str,
    "adult_library_path": str,
    "tv_library_path": str,
    "music_library_path": str,
    "books_library_path": str,
    "audiobooks_library_path": str,
    "podcasts_library_path": str,
    "comics_library_path": str,
    "manga_library_path": str,
    "youtube_library_path": str,
    "downloads_path": str,
    "movie_naming_folder": str,
    "episode_naming": str,
    # download clients
    "qbit_url": str,
    "qbit_username": str,
    "qbit_password": str,
    "sabnzbd_url": str,
    "sabnzbd_api_key": str,
    "sabnzbd_category": str,
    "nzbget_url": str,
    "nzbget_username": str,
    "nzbget_password": str,
    "nzbget_category": str,
    "torrent_client": str,
    "transmission_url": str,
    "transmission_username": str,
    "transmission_password": str,
    "deluge_url": str,
    "deluge_password": str,
    "rtorrent_url": str,
    "aria2_url": str,
    "aria2_secret": str,
    "usenet_client": str,
    "allow_usenet": bool,
    # indexers
    "prowlarr_url": str,
    "prowlarr_api_key": str,
    "jackett_url": str,
    "jackett_api_key": str,
    "cardigann_enabled": bool,
    "cardigann_definitions_path": str,
    "cardigann_auto_sync": bool,
    "cardigann_auto_sync_on_startup": bool,
    "min_seeders": int,
    "jackett_sync_on_startup": bool,
    "flaresolverr_url": str,
    "cf_bypass_enabled": bool,
    "cf_impersonate": str,
    # subtitles
    "opensubtitles_api_key": str,
    "opensubtitles_username": str,
    "opensubtitles_password": str,
    "subtitle_languages": str,
    "subtitle_hearing_impaired": str,
    "subtitle_providers": str,
    "subdl_api_key": str,
    # cleanup
    "cleanup_enabled": bool,
    "cleanup_max_strikes": int,
    "cleanup_auto_search": bool,
    # usenet / nntp
    "nntp_host": str,
    "nntp_port": int,
    "nntp_user": str,
    "nntp_pass": str,
    "nntp_ssl": bool,
    # vpn
    "vpn_enabled": bool,
    "vpn_provider": str,
    "vpn_username": str,
    "vpn_password": str,
    "vpn_kill_switch": bool,
    "vpn_port_forwarding": bool,
    "vpn_server_countries": str,
    "vpn_wireguard_private_key": str,
    "vpn_opvn_password": str,
    "vpn_opvn_user": str,
    "vpn_service_provider": str,
    "vpn_killswitch": bool,
    "vpn_interface": str,
    "vpn_gluetun_url": str,
    "vpn_expected_country": str,
    # youtube
    "youtube_library_path": str,
    "youtube_ytdlp_path": str,
    "youtube_format": str,
    "youtube_auto_download_default": bool,
    "youtube_cookies_path": str,
    "youtube_cookies_from_browser": str,
    "youtube_sponsorblock_remove": str,
    "youtube_sponsorblock_mark": str,
    "youtube_backlog_download": bool,
    # debrid
    "real_debrid_token": str,
    "torbox_api_key": str,
    "alldebrid_api_key": str,
    "premiumize_api_key": str,
    "debridlink_api_key": str,
    "putio_token": str,
    "easydebrid_api_key": str,
    "offcloud_api_key": str,
    "movie_download_mode": str,
    # media servers + notifications
    "jellyfin_url": str,
    "jellyfin_api_key": str,
    "emby_url": str,
    "emby_api_key": str,
    "apprise_url": str,
    "discord_webhook_url": str,
    "telegram_bot_token": str,
    "telegram_chat_id": str,
    # auth
    "auth_username": str,
    "auth_password": str,
    "auth_api_key": str,
    "arr_api_key": str,
}



class SetupStatus(BaseModel):
    complete: bool
    has_tmdb: bool
    has_tvdb: bool
    has_qbit: bool
    has_indexer: bool
    has_nntp: bool
    has_vpn: bool
    has_jellyfin: bool
    movies_path_ok: bool
    tv_path_ok: bool
    steps: list[str]
    wizard_steps: list[dict[str, Any]]


class SetupPayload(BaseModel):
    """Accept any wizard field; unknown keys ignored. mark_complete finishes onboarding."""
    mark_complete: bool = True
    # allow arbitrary extra via model_extra
    model_config = {"extra": "allow"}



def _set_enabled_modules(db: Session, modules: list[str]) -> None:
    from app.models import AppSetting
    import json
    mods = list(dict.fromkeys(["movies", "tv"] + [m for m in modules if m]))
    row = db.query(AppSetting).filter(AppSetting.key == "enabled_modules").first()
    if not row:
        row = AppSetting(key="enabled_modules", value=json.dumps(mods))
    else:
        row.value = json.dumps(mods)
    db.add(row)
    db.commit()


def _ensure_admin_user(db: Session, username: str, password: str, role: str = "admin") -> str | None:
    """Create or update admin from wizard. Returns action note."""
    from app.models import User
    from app.auth import hash_password
    username = (username or "").strip()
    password = (password or "").strip()
    if not username or not password:
        return None
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        existing.password_hash = hash_password(password)
        existing.role = role or existing.role or "admin"
        db.add(existing)
        db.commit()
        return f"updated user {username}"
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role or "admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return f"created user {username}"


def _set_adult_passcode(db: Session, code: str) -> str | None:
    code = (code or "").strip()
    if not code:
        return None
    if not (code.isdigit() and len(code) == 5):
        raise HTTPException(400, "Adult passcode must be exactly 5 digits")
    from app.models import AppSetting
    from app.services import adult_gate
    h = adult_gate.set_passcode(code)
    row = db.query(AppSetting).filter(AppSetting.key == "adult_passcode_hash").first()
    if not row:
        row = AppSetting(key="adult_passcode_hash", value=h)
    else:
        row.value = h
    db.add(row)
    db.commit()
    return "adult passcode set"


def _create_extra_users(db: Session, users: list) -> list[str]:
    from app.models import User
    from app.auth import hash_password
    notes = []
    for u in users or []:
        if not isinstance(u, dict):
            continue
        un = (u.get("username") or "").strip()
        pw = (u.get("password") or "").strip()
        role = (u.get("role") or "user").strip() or "user"
        if not un or not pw:
            continue
        if db.query(User).filter(User.username == un).first():
            notes.append(f"skip existing {un}")
            continue
        db.add(User(username=un, password_hash=hash_password(pw), role=role, is_active=True))
        notes.append(f"created {un}")
    if notes:
        db.commit()
    return notes


def _apply_payload(db: Session, data: dict[str, Any]) -> list[str]:
    """Write non-empty values into settings + AppSetting rows. Returns applied keys."""
    from app.models import AppSetting
    import json

    applied: list[str] = []
    for key, type_ in WIZARD_FIELDS.items():
        if key not in data:
            continue
        raw = data[key]
        if raw is None or raw == "" or raw == "__SET__":
            continue
        if type_ is bool:
            value = raw if isinstance(raw, bool) else str(raw).lower() in ("1", "true", "yes", "on")
        elif type_ is int:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                continue
        else:
            value = str(raw)
        try:
            setattr(settings, key, value)
        except Exception:
            pass
        try:
            row = db.get(AppSetting, key)
            if row is None:
                db.add(AppSetting(key=key, value=json.dumps(value)))
            else:
                row.value = json.dumps(value)
            applied.append(key)
        except Exception:
            applied.append(key)  # settings singleton still updated
    try:
        db.commit()
    except Exception:
        db.rollback()
    
    # Modules (movies+tv mandatory)
    mods = data.get("enabled_modules") or data.get("modules")
    if isinstance(mods, str):
        mods = [x.strip() for x in mods.split(",") if x.strip()]
    if isinstance(mods, list) and mods:
        _set_enabled_modules(db, mods)
        applied.append("enabled_modules")

    # Admin account
    admin_user = data.get("auth_username") or data.get("admin_username")
    admin_pass = data.get("auth_password") or data.get("admin_password")
    admin_role = data.get("admin_role") or "admin"
    note = _ensure_admin_user(db, admin_user or "", admin_pass or "", role=str(admin_role))
    if note:
        applied.append(note)

    # Extra users [{username,password,role}]
    extra = data.get("extra_users") or data.get("users") or []
    for n in _create_extra_users(db, extra):
        applied.append(n)

    # Adult 5-digit passcode
    if data.get("adult_passcode") or data.get("adult_pin"):
        try:
            n = _set_adult_passcode(db, data.get("adult_passcode") or data.get("adult_pin"))
            if n:
                applied.append(n)
        except HTTPException:
            raise
        except Exception as e:
            applied.append(f"adult_passcode_error:{e}")

    # Sensible defaults for all-in-one (automatic APIs / nodes)
    defaults_on = {
        "cardigann_enabled": True,
        "cardigann_auto_sync": True,
        "cardigann_auto_sync_on_startup": True,
        "livetv_seed_iptv_org": True,
        "livetv_auto_grab": True,
        "cf_bypass_enabled": True,
        "cleanup_enabled": True,
    }
    if data.get("auto_defaults", True):
        for k, v in defaults_on.items():
            if k not in data:
                try:
                    if hasattr(settings, k):
                        setattr(settings, k, v)
                        applied.append(k)
                except Exception:
                    pass

    return applied


@router.get("/status", response_model=SetupStatus)
def setup_status(db: Session = Depends(get_db)):
    steps: list[str] = []
    has_tmdb = bool(getattr(settings, "tmdb_api_key", ""))
    has_tvdb = bool(getattr(settings, "tvdb_api_key", ""))
    has_qbit = bool(getattr(settings, "qbit_url", ""))
    has_indexer = bool(getattr(settings, "prowlarr_url", "") and getattr(settings, "prowlarr_api_key", ""))
    has_nntp = bool(getattr(settings, "nntp_host", ""))
    has_vpn = bool(getattr(settings, "vpn_provider", "") or getattr(settings, "vpn_username", ""))
    has_jellyfin = bool(getattr(settings, "jellyfin_url", ""))
    try:
        from app.models import Indexer
        if db.query(Indexer).filter(Indexer.enabled.is_(True)).count() > 0:
            has_indexer = True
    except Exception:
        pass
    movies_ok = os.path.isdir(getattr(settings, "movies_library_path", "") or "")
    tv_ok = os.path.isdir(getattr(settings, "tv_library_path", "") or "")
    if not has_tmdb:
        steps.append("Add TMDb API key")
    if not has_qbit:
        steps.append("Configure qBittorrent (or SABnzbd)")
    if not has_indexer:
        steps.append("Builtin indexers work out of the box — optional: Prowlarr / Torznab")
    if not movies_ok:
        steps.append("Set / mount movies library path")
    if not tv_ok:
        steps.append("Set / mount TV library path")

    wizard_steps = [
        {"id": "welcome", "title": "Welcome", "required": False},
        {"id": "metadata", "title": "Metadata keys", "required": True},
        {"id": "library", "title": "Library & download paths", "required": True},
        {"id": "downloads", "title": "Download clients", "required": False},
        {"id": "indexers", "title": "Indexers", "required": False},
        {"id": "subtitles", "title": "Subtitles login", "required": False},
        {"id": "usenet", "title": "Usenet / NNTP", "required": False},
        {"id": "vpn", "title": "VPN", "required": False},
        {"id": "youtube", "title": "YouTube login", "required": False},
        {"id": "integrations", "title": "Debrid, servers & notifications", "required": False},
        {"id": "admin", "title": "Admin account", "required": False},
        {"id": "finish", "title": "Finish", "required": False},
    ]
    return SetupStatus(
        complete=is_setup_complete(),
        has_tmdb=has_tmdb,
        has_tvdb=has_tvdb,
        has_qbit=has_qbit,
        has_indexer=has_indexer,
        has_nntp=has_nntp,
        has_vpn=has_vpn,
        has_jellyfin=has_jellyfin,
        movies_path_ok=movies_ok,
        tv_path_ok=tv_ok,
        steps=steps,
        wizard_steps=wizard_steps,
    )


@router.get("/schema")
def setup_schema():
    """Machine-readable wizard field list for future UI extensions."""
    return {
        "fields": [
            {"key": k, "type": t.__name__, "secret": any(x in k for x in ("pass", "token", "key", "secret"))}
            for k, t in WIZARD_FIELDS.items()
        ],
        "steps": [
            "welcome", "metadata", "library", "downloads", "indexers",
            "subtitles", "usenet", "vpn", "youtube", "integrations", "admin", "finish",
        ],
    }




@router.get("/defaults")
def setup_defaults():
    """Current values for wizard prefill (secrets masked if set)."""
    out = {}
    for key, type_ in WIZARD_FIELDS.items():
        try:
            val = getattr(settings, key, None)
        except Exception:
            val = None
        if val is None or val == "":
            out[key] = "" if type_ is str else (False if type_ is bool else (0 if type_ is int else ""))
            continue
        secret = any(x in key for x in ("pass", "token", "key", "secret", "webhook"))
        if secret and str(val):
            out[key] = "__SET__"  # UI keeps existing unless user types new value
        else:
            out[key] = val
    return out


@router.post("/check-paths")
def check_paths(payload: dict[str, Any]):
    """Verify library/download paths exist and are writable."""
    keys = [
        "movies_library_path", "tv_library_path", "music_library_path",
        "books_library_path", "audiobooks_library_path", "podcasts_library_path",
        "comics_library_path", "manga_library_path", "youtube_library_path",
        "downloads_path",
    ]
    results = []
    for k in keys:
        p = (payload.get(k) or getattr(settings, k, "") or "").strip()
        if not p:
            results.append({"key": k, "path": p, "exists": False, "writable": False, "note": "empty"})
            continue
        path = Path(p)
        exists = path.exists()
        writable = False
        note = ""
        try:
            if not exists:
                path.mkdir(parents=True, exist_ok=True)
                exists = path.exists()
                note = "created"
            if exists:
                test = path / ".mediaos_write_test"
                try:
                    test.write_text("ok", encoding="utf-8")
                    test.unlink(missing_ok=True)
                    writable = True
                except Exception as e:
                    note = str(e)[:80]
        except Exception as e:
            note = str(e)[:80]
        results.append({"key": k, "path": p, "exists": exists, "writable": writable, "note": note})
    return {"results": results}






@router.get("/indexers/guidance")
def setup_indexer_guidance():
    """Wizard help: public vs private trackers and recommended path."""
    return {
        "recommended": "prowlarr",
        "public": {
            "path": "builtin + Cardigann YAML (definitions/)",
            "notes": "Works out of the box. Sync Jackett only if you already run it.",
        },
        "private": {
            "path": "Prowlarr → Torznab import in this wizard",
            "notes": (
                "Add private trackers in Prowlarr (with FlareSolverr if needed), "
                "then import selected indexers here. MediaOs does not store tracker cookies itself."
            ),
        },
        "flaresolverr": {
            "for_mediaos": "Optional — improves Subscene/Addic7ed HTML subtitle scrapes",
            "for_prowlarr": "Configure in Prowlarr Settings → Indexers → FlareSolverr for CF sites",
            "compose": "Use docker-compose.integrations.example.yml or add the flaresolverr service",
        },
        "steps": [
            "1. Run Prowlarr on the same Docker network",
            "2. Add public + private indexers in Prowlarr (test each)",
            "3. Paste Prowlarr URL + API key in this wizard",
            "4. Pick indexers (or Import all) — private ones show a lock badge",
            "5. Finish setup — MediaOs searches via Torznab",
        ],
    }

@router.get("/prowlarr/indexers")
def setup_list_prowlarr_indexers(
    url: str | None = None,
    api_key: str | None = None,
):
    """List indexers from Prowlarr for the setup wizard picker.

    Uses query params or falls back to saved settings so the wizard can
    preview before Finish.
    """
    from app.config import settings
    import httpx
    base = (url or getattr(settings, "prowlarr_url", "") or "").rstrip("/")
    key = (api_key or getattr(settings, "prowlarr_api_key", "") or "").strip()
    if not base or not key:
        return {"ok": False, "error": "Set Prowlarr URL and API key first", "indexers": []}
    try:
        with httpx.Client(
            base_url=base,
            headers={"X-Api-Key": key},
            timeout=20.0,
        ) as client:
            r = client.get("/api/v1/indexer")
            r.raise_for_status()
            rows = r.json()
    except Exception as e:
        return {"ok": False, "error": str(e), "indexers": []}
    out = []
    for ix in rows:
        impl = (ix.get("implementationName") or ix.get("implementation") or ix.get("configContract") or "")
        name = ix.get("name") or ""
        # Heuristic: Prowlarr marks privacy on some defs; also common private tracker keywords
        privacy = (ix.get("privacy") or "").lower()
        blob = f"{name} {impl} {privacy}".lower()
        is_private = privacy in ("private", "semi-private") or any(
            k in blob for k in ("private", "vip", "scene", "ratio", "passkey")
        )
        out.append({
            "id": ix.get("id"),
            "name": name,
            "protocol": (ix.get("protocol") or "torrent").lower(),
            "enable": bool(ix.get("enable", True)),
            "priority": ix.get("priority"),
            "supportsRss": ix.get("supportsRss"),
            "supportsSearch": ix.get("supportsSearch"),
            "fields_summary": impl,
            "privacy": privacy or ("private" if is_private else "public"),
            "is_private": is_private,
        })
    private_n = sum(1 for x in out if x.get("is_private"))
    return {
        "ok": True,
        "url": base,
        "count": len(out),
        "private_count": private_n,
        "public_count": len(out) - private_n,
        "indexers": out,
        "guidance": (
            "Private trackers: import via Prowlarr Torznab (recommended). "
            "Cardigann/builtin defs cover many public indexers only. "
            "Enable FlareSolverr in Prowlarr for CF-protected sites."
        ),
    }


class ProwlarrPickPayload(BaseModel):
    url: str | None = None
    api_key: str | None = None
    indexer_ids: list[int] = []
    enable_all: bool = False


@router.post("/prowlarr/import")
def setup_import_prowlarr_indexers(payload: ProwlarrPickPayload, db: Session = Depends(get_db)):
    """Import selected (or all enabled) Prowlarr indexers into MediaOs Torznab rows."""
    from app.config import settings
    from app.services.arr_migrator import sync_prowlarr_indexers
    base = (payload.url or getattr(settings, "prowlarr_url", "") or "").rstrip("/")
    key = (payload.api_key or getattr(settings, "prowlarr_api_key", "") or "").strip()
    if not base or not key:
        raise HTTPException(400, "Prowlarr URL and API key required")
    # Persist credentials if provided in wizard
    if payload.url:
        settings.prowlarr_url = payload.url
    if payload.api_key:
        settings.prowlarr_api_key = payload.api_key
    ids = None if payload.enable_all else (payload.indexer_ids or None)
    result = sync_prowlarr_indexers(
        db, url=base, api_key=key, enable_new=True, indexer_ids=ids,
    )
    return {"ok": True, **result}


@router.post("/complete")
def setup_complete(payload: SetupPayload, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_none=True)
    # merge extras
    if hasattr(payload, "model_extra") and payload.model_extra:
        data.update(payload.model_extra)
    mark = data.pop("mark_complete", True)
    applied = _apply_payload(db, data)
    bootstrap_status = None
    if mark:
        mark_complete()
        # Zero-touch: pull defs + Jackett/Prowlarr indexers in the background
        try:
            from app.services.bootstrap import bootstrap_after_setup
            bootstrap_status = bootstrap_after_setup(background=True, force_defs=True)
        except Exception as e:
            bootstrap_status = {"ok": False, "error": str(e)}
    return {
        "ok": True,
        "complete": is_setup_complete(),
        "applied": applied,
        "count": len(applied),
        "bootstrap": bootstrap_status,
        "message": "Setup complete. Indexers and definitions are syncing in the background — you can start searching.",
    }


@router.get("/bootstrap")
def setup_bootstrap_status():
    """Poll post-wizard bootstrap progress."""
    from app.services.bootstrap import last_bootstrap_result
    return last_bootstrap_result() or {"status": "idle"}


@router.post("/bootstrap")
def setup_bootstrap_run(force: bool = True, _perm: list = Depends(require_permission("settings"))):
    """Re-run full bootstrap (defs + Jackett + Prowlarr) on demand."""
    from app.services.bootstrap import bootstrap_after_setup
    return bootstrap_after_setup(background=True, force_defs=force)


@router.post("/apply")
def setup_apply(payload: SetupPayload, db: Session = Depends(get_db)):
    """Save a partial step without marking setup complete."""
    data = payload.model_dump(exclude_none=True)
    if hasattr(payload, "model_extra") and payload.model_extra:
        data.update(payload.model_extra)
    data.pop("mark_complete", None)
    applied = _apply_payload(db, data)
    return {"ok": True, "applied": applied, "count": len(applied), "complete": is_setup_complete()}


@router.post("/reset")
def setup_reset(_perm: list = Depends(require_permission("settings"))):
    """Clear setup-complete flags so the wizard shows again."""
    removed = []
    for p in _flag_paths():
        try:
            if p.exists():
                p.unlink()
                removed.append(str(p))
        except Exception:
            pass
    return {"ok": True, "removed": removed}


class GuidedStep(BaseModel):
    id: str
    title: str
    detail: str
    done: bool
    action: str | None = None  # UI page key hint
    help: str | None = None


@router.get("/guided")
def guided_first_run(db: Session = Depends(get_db)):
    """Beginner checklist per library: movies, TV, music, audiobooks, comics."""
    from pathlib import Path as FsPath
    from app.models import MediaItem, MediaType, ItemStatus

    def path_ok(attr: str) -> bool:
        v = getattr(settings, attr, "") or ""
        return bool(v)

    def counts(mt: MediaType) -> tuple[int, int]:
        try:
            total = db.query(MediaItem).filter(MediaItem.media_type == mt).count()
            done = (
                db.query(MediaItem)
                .filter(MediaItem.media_type == mt, MediaItem.status == ItemStatus.downloaded)
                .count()
            )
            return total, done
        except Exception:
            return 0, 0

    has_qbit = bool(getattr(settings, "qbit_url", ""))
    m_total, m_done = counts(MediaType.movie)
    t_total, t_done = counts(MediaType.tv)
    mu_total, mu_done = counts(MediaType.music)
    a_total, a_done = counts(MediaType.audiobook)
    c_total, c_done = counts(MediaType.comic)
    g_total, g_done = counts(MediaType.manga)

    libraries = [
        {
            "id": "movies",
            "label": "Movies",
            "steps": [
                GuidedStep("folder", "Movies folder", "Path where finished films are stored.", path_ok("movies_library_path"), "setup", "Compose volume e.g. ./data/movies → /movies"),
                GuidedStep("downloader", "Download client", "qBittorrent URL + login.", has_qbit, "setup", "Standalone compose includes qB — point mediaos at it."),
                GuidedStep("add", "Add one movie", "Discover or Movies → Add.", m_total > 0, "discover", "Pick something popular so public indexers find it."),
                GuidedStep("watch", "Play it", "When status is downloaded, hit Play.", m_done > 0, "movies", "No file? Check qBittorrent and try another title."),
            ],
        },
        {
            "id": "tv",
            "label": "TV",
            "steps": [
                GuidedStep("folder", "TV folder", "Path for TV episodes.", path_ok("tv_library_path"), "setup", "./data/tv → /tv"),
                GuidedStep("downloader", "Download client", "Same qBittorrent as movies.", has_qbit, "setup", None),
                GuidedStep("add", "Add one series", "Discover → TV, or TV page.", t_total > 0, "discover", "Add a series; episodes fill in from metadata."),
                GuidedStep("watch", "Download an episode", "Open the series → Search missing / Play when downloaded.", t_done > 0, "tv", "Episode Play appears after a file is on disk."),
            ],
        },
        {
            "id": "music",
            "label": "Music",
            "steps": [
                GuidedStep("folder", "Music folder", "Albums land here after organize.", path_ok("music_library_path"), "setup", "./data/music → /music"),
                GuidedStep("downloader", "Download client", "qBittorrent for album torrents.", has_qbit, "setup", None),
                GuidedStep("add", "Add one album", "Music page → search MusicBrainz.", mu_total > 0, "music", "Prefer a well-known album for public trackers."),
                GuidedStep("done", "Album downloaded", "Status becomes downloaded when the file is organized.", mu_done > 0, "music", "FLAC preferred by the default music profile."),
            ],
        },
        {
            "id": "audiobooks",
            "label": "Audiobooks",
            "steps": [
                GuidedStep("folder", "Audiobooks folder", "M4B / chaptered books path.", path_ok("audiobooks_library_path"), "setup", "./data/audiobooks → /audiobooks"),
                GuidedStep("downloader", "Download client", "Same download client.", has_qbit, "setup", None),
                GuidedStep("add", "Add one audiobook", "Audiobooks page → search.", a_total > 0, "audiobooks", "Look for M4B / unabridged in releases."),
                GuidedStep("done", "File on disk", "Downloaded + organized into the library.", a_done > 0, "audiobooks", None),
            ],
        },
        {
            "id": "comics",
            "label": "Comics / Manga",
            "steps": [
                GuidedStep("folder", "Comics & manga folders", "CBZ/CBR library paths.", path_ok("comics_library_path") or path_ok("manga_library_path"), "setup", "./data/comics and ./data/manga"),
                GuidedStep("meta", "Metadata (optional)", "ComicVine API key improves comic search.", bool(getattr(settings, "comicvine_api_key", "")), "setup", "MangaDex needs no key. ComicVine is free with a key."),
                GuidedStep("add", "Add a volume", "Comics page → search ComicVine or MangaDex.", (c_total + g_total) > 0, "comics", "Sync issues after add for chapter-level tracking."),
                GuidedStep("done", "Archive downloaded", "CBZ/CBR organized into the library.", (c_done + g_done) > 0, "comics", "Default profile prefers CBZ over CBR/PDF."),
            ],
        },
    ]

    # flatten primary movie track for backward compat
    movie_steps = libraries[0]["steps"]
    done_n = sum(1 for s in movie_steps if s.done)
    # overall progress across all libraries
    all_steps = [s for lib in libraries for s in lib["steps"]]
    all_done = sum(1 for s in all_steps if s.done)

    return {
        "steps": movie_steps,
        "done_count": done_n,
        "total": len(movie_steps),
        "pct": round(100 * done_n / len(movie_steps)),
        "complete": done_n == len(movie_steps),
        "libraries": [
            {
                "id": lib["id"],
                "label": lib["label"],
                "steps": lib["steps"],
                "done_count": sum(1 for s in lib["steps"] if s.done),
                "total": len(lib["steps"]),
                "pct": round(100 * sum(1 for s in lib["steps"] if s.done) / len(lib["steps"])),
                "complete": all(s.done for s in lib["steps"]),
            }
            for lib in libraries
        ],
        "overall_pct": round(100 * all_done / len(all_steps)) if all_steps else 0,
        "recommended_compose": "docker compose -f docker-compose.standalone.yml up -d",
        "power_packs": [
            {"id": "gpu", "title": "GPU converter", "compose": "docker compose -f docker-compose.yml -f docker-compose.nvidia.yml up -d", "when": "Optional encode after library works"},
            {"id": "vpn", "title": "VPN", "compose": "See docker-compose.vpn.example.yml", "when": "Optional"},
        ],
    }


@router.get("/glossary")
def glossary():
    """Plain-language terms for people new to media servers."""
    return {
        "terms": [
            {"term": "Library", "def": "Folders on disk where finished movies, shows, and other media are stored."},
            {"term": "Download client", "def": "App that fetches files (usually qBittorrent for torrents)."},
            {"term": "Indexer", "def": "Search engine for torrents or usenet — mediaos includes several public ones already."},
            {"term": "Grab", "def": "Send a release to the download client to start downloading."},
            {"term": "Organize", "def": "Move a finished download into your library with a clean name."},
            {"term": "Quality profile", "def": "Rules for preferred resolution and file type (e.g. 1080p, CBZ)."},
            {"term": "Wanted", "def": "Titles you monitor that are not on disk yet."},
            {"term": "Monitor", "def": "Keep watching for a better or missing release automatically."},
            {"term": "Compose", "def": "Docker’s recipe file that starts mediaos and related apps together."},
            {"term": "Mount / volume", "def": "Link between a folder on your computer and a path inside Docker."},
        ]
    }


@router.get("/pipelines")
def pipeline_status():
    """Map each *arr role to mediaos readiness — for one-app cutover checklist."""
    from pathlib import Path as P

    def path_ok(p: str) -> bool:
        try:
            return bool(p) and P(p).exists()
        except Exception:
            return False

    def has(attr: str) -> bool:
        v = getattr(settings, attr, None)
        return bool(v)

    pipelines = [
        {
            "replaces": "Radarr",
            "module": "Movies",
            "ready": has("tmdb_api_key") and path_ok(getattr(settings, "movies_library_path", "")),
            "needs": ["TMDb API key", "Movies library path", "Download client", "Indexer (builtin/Jackett/Prowlarr)"],
            "routes": ["/api/movies", "/api/discover/movies"],
        },
        {
            "replaces": "Sonarr",
            "module": "TV",
            "ready": (has("tmdb_api_key") or has("tvdb_api_key")) and path_ok(getattr(settings, "tv_library_path", "")),
            "needs": ["TMDb or TVDb key", "TV library path", "Download client", "Indexer"],
            "routes": ["/api/tv", "/api/calendar"],
        },
        {
            "replaces": "Lidarr",
            "module": "Music",
            "ready": path_ok(getattr(settings, "music_library_path", "")),
            "needs": ["Music library path", "Download client (MusicBrainz needs no key)"],
            "routes": ["/api/music"],
        },
        {
            "replaces": "Readarr",
            "module": "Books + Audiobooks",
            "ready": path_ok(getattr(settings, "books_library_path", "")) or path_ok(getattr(settings, "audiobooks_library_path", "")),
            "needs": ["Books and/or Audiobooks path"],
            "routes": ["/api/books", "/api/audiobooks"],
        },
        {
            "replaces": "Bazarr",
            "module": "Subtitles",
            "ready": has("opensubtitles_api_key") or bool(getattr(settings, "subtitle_providers", "")),
            "needs": ["OpenSubtitles key (or other providers)", "subtitle_languages"],
            "routes": ["/api/movies/{id}/subtitles"],
        },
        {
            "replaces": "Prowlarr / Jackett",
            "module": "Indexers",
            "ready": True,  # builtins always on
            "needs": ["Optional: Jackett sync, Prowlarr, or Cardigann YAML"],
            "routes": ["/api/indexers", "/api/indexers/cardigann", "/api/indexers/builtin", "/api/indexers/jackett/sync"],
        },
        {
            "replaces": "Overseerr / Jellyseerr",
            "module": "Requests",
            "ready": True,
            "needs": ["Optional: ARR_API_KEY for external clients"],
            "routes": ["/api/requests"],
        },
        {
            "replaces": "FlareSolverr",
            "module": "CF bypass",
            "ready": bool(getattr(settings, "cf_bypass_enabled", True)),
            "needs": ["curl_cffi in image; optional FLARESOLVERR_URL"],
            "routes": [],
        },
        {
            "replaces": "Cleanuparr",
            "module": "Queue cleaner",
            "ready": bool(getattr(settings, "cleanup_enabled", True)),
            "needs": ["qB/Transmission categories mediaos*"],
            "routes": ["/api/tools/cleanup/run"],
        },
        {
            "replaces": "— (beyond *arr)",
            "module": "Podcasts / Comics / YouTube / Live TV / Converter",
            "ready": True,
            "needs": ["Configure paths in wizard for types you use"],
            "routes": ["/api/podcasts", "/api/comics", "/api/youtube", "/api/livetv", "/api/converter"],
        },
    ]
    download_ready = has("qbit_url") or has("transmission_url") or has("deluge_url") or has("rtorrent_url") or has("aria2_url")
    return {
        "download_client_ready": download_ready,
        "setup_complete": is_setup_complete(),
        "pipelines": pipelines,
        "cutover_order": [
            "Radarr (Movies)",
            "Sonarr (TV)",
            "Bazarr (Subtitles)",
            "Overseerr (Requests)",
            "Lidarr / Readarr (Music / Books)",
            "Prowlarr / Jackett (optional once builtins + Jackett sync work)",
            "Cleanuparr (optional)",
            "FlareSolverr (optional)",
        ],
    }


# ── Modules selection (wizard + Module Store) ─────────────────────────────
from app.services import modules as modsvc


class ModulesBody(BaseModel):
    enabled: list[str] = Field(default_factory=list)


@router.get("/modules")
def setup_modules(db: Session = Depends(get_db)):
    """Catalog for the wizard Modules step."""
    return modsvc.status(db)


@router.post("/modules")
def setup_save_modules(body: ModulesBody, db: Session = Depends(get_db)):
    """Save selected modules from the wizard (movies+tv always on)."""
    enabled = modsvc.set_enabled(db, body.enabled)
    return {"ok": True, "enabled": enabled}
