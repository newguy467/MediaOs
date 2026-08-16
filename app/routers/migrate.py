"""Import libraries from Sonarr / Radarr APIs + TRaSH quality profiles."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db

router = APIRouter(prefix="/migrate", tags=["migrate"])


class ArrSource(BaseModel):
    url: str
    api_key: str
    monitor: bool = True


class TrashImportIn(BaseModel):
    url: str | None = None
    data: Any | None = None  # raw JSON body alternative
    profile_name: str = "TRaSH Imported"
    media_type: str = "movie"  # movie | tv
    replace_formats: bool = True


@router.post("/radarr")
def migrate_radarr(payload: ArrSource, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    from app.services.arr_migrator import migrate_radarr as do
    try:
        return do(db, url=payload.url, api_key=payload.api_key, monitor=payload.monitor)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@router.post("/sonarr")
def migrate_sonarr(payload: ArrSource, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    from app.services.arr_migrator import migrate_sonarr as do
    try:
        return do(db, url=payload.url, api_key=payload.api_key, monitor=payload.monitor)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@router.post("/trash")
def import_trash(payload: TrashImportIn, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    from app.services.trash_import import import_trash_payload
    try:
        if payload.url:
            # URL-based fetch-and-import was never implemented in
            # app.services.trash_import (only raw-payload import exists) —
            # fail clearly instead of the previous hard ImportError/500.
            raise HTTPException(
                400,
                "Trash import by URL is not supported — fetch the JSON yourself "
                "and POST it as `data` instead.",
            )
        if payload.data is not None:
            return import_trash_payload(payload.data)
        raise HTTPException(400, "Provide url or data")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@router.get("/trash/presets")
def trash_presets():
    # No preset guide URLs are defined anywhere in this codebase (this
    # previously imported two nonexistent constants and 500'd on every
    # call). Only raw-payload import via POST /migrate/trash is supported.
    return {
        "movie_hd_bluray_web": None,
        "tv_hd_bluray_web": None,
        "notes": "No built-in preset URLs — paste a TRaSH custom-format JSON export via POST /migrate/trash instead.",
    }


class DbMigrateIn(BaseModel):
    path: str | None = None  # sqlite file path
    postgres_url: str | None = None
    kind: str = "radarr"  # radarr | sonarr


@router.post("/db")
def migrate_from_db(payload: DbMigrateIn, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    """Offline migrator: Sonarr/Radarr SQLite file or Postgres connection string."""
    from app.services.arr_db_migrator import (
        migrate_radarr_sqlite,
        migrate_sonarr_sqlite,
        migrate_arr_postgres,
    )
    try:
        if payload.path:
            if payload.kind == "sonarr":
                base = migrate_sonarr_sqlite(db, payload.path)
                try:
                    from app.services.arr_db_migrator import migrate_sonarr_extras_sqlite
                    base["extras"] = migrate_sonarr_extras_sqlite(db, payload.path)
                except Exception as e:
                    base["extras_error"] = str(e)
                return base
            base = migrate_radarr_sqlite(db, payload.path)
            try:
                from app.services.arr_db_migrator import migrate_radarr_extras_sqlite
                base["extras"] = migrate_radarr_extras_sqlite(db, payload.path)
            except Exception as e:
                base["extras_error"] = str(e)
            return base
        if payload.postgres_url:
            return migrate_arr_postgres(db, url=payload.postgres_url, kind=payload.kind)
        raise HTTPException(400, "Provide path (sqlite) or postgres_url")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e)) from e



class ArrTestIn(BaseModel):
    url: str
    api_key: str
    kind: str = "sonarr"


@router.post("/test")
def test_arr(payload: ArrTestIn, _: str = Depends(require_admin)):
    from app.services.arr_migrator import test_arr_connection
    return test_arr_connection(payload.url, payload.api_key, payload.kind)


@router.post("/lidarr")
def migrate_lidarr(payload: ArrSource, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    from app.services.arr_migrator import migrate_lidarr as do
    try:
        return do(db, url=payload.url, api_key=payload.api_key, monitor=payload.monitor)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


class ReadarrSource(ArrSource):
    audiobooks: bool = False


@router.post("/readarr")
def migrate_readarr(payload: ReadarrSource, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    from app.services.arr_migrator import migrate_readarr as do
    try:
        return do(db, url=payload.url, api_key=payload.api_key, monitor=payload.monitor, audiobooks=payload.audiobooks)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@router.post("/prowlarr/indexers")
def sync_prowlarr(payload: ArrSource, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    from app.services.arr_migrator import sync_prowlarr_indexers
    try:
        return sync_prowlarr_indexers(db, url=payload.url, api_key=payload.api_key)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@router.get("/supported")
def supported_arrs():
    return {
        "apps": [
            {"id": "radarr", "name": "Radarr", "media": "movies", "api": "v3", "import": True, "compat": True},
            {"id": "sonarr", "name": "Sonarr", "media": "tv", "api": "v3", "import": True, "compat": True},
            {"id": "lidarr", "name": "Lidarr", "media": "music", "api": "v1", "import": True, "compat": False},
            {"id": "readarr", "name": "Readarr", "media": "books", "api": "v1", "import": True, "compat": False},
            {"id": "prowlarr", "name": "Prowlarr", "media": "indexers", "api": "v1", "import": True, "compat": False},
            {"id": "bazarr", "name": "Bazarr", "media": "subtitles", "api": "—", "import": False, "compat": "partial (built-in subtitles)"},
            {"id": "whisparr", "name": "Whisparr", "media": "adult", "api": "v3", "import": False, "compat": "via movie API subset"},
        ],
        "notes": "Import pulls library into mediaos so you can retire the *arr. Compat means Jellyseerr/Overseerr/LunaSea can talk to mediaos as if it were that app.",
    }


@router.post("/backfill-provider-ids")
def backfill_provider_ids(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    """One-shot: copy external_id into imdb_id/tvdb_id when external_source is known."""
    from app.models import MediaItem
    updated = 0
    rows = db.query(MediaItem).all()
    for item in rows:
        changed = False
        src = (item.external_source or "").lower()
        if src in ("tvdb", "tvdb.com") and item.external_id and not item.tvdb_id:
            item.tvdb_id = int(item.external_id)
            changed = True
        if src in ("imdb",) and item.external_id and not item.imdb_id:
            eid = str(item.external_id)
            item.imdb_id = eid if eid.startswith("tt") else f"tt{eid}"
            changed = True
        # external_ids JSON seed
        if not item.external_ids and item.external_id:
            import json
            blob = {}
            if src in ("tmdb", "", "none") or src is None:
                blob["tmdb"] = item.external_id
            if src == "tvdb" or item.tvdb_id:
                blob["tvdb"] = item.tvdb_id or item.external_id
            if item.imdb_id:
                blob["imdb"] = item.imdb_id
            if blob:
                item.external_ids = json.dumps(blob)
                changed = True
        if changed:
            db.add(item)
            updated += 1
    db.commit()
    return {"ok": True, "updated": updated, "scanned": len(rows)}


class ArrValidateIn(BaseModel):
    url: str
    api_key: str
    kind: str = "sonarr"


@router.post("/validate")
def validate_arr(payload: ArrValidateIn, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    """Pre-flight: connection + library shape + side-by-side vs MediaOS (no writes)."""
    from app.services.arr_validation import full_preflight
    try:
        return full_preflight(db, payload.url, payload.api_key, payload.kind)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@router.post("/validate/connection")
def validate_arr_connection(payload: ArrValidateIn, _: str = Depends(require_admin)):
    from app.services.arr_validation import validate_connection
    return validate_connection(payload.url, payload.api_key, payload.kind)


@router.post("/validate/side-by-side")
def validate_arr_side_by_side(payload: ArrValidateIn, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    from app.services.arr_validation import side_by_side
    try:
        return side_by_side(db, payload.url, payload.api_key, payload.kind)
    except Exception as e:
        raise HTTPException(400, str(e)) from e

