"""
Games module router (Questarr-inspired, MediaOS v2).

Opt-in via Module Store. Shares download clients + indexers where applicable.
"""
import logging
log = logging.getLogger(__name__)

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_permission
from app.config import settings
from app.models import Game, Platform, GameRelease

router = APIRouter(prefix="/games", tags=["games"])

@router.get("/install-jobs")
def list_install_jobs(limit: int = 50, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    from app.models import GameInstallJob
    rows = db.query(GameInstallJob).order_by(GameInstallJob.id.desc()).limit(limit).all()
    return {"items": [
        {"id": r.id, "game_id": r.game_id, "status": r.status, "kind": r.kind or "install",
         "command": r.command, "log_text": (r.log_text or "")[:2000], "returncode": r.returncode,
         "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]}


@router.get("/install-jobs/{job_id}")
def get_install_job(job_id: int, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    from app.models import GameInstallJob
    r = db.get(GameInstallJob, job_id)
    if not r:
        raise HTTPException(404, "Not found")
    return {"id": r.id, "game_id": r.game_id, "status": r.status, "kind": r.kind or "install",
            "command": r.command, "log_text": r.log_text, "returncode": r.returncode}



class PlatformIn(BaseModel):
    name: str
    slug: str
    icon_url: Optional[str] = None
    metadata_provider: Optional[str] = None
    emulator_command: Optional[str] = None


class PlatformUpdate(BaseModel):
    name: Optional[str] = None
    icon_url: Optional[str] = None
    metadata_provider: Optional[str] = None
    emulator_command: Optional[str] = None


class GameIn(BaseModel):
    title: str
    year: Optional[int] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    platform_id: Optional[int] = None
    monitored: bool = True
    quality_profile: Optional[str] = None
    external_ids: Optional[str] = None


class GameUpdate(BaseModel):
    title: Optional[str] = None
    monitored: Optional[bool] = None
    status: Optional[str] = None
    path: Optional[str] = None
    install_path: Optional[str] = None
    launcher: Optional[str] = None
    quality_profile: Optional[str] = None
    completion_percent: Optional[float] = None
    playtime_minutes: Optional[int] = None


@router.get("")
def list_games(
    status: Optional[str] = None,
    monitored: Optional[bool] = None,
    q: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Game)
    if status:
        query = query.filter(Game.status == status)
    if monitored is not None:
        query = query.filter(Game.monitored == monitored)
    if q:
        query = query.filter(Game.title.ilike(f"%{q}%"))
    total = query.count()
    items = query.order_by(Game.title).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": g.id,
                "title": g.title,
                "year": g.year,
                "status": g.status,
                "monitored": g.monitored,
                "platform_id": g.platform_id,
                "poster_path": g.poster_path,
                "completion_percent": g.completion_percent,
                "playtime_minutes": g.playtime_minutes,
                "path": g.path,
            }
            for g in items
        ],
    }


@router.post("")
def add_game(
    body: GameIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("library")),
):
    g = Game(
        title=body.title,
        year=body.year,
        overview=body.overview,
        poster_path=body.poster_path,
        platform_id=body.platform_id,
        monitored=body.monitored,
        quality_profile=body.quality_profile,
        external_ids=body.external_ids,
        status="wanted",
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return {"ok": True, "id": g.id, "title": g.title}


@router.get("/search")
def search_games_meta(q: str, limit: int = 20):
    from app.clients import igdb
    configured = False
    try:
        configured = bool(igdb.configured())
    except Exception:
        configured = False
    results = igdb.search(q, limit=limit) if configured else []
    return {
        "results": results or [],
        "provider": "igdb" if configured else "none",
        "configured": configured,
        "message": None
        if configured
        else "IGDB not configured — set igdb_client_id + igdb_client_secret (Twitch) in Settings",
    }


@router.get("/wanted")
def list_wanted_games(db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    rows = db.query(Game).filter(Game.monitored.is_(True), Game.status.in_(["wanted", "missing"])).order_by(Game.id.desc()).limit(100).all()
    return {
        "items": [
            {"id": g.id, "title": g.title, "year": g.year, "status": g.status, "platform_id": g.platform_id}
            for g in rows
        ]
    }


# NOTE: "/{game_id}" below is a single dynamic path segment, so any literal
# single-segment GET route (like "/search" or "/wanted" above) must be
# registered before it — FastAPI/Starlette match routes in registration
# order, so a literal route declared after "/{game_id}" would be shadowed
# (e.g. GET /search would 422 trying to parse "search" as an int game_id).

class GameBulkIn(BaseModel):
    ids: list[int]
    monitored: bool | None = None


@router.post("/bulk")
def bulk_games(payload: GameBulkIn, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Bulk monitor toggle for games — must sit before /{game_id}."""
    n = 0
    for gid in payload.ids:
        g = db.get(Game, gid)
        if not g:
            continue
        if payload.monitored is not None:
            g.monitored = payload.monitored
        db.add(g)
        n += 1
    db.commit()
    return {"ok": True, "updated": n}



@router.get("/{game_id}")
def get_game(game_id: int, db: Session = Depends(get_db)):
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    releases = db.query(GameRelease).filter(GameRelease.game_id == game_id).all()
    return {
        "id": g.id,
        "title": g.title,
        "year": g.year,
        "overview": g.overview,
        "status": g.status,
        "monitored": g.monitored,
        "path": g.path,
        "completion_percent": g.completion_percent,
        "playtime_minutes": g.playtime_minutes,
        "poster_path": g.poster_path,
        "platform_id": g.platform_id,
        "releases": [
            {"id": r.id, "title": r.title, "edition": r.edition, "grabbed": r.grabbed, "installed": r.installed}
            for r in releases
        ],
    }




@router.post("/{game_id}/launch")
def launch_game(game_id: int, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Return launch targets: Steam URL, emulator (if configured), install path, or library path."""
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Not found")
    steam_id = None
    try:
        import json
        ext = json.loads(g.external_ids or "{}")
        steam_id = ext.get("steam") or ext.get("steam_appid")
    except Exception:
        pass
    if not steam_id and getattr(g, "steam_appid", None):
        steam_id = g.steam_appid
    targets = []
    if steam_id:
        targets.append({"kind": "steam", "url": f"steam://run/{steam_id}", "label": "Steam"})
    if g.platform_id:
        from app.services.emulator import get_emulator_target
        platform = db.get(Platform, g.platform_id)
        emulator_target = get_emulator_target(g, platform)
        if emulator_target:
            targets.append(emulator_target)
    if g.install_path:
        targets.append({"kind": "install_path", "path": g.install_path, "label": "Install folder"})
    if g.path:
        targets.append({"kind": "library_path", "path": g.path, "label": "Library path"})
    if not targets:
        raise HTTPException(404, "No launch target (set Steam id, emulator, or install path)")
    return {"ok": True, "game_id": g.id, "title": g.title, "targets": targets, "primary": targets[0]}


@router.post("/{game_id}/launch/emulator")
def launch_game_emulator(game_id: int, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Actually run the game's platform emulator_command as a background job."""
    from app.services.emulator import EmulatorConfigError, launch_via_emulator

    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    if not g.platform_id:
        raise HTTPException(400, "Game has no platform set")
    platform = db.get(Platform, g.platform_id)
    if not platform:
        raise HTTPException(404, "Platform not found")
    try:
        job = launch_via_emulator(db, g, platform)
    except EmulatorConfigError as e:
        raise HTTPException(400, str(e))
    return {
        "ok": True,
        "job_id": job.id,
        "game_id": g.id,
        "status": job.status,
        "command": job.command,
    }


@router.patch("/{game_id}")
def update_game(
    game_id: int,
    body: GameUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("library")),
):
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(g, k, v)
    db.commit()
    return {"ok": True, "id": g.id}


@router.delete("/{game_id}")
def delete_game(
    game_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("library")),
):
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    db.delete(g)
    db.commit()
    return {"ok": True}


@router.get("/platforms/list")
def list_platforms(db: Session = Depends(get_db)):
    rows = db.query(Platform).order_by(Platform.name).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "icon_url": p.icon_url,
            "emulator_command": p.emulator_command,
        }
        for p in rows
    ]


@router.post("/platforms")
def add_platform(
    body: PlatformIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("settings")),
):
    p = Platform(
        name=body.name,
        slug=body.slug,
        icon_url=body.icon_url,
        metadata_provider=body.metadata_provider,
        emulator_command=body.emulator_command,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"ok": True, "id": p.id}


