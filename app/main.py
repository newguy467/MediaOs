import base64
import os
import logging
import uuid
import secrets

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import (
    _auth_enabled,
    _valid_token,
    hash_password,
    revoke_token,
    try_login,
)
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import (
    library_gaps,
    library_tools,
    sse,
    migrate,

    arr_compat,
    audiobooks,
    books,
    comics,
    youtube,
    calendar,
    collections,
    discover,
    imports,
    indexers,
    livetv,
    movies,
    adult,
    music,
    music_smartlists,
    podcasts,
    player,
    converter,
    queue,
    requests as requests_router,
    smartlists,
    system,
    tools,
    tv,
    users,
    wanted,
    setup,
    parity,
    auth_sessions,
    quality_ui,
    overhaul,
    modules,
    plugins as plugins_router,
    hunt,
    ai,
    games,
    scrobbling,
    tracking,
    homelab,
    webhooks,
    imports_tracking,
    global_search,
)
from app.routers import settings as settings_router
from app.scheduler import start_scheduler
from app.services.quality.store import seed_default_profiles
from app.services.converter import seed_default_presets as seed_convert_presets

from app.logging_config import configure_logging, request_id_var
from app.version import get_version
configure_logging()
log = logging.getLogger("mediaos")


app = FastAPI(
    title="MediaOS",
    version=get_version(),
    description="All-in-one media & games OS — movies, TV, music, books, audiobooks, comics, adult, Live TV, games, scrobbling, tracking",
)