@router.patch("/platforms/{platform_id}")
def update_platform(
    platform_id: int,
    body: PlatformUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("settings")),
):
    p = db.get(Platform, platform_id)
    if not p:
        raise HTTPException(404, "Platform not found")
    if body.name is not None:
        p.name = body.name
    if body.icon_url is not None:
        p.icon_url = body.icon_url
    if body.metadata_provider is not None:
        p.metadata_provider = body.metadata_provider
    if body.emulator_command is not None:
        p.emulator_command = body.emulator_command
    db.add(p)
    db.commit()
    return {
        "ok": True,
        "id": p.id,
        "name": p.name,
        "icon_url": p.icon_url,
        "metadata_provider": p.metadata_provider,
        "emulator_command": p.emulator_command,
    }


# --- Questarr-depth: IGDB search, platform seed, search-grab ---

DEFAULT_PLATFORMS = [
    ("PC", "pc"),
    ("Steam", "steam"),
    ("GOG", "gog"),
    ("Epic", "epic"),
    ("PlayStation 5", "ps5"),
    ("PlayStation 4", "ps4"),
    ("Xbox Series X|S", "xbox-series"),
    ("Xbox One", "xbox-one"),
    ("Nintendo Switch", "switch"),
    ("Nintendo 3DS", "3ds"),
    ("Android", "android"),
    ("iOS", "ios"),
]


@router.post("/platforms/seed")
def seed_platforms(db: Session = Depends(get_db), _=Depends(require_permission("settings"))):
    added = 0
    for name, slug in DEFAULT_PLATFORMS:
        exists = db.query(Platform).filter(Platform.slug == slug).first()
        if exists:
            continue
        db.add(Platform(name=name, slug=slug))
        added += 1
    db.commit()
    return {"ok": True, "added": added, "total": db.query(Platform).count()}


@router.get("/{game_id}/interactive-search")
def game_interactive_search(game_id: int, db: Session = Depends(get_db)):
    """Shared interactive search pipeline (integration B)."""
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    from app.services.interactive_search import interactive_game_search
    data = interactive_game_search(g.title, db=db, limit=50)
    # normalize to list for UI that expects array
    results = data.get("results") if isinstance(data, dict) else data
    return results if isinstance(results, list) else (data or {})


@router.post("/{game_id}/grab")
def game_grab(game_id: int, body: dict, db: Session = Depends(get_db), _=Depends(require_permission("download"))):
    """Grab via shared download clients + queue row with game_id (integration A)."""
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    from app.services.grab import grab_game_release
    try:
        dl = grab_game_release(db, g, body)
        return {
            "ok": True,
            "download_id": dl.id,
            "title": dl.release_title,
            "status": dl.status,
            "game_id": g.id,
        }
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/{game_id}/search-grab")
def search_and_grab_game(game_id: int, db: Session = Depends(get_db), _=Depends(require_permission("download"))):
    """Search then return candidates (grab explicitly via /grab)."""
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    from app.services.interactive_search import interactive_game_search
    data = interactive_game_search(g.title, db=db, limit=25)
    results = data.get("results") if isinstance(data, dict) else (data or [])
    return {"ok": True, "game_id": g.id, "title": g.title, "results": results}