# CORS: same-origin UI needs none; allow configured origins for split frontends / LAN apps.
# Set CORS_ORIGINS=* only for trusted private networks.
_cors_origins = [o.strip() for o in (getattr(settings, "cors_origins", "") or "").split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if _cors_origins == ["*"] else _cors_origins,
        allow_credentials=_cors_origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Attach request id, log access + errors for every HTTP call."""
    import time
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    token = request_id_var.set(rid)
    start = time.perf_counter()
    access = logging.getLogger("mediaos.access")
    try:
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        path = request.url.path
        if not path.startswith(("/assets", "/favicon", "/api/sse")):
            access.info(
                "%s %s → %s %.1fms",
                request.method,
                path,
                response.status_code,
                elapsed_ms,
            )
        response.headers["X-Request-Id"] = rid
        return response
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log.exception("Unhandled error %s %s (%.1fms)", request.method, request.url.path, elapsed_ms)
        raise
    finally:
        request_id_var.reset(token)

app.include_router(movies.router, prefix="/api")
app.include_router(adult.router, prefix="/api")
app.include_router(tv.router, prefix="/api")
app.include_router(music.router, prefix="/api")
app.include_router(music_smartlists.router, prefix="/api")
app.include_router(books.router, prefix="/api")
app.include_router(audiobooks.router, prefix="/api")
app.include_router(calendar.router, prefix="/api")
app.include_router(smartlists.router, prefix="/api")
app.include_router(indexers.router, prefix="/api")
app.include_router(queue.router, prefix="/api")
app.include_router(tools.router, prefix="/api")
app.include_router(sse.router, prefix="/api")
app.include_router(migrate.router, prefix="/api")
app.include_router(wanted.router, prefix="/api")
app.include_router(setup.router, prefix="/api")
app.include_router(parity.router, prefix="/api")
app.include_router(auth_sessions.router, prefix="/api")
app.include_router(quality_ui.router, prefix="/api")
app.include_router(overhaul.router, prefix="/api")
app.include_router(arr_compat.router)  # /api/v3/* LunaSea shim
app.include_router(discover.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(livetv.router, prefix="/api")
app.include_router(library_tools.router, prefix="/api")
app.include_router(library_gaps.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(podcasts.router, prefix="/api")
app.include_router(collections.router, prefix="/api")
app.include_router(requests_router.router, prefix="/api")
app.include_router(comics.router, prefix="/api")
app.include_router(youtube.router, prefix="/api")
app.include_router(player.router, prefix="/api")
app.include_router(converter.router, prefix="/api")
app.include_router(modules.router, prefix="/api")
app.include_router(plugins_router.router, prefix="/api")
app.include_router(hunt.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(games.router, prefix="/api")
app.include_router(scrobbling.router, prefix="/api")
app.include_router(tracking.router, prefix="/api")
app.include_router(homelab.router, prefix="/api")
app.include_router(global_search.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(imports_tracking.router, prefix="/api")


class LoginBody(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def auth_login(body: LoginBody, request: Request):
    if not _auth_enabled():
        return {"token": None, "auth_required": False}
    from app.services import rate_limit

    client_ip = request.client.host if request.client else "unknown"
    rl_key = f"login:{client_ip}:{body.username.strip().lower()}"
    remaining = rate_limit.remaining_backoff(rl_key)
    if remaining > 0:
        return JSONResponse(
            {"detail": f"Too many failed attempts. Try again in {int(remaining)}s."},
            status_code=429,
            headers={"Retry-After": str(int(remaining) + 1)},
        )
    result = try_login(body.username, body.password)
    if not result:
        rate_limit.record_failure(rl_key, "invalid credentials", base_seconds=15.0)
        return JSONResponse({"detail": "Invalid credentials"}, status_code=401)
    rate_limit.record_success(rl_key)
    token, role = result
    return {
        "token": token,
        "token_type": "bearer",
        "expires_in": 604800,
        "role": role,
        "username": body.username,
    }


@app.post("/api/auth/logout")
def auth_logout(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        revoke_token(auth.split(" ", 1)[1].strip())
    return {"ok": True}


@app.get("/api/auth/status")
def auth_status():
    methods = []
    if (settings.auth_username or "").strip():
        methods.append("basic_env")
        methods.append("bearer")
    if (settings.auth_api_key or "").strip():
        methods.append("api_key")
    try:
        from app.models import User

        db = SessionLocal()
        try:
            if db.query(User).filter(User.is_active.is_(True)).count() > 0:
                methods.append("db_users")
                methods.append("bearer")
        finally:
            db.close()
    except Exception:
        pass
    return {"required": _auth_enabled(), "methods": sorted(set(methods))}


@app.middleware("http")
async def optional_auth_middleware(request: Request, call_next):
    path = request.url.path
    open_paths = {
        "/api/health",
        "/api/auth/login",
        "/api/auth/status",
        "/api/auth/logout",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
    if not path.startswith("/api") or path in open_paths:
        return await call_next(request)
    if not _auth_enabled():
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    expected_key = (settings.auth_api_key or "").strip()
    if expected_key and api_key and secrets.compare_digest(api_key.strip(), expected_key):
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        if _valid_token(auth.split(" ", 1)[1].strip()):
            return await call_next(request)

    if auth.startswith("Basic "):
        try:
            raw = base64.b64decode(auth.split(" ", 1)[1]).decode()
            u, p = raw.split(":", 1)
            env_user = (settings.auth_username or "").strip()
            env_pw = (settings.auth_password or "").strip()
            if (
                env_user
                and secrets.compare_digest(u, env_user)
                and secrets.compare_digest(p, env_pw)
            ):
                return await call_next(request)
            from app.auth import _check_db_user

            if _check_db_user(u, p):
                return await call_next(request)
        except Exception:
            pass

    return JSONResponse(
        {"detail": "Authentication required"},
        status_code=401,
        headers={"WWW-Authenticate": "Basic"},
    )




def _ensure_bootstrap_auth() -> None:
    """Require authentication on fresh installs without shipping a default secret.

    If the administrator did not configure AUTH_* values and no DB users exist,
    generate a one-time local admin credential and persist it under data_path/bootstrap.
    The password is never returned by an API endpoint.
    """
    if (settings.auth_username or settings.auth_api_key or settings.auth_seed_admin_username):
        return
    try:
        from app.models import User
        db = SessionLocal()
        try:
            if db.query(User).filter(User.is_active.is_(True)).count() > 0:
                return
        finally:
            db.close()
    except Exception:
        return
    from pathlib import Path as _P
    root = _P(getattr(settings, "data_path", None) or "/app/data") / "bootstrap"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Configured data dir isn't writable (e.g. /app/data in CI/local dev).
        # Fall back to a local ./data directory so startup never crashes.
        root = _P("data") / "bootstrap"
        root.mkdir(parents=True, exist_ok=True)
    cred_file = root / "admin-credentials.txt"
    if cred_file.exists():
        lines = cred_file.read_text(encoding="utf-8").splitlines()
        vals = dict(line.split("=", 1) for line in lines if "=" in line)
        user = vals.get("username", "").strip()
        pw = vals.get("password", "").strip()
        if user and pw:
            settings.auth_username = user
            settings.auth_password = pw
            return
    user = "admin"
    pw = secrets.token_urlsafe(24)
    settings.auth_username = user
    settings.auth_password = pw
    cred_file.write_text(f"username={user}\npassword={pw}\n", encoding="utf-8")
    try:
        cred_file.chmod(0o600)
    except OSError:
        pass
    log.warning("Generated first-run admin credentials at %s", cred_file)


def _seed_admin_if_needed() -> None:
    seed_user = (settings.auth_seed_admin_username or "").strip()
    seed_pw = (settings.auth_seed_admin_password or "").strip()
    if not seed_user or not seed_pw:
        return
    from app.models import User, UserRole

    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return
        user = User(
            username=seed_user,
            password_hash=hash_password(seed_pw),
            role=UserRole.admin.value,
            is_active=True,
        )
        db.add(user)
        db.commit()
        log.info("Seeded admin user %r", seed_user)
    finally:
        db.close()


@app.on_event("startup")
async def _start_watch():
    try:
        from app.services.library_watch import start_library_watch
        start_library_watch()
    except Exception:
        pass


def _ensure_download_cleanup_columns():
    """Add strikes/last_error on downloads if missing (create_all does not ALTER)."""
    from sqlalchemy import text
    with engine.begin() as conn:
        dialect = engine.dialect.name
        if dialect == "sqlite":
            rows = conn.execute(text("PRAGMA table_info(downloads)")).fetchall()
            cols = {r[1] for r in rows}
            if "strikes" not in cols:
                conn.execute(text("ALTER TABLE downloads ADD COLUMN strikes INTEGER DEFAULT 0"))
            if "last_error" not in cols:
                conn.execute(text("ALTER TABLE downloads ADD COLUMN last_error VARCHAR"))
        else:
            # postgres
            conn.execute(text(
                "ALTER TABLE downloads ADD COLUMN IF NOT EXISTS strikes INTEGER DEFAULT 0"
            ))
            conn.execute(text(
                "ALTER TABLE downloads ADD COLUMN IF NOT EXISTS last_error VARCHAR"
            ))


@app.on_event("startup")
def on_startup():
    # Alembic is the single authoritative schema manager.
    try:
        import os as _os
        from alembic import command as _alembic_command
        from alembic.config import Config as _AlembicConfig
        _alembic_cfg = _AlembicConfig(_os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "alembic.ini"))
        _alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
        _alembic_command.upgrade(_alembic_cfg, "head")
        log.info("database migrations at Alembic head")
    except Exception as exc:
        log.exception("database migration failed; refusing to continue with an unknown schema")
        raise RuntimeError("MediaOS database migration failed") from exc
    try:
        from app.services.plugins import load_plugins, run_hook
        load_plugins()
        try:
            run_hook("startup")
        except Exception as _he:
            log.debug("plugin startup hooks: %s", _he)
    except Exception as _pe:
        log.debug('plugins: %s', _pe)
    Base.metadata.create_all(bind=engine)
    try:
        from app.services.converter import seed_default_presets as _seed_cp, seed_library_watch_folders as _seed_wf
        _db = SessionLocal()
        try:
            _seed_cp(_db)
            _seed_wf(_db)
        finally:
            _db.close()
    except Exception as _ce:
        log.debug("converter seed: %s", _ce)

    # Versioned soft migrations (replaces ad-hoc ALTER lists)
    try:
        from app.services.schema_migrate import run_schema_migrations
        mig = run_schema_migrations(engine)
        if mig.get("applied"):
            log.info("schema migrations applied: %s", [a["version"] for a in mig["applied"]])
    except Exception:
        # A failed schema migration is not safe to treat as a warning.
        # Continuing would let the API start against a partially upgraded
        # database and turn a deterministic startup problem into scattered
        # runtime failures. Fail startup so Docker/systemd can restart and
        # surface the migration error clearly.
        log.exception("schema migration failed; refusing to start with an unverified database schema")
        raise
    # Legacy ensure (kept for safety on very old DBs)
    try:
        _ensure_download_cleanup_columns()
    except Exception as exc:
        log.warning('schema ensure cleanup columns: %s', exc)
    db = SessionLocal()
    try:
        seed_convert_presets(db)
        seed_default_profiles(db)
        from app.services.app_settings import load_overrides
        load_overrides(db)
    finally:
        db.close()
    _seed_admin_if_needed()
    _ensure_bootstrap_auth()
    app.state.scheduler = start_scheduler()
    # Automatic Live TV: iptv-org playlists + EPG (zero-touch)
    try:
        from app.config import settings as _livetv_s
        if getattr(_livetv_s, "livetv_seed_iptv_org", True):
            from app.scheduler import run_iptv_org_resync, run_livetv_epg_sync
            import threading
            def _livetv_boot():
                try:
                    run_iptv_org_resync()
                    run_livetv_epg_sync()
                except Exception as _le:
                    log.warning("LiveTV auto boot: %s", _le)
            threading.Thread(target=_livetv_boot, name="livetv-boot", daemon=True).start()
            log.info("LiveTV auto: iptv-org seed/resync + EPG scheduled in background")
    except Exception as _e:
        log.debug("LiveTV auto skip: %s", _e)

    # Zero-touch startup: seed defs, and if wizard already done run full bootstrap
    try:
        from app.routers.setup import is_setup_complete
        from app.services.bootstrap import bootstrap_after_setup
        from app.config import settings as _s
        if is_setup_complete():
            # Full background bootstrap (defs + Jackett + Prowlarr if configured)
            bootstrap_after_setup(background=True, force_defs=False)
        elif getattr(_s, "cardigann_auto_sync_on_startup", True):
            from app.services.definition_sync import ensure_seed_definitions
            ensure_seed_definitions()
        try:
            from app.services.bootstrap import load_runtime_settings_from_db
            load_runtime_settings_from_db()
        except Exception as _le:
            log.debug("runtime settings load: %s", _le)
        # Jackett list sync on startup when enabled
        if getattr(_s, "jackett_sync_on_startup", True) and (getattr(_s, "jackett_url", None) or "").strip():
            from app.scheduler import run_jackett_sync
            try:
                run_jackett_sync()
            except Exception as je:
                log.debug("jackett startup sync: %s", je)
    except Exception as _e:
        log.warning("startup bootstrap: %s", _e)
    log.info("mediaos v%s started", get_version())


@app.get("/api/health")
def health():
    db_ok = False
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_ok = True
        finally:
            db.close()
    except Exception as exc:
        log.warning("Health DB check failed: %s", exc)

    from app.clients.flaresolverr import flaresolverr_client
    from app.services.vpn import get_vpn_status

    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "version": get_version(),
        "auth_required": _auth_enabled(),
        "flaresolverr": flaresolverr_client.get_status(),
        "vpn": get_vpn_status(),
        "features": [
            "movies",
            "tv",
            "music",
            "books",
            "audiobooks",
            "livetv",
            "games",
            "scrobbling",
            "unified-tracking",
            "dvr",
            "discover",
            "quality-profiles",
            "manual-import",
            "upgrade-on-better",
            "season-packs",
            "search-all-missing",
            "fail-blocklist",
            "apprise",
            "jellyfin-refresh",
            "opensubtitles",
            "hardlink-organize",
            "trash-guide-sync",
            "auth-basic",
            "auth-api-key",
            "auth-bearer",
            "auth-multi-user",
            "flaresolverr",
            "movie-profile-picker",
            "book-organize",
            "audiobook-organize",
            "audiobooks-ui",
            "admin-guards",
            "vpn",
            "strm-mode",
            "quality-profile-editor",
            "music-path-trust",
            "readarr-authors",
            "jdupes",
            "unpack",
            "cross-seed",
            "lunasea-api",
            "jellyseerr",
            "ui-collage",
            "wanted-missing",
            "library-watch",
            "deeper-scoring",
            "multi-subs",
            "setup-wizard",
            "mobile-ui",
            "mediaos-parity",
            "usenet-sab",
            "real-debrid",
            "trakt",
            "delay-profiles",
            "workers",
            "inotify-watch",
            "epg-guide",
            "stalker-iptv",
            "stream-providers",
            "usenet-stream",
            "cf-bypass-builtin",
            "better-auth-sessions",
            "full-setup-wizard",
            "mobile-first-ui",
            "delay-enforced",
            "six-sub-providers",
            "dictionarry-factors",
            "audnexus",
            "indexer-manager",
            "builtin-torznab",
            "queue-history",
            "lidarr-discography",
            "subtitle-hi",
            "subtitle-manual",
            "sonarr-rss",
            "smart-lists",
            "calendar",
            "podcasts",
            "movie-collections",
            "native-requests",
            "comics",
            "manga",
            "youtube-creators",
            "podcast-chapters",
            "builtin-1337x-tpb",
            "collection-dashboard",
            "cardigann",
            "quality-profiles-all-media",
            "comics-detail-ui",
            "builtin-media-player",
            "file-converter",
            "games-interactive-search",
            "games-grab-queue",
            "dashboard-widgets-v2",
            "schema-migrations",
            "continue-watching",
            "homelab-links",
            "tmdb-tv-path",
            "games-organize",
            "diagnostics",
            "homelab-health",
            "backup-restore",
        ],
    }


try:
    app.mount("/docs", StaticFiles(directory="docs", html=True), name="docs")
except Exception:
    pass
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