@router.post("/{game_id}/organize")
def organize_game(game_id: int, body: dict | None = None, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Move/link completed download into games library layout and mark downloaded."""
    from pathlib import Path as _Path
    from app.config import settings
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    body = body or {}
    src = body.get("source_path") or g.path
    if src:
        from pathlib import Path as _ValidatePath
        _downloads_root = _ValidatePath(getattr(settings, "downloads_path", None) or "/downloads").resolve()
        _games_root = _ValidatePath(getattr(settings, "games_library_path", None) or "/games").resolve()
        _candidate = _ValidatePath(src)
        _resolved = _candidate if _candidate.is_absolute() else (_downloads_root / _candidate)
        _resolved = _resolved.resolve()
        _allowed = any(
            _resolved == _root or _root in _resolved.parents
            for _root in (_downloads_root, _games_root)
        )
        if not _allowed:
            raise HTTPException(400, "source_path must be inside the downloads folder or games library")
        src = str(_resolved)
    if not src:
        # try latest completed download for this game
        from app.models import Download
        dl = (
            db.query(Download)
            .filter(Download.game_id == game_id, Download.status.in_(["completed", "grabbed", "downloading"]))
            .order_by(Download.id.desc())
            .first()
        )
        src = getattr(dl, "path", None) or getattr(dl, "output_path", None) if dl else None
    lib = _Path(getattr(settings, "games_library_path", None) or "/games")
    lib.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in (g.title or "game"))[:80].strip() or "game"
    dest = lib / safe
    dest.mkdir(parents=True, exist_ok=True)
    organized = None
    if src:
        import shutil, os
        sp = _Path(src)
        try:
            if sp.is_file():
                target = dest / sp.name
                if not target.exists():
                    try:
                        os.link(sp, target)
                    except Exception:
                        shutil.copy2(sp, target)
                organized = str(target)
            elif sp.is_dir():
                for child in sp.iterdir():
                    target = dest / child.name
                    if not target.exists():
                        try:
                            if child.is_dir():
                                shutil.copytree(child, target)
                            else:
                                try:
                                    os.link(child, target)
                                except Exception:
                                    shutil.copy2(child, target)
                        except Exception:
                            pass
                organized = str(dest)
        except Exception as e:
            raise HTTPException(400, f"organize failed: {e}")
    g.path = str(dest)
    g.install_path = organized or str(dest)
    g.status = "installed" if (organized or dest) else "downloaded"
    db.add(g)
    db.commit()
    return {"ok": True, "path": g.path, "install_path": g.install_path, "status": g.status}




@router.post("/{game_id}/install")
def install_game(game_id: int, body: dict | None = None, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Mark install_path and status=installed (optional path override)."""
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Not found")
    body = body or {}
    if body.get("install_path"):
        g.install_path = body["install_path"]
    elif not g.install_path and g.path:
        g.install_path = g.path
    if not g.install_path and not g.path:
        raise HTTPException(400, "No path to install — organize or set install_path first")
    g.status = "installed"
    db.add(g)
    db.commit()
    script_out = None
    job_id = None
    try:
        from app.config import settings
        from app.models import GameInstallJob
        from datetime import datetime, timezone
        script = (getattr(settings, "games_install_script", None) or "").strip()
        if script and g.install_path:
            import shlex, subprocess
            cmd = script.format(path=g.install_path, title=g.title or "", id=g.id)
            job = GameInstallJob(game_id=g.id, status="running", command=cmd)
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = job.id
            proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=120)
            log_text = ((proc.stdout or "") + chr(10) + (proc.stderr or ""))[:8000]
            job.log_text = log_text
            job.returncode = proc.returncode
            job.status = "done" if proc.returncode == 0 else "failed"
            job.finished_at = datetime.now(timezone.utc)
            db.add(job)
            db.commit()
            script_out = {"returncode": proc.returncode, "stdout": (proc.stdout or "")[:500], "stderr": (proc.stderr or "")[:500], "job_id": job_id}
    except Exception as e:
        script_out = {"error": str(e), "job_id": job_id}
    return {"ok": True, "id": g.id, "status": g.status, "install_path": g.install_path, "path": g.path, "script": script_out}


@router.post("/{game_id}/complete")
def complete_game(game_id: int, body: dict | None = None, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Mark game installed/completed with optional playtime/completion."""
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    body = body or {}
    if body.get("install_path"):
        g.install_path = body["install_path"]
    if body.get("path"):
        g.path = body["path"]
    if body.get("launcher"):
        g.launcher = body["launcher"]
    if body.get("completion_percent") is not None:
        g.completion_percent = float(body["completion_percent"])
    if body.get("playtime_minutes") is not None:
        g.playtime_minutes = int(body["playtime_minutes"])
    status = body.get("status") or "installed"
    if body.get("completed") or (g.completion_percent or 0) >= 100:
        status = "completed"
    g.status = status
    db.add(g)
    db.commit()
    return {"ok": True, "id": g.id, "status": g.status, "path": g.path, "install_path": g.install_path}


# ── Metadata search + grab pipeline (Questarr depth) ─────────────────────────

@router.get("/metadata/search")
def metadata_search(q: str = Query(..., min_length=1), limit: int = 25, _=Depends(require_permission("library"))):
    """Search IGDB + Steam for games to add."""
    from app.clients import igdb, steam
    results = []
    try:
        results.extend(igdb.search_games(q, limit=limit))
    except Exception as e:
        log.warning("IGDB search failed for %r: %s", q, e)
    try:
        results.extend(steam.search_store(q, limit=min(10, limit)))
    except Exception as e:
        log.warning("Steam search failed for %r: %s", q, e)
    # de-dupe by title lower
    seen = set()
    out = []
    for r in results:
        key = (r.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return {"query": q, "results": out[:limit], "igdb_configured": igdb.configured()}


@router.get("/metadata/igdb/{igdb_id}")
def metadata_igdb_detail(igdb_id: int, _=Depends(require_permission("library"))):
    from app.clients import igdb
    d = igdb.game_detail(igdb_id)
    if not d:
        raise HTTPException(404, "IGDB game not found")
    return d


@router.get("/metadata/steam/{appid}")
def metadata_steam_detail(appid: int, _=Depends(require_permission("library"))):
    from app.clients import steam
    d = steam.app_details(appid)
    if not d:
        raise HTTPException(404, "Steam app not found")
    return d


@router.post("/from-metadata")
def add_from_metadata(body: dict, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Add monitored game from IGDB/Steam search result."""
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title required")
    platform_id = body.get("platform_id")
    external = {}
    if body.get("igdb_id"):
        external["igdb"] = body["igdb_id"]
    if body.get("steam_appid"):
        external["steam"] = body["steam_appid"]
    import json
    g = Game(
        title=title,
        year=body.get("year"),
        overview=body.get("overview"),
        poster_path=body.get("poster_path"),
        platform_id=platform_id,
        monitored=bool(body.get("monitored", True)),
        status="wanted",
        external_ids=json.dumps(external) if external else None,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return {"ok": True, "id": g.id, "title": g.title, "status": g.status}


@router.post("/{game_id}/search")
def search_game_releases(game_id: int, db: Session = Depends(get_db), _=Depends(require_permission("download", "library"))):
    """Interactive search via shared indexer pipeline (torznab / prowlarr)."""
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    try:
        from app.services.interactive_search import interactive_game_search
        return interactive_game_search(g.title, db=db, limit=50)
    except Exception as e:
        return {"game_id": g.id, "title": g.title, "results": [], "error": str(e)}


@router.post("/{game_id}/grab-url")
def grab_game_by_url(game_id: int, body: dict, db: Session = Depends(get_db), _=Depends(require_permission("download"))):
    """Manual grab: send an arbitrary magnet/torrent/link straight to the download client.

    Distinct from POST /{game_id}/grab (release-object grab through
    app.services.grab.grab_game_release) — this endpoint is for pasting a raw
    URL/magnet that didn't come from an indexer search result.
    """
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    download_url = body.get("download_url") or body.get("magnet") or body.get("link")
    if not download_url:
        raise HTTPException(400, "download_url or magnet required")
    from app.services.vpn import vpn_allows_grabs
    vpn_ok, vpn_reason = vpn_allows_grabs()
    if not vpn_ok:
        raise HTTPException(409, vpn_reason)
    try:
        from app.services.download_clients import add_torrent
        category = getattr(settings, "qbit_category_games", None) or getattr(settings, "qbit_category", None) or "mediaos-games"
        save_path = getattr(settings, "games_library_path", None) or getattr(settings, "downloads_path", "/downloads")
        add_torrent(download_url, save_path=str(save_path), category=category)
        g.status = "downloading"
        db.add(g)
        db.commit()
        return {"ok": True, "status": "downloading"}
    except Exception as e:
        raise HTTPException(400, f"grab failed: {e}")


@router.post("/{game_id}/playtime")
def add_playtime(game_id: int, body: dict, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Increment playtime_minutes and optionally push completion into tracking."""
    g = db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    mins = int(body.get("minutes") or body.get("playtime_minutes") or 0)
    if mins < 0:
        raise HTTPException(400, "minutes must be >= 0")
    g.playtime_minutes = int(g.playtime_minutes or 0) + mins
    if body.get("completion_percent") is not None:
        g.completion_percent = float(body["completion_percent"])
    if body.get("launcher"):
        g.launcher = body["launcher"]
    if (g.completion_percent or 0) >= 100:
        g.status = "completed"
    db.add(g)
    db.commit()
    # feed tracking layer when media_item link exists
    try:
        if getattr(g, "media_item_id", None):
            from app.models import TrackedItem
            from datetime import datetime, timezone
            tr = db.query(TrackedItem).filter(TrackedItem.media_item_id == g.media_item_id).first()
            if tr:
                tr.progress_percent = g.completion_percent or tr.progress_percent
                if g.status == "completed":
                    tr.status = "completed"
                elif (g.playtime_minutes or 0) > 0 and tr.status in ("planned", None, ""):
                    tr.status = "in_progress"
                tr.updated_at = datetime.now(timezone.utc)
                db.add(tr)
                db.commit()
    except Exception:
        pass
    return {
        "ok": True,
        "id": g.id,
        "playtime_minutes": g.playtime_minutes,
        "completion_percent": g.completion_percent,
        "status": g.status,
        "launcher": g.launcher,
    }

