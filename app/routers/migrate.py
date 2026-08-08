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
    from app.services.trash_import import import_trash_from_url, import_trash_into_profile
    try:
        if payload.url:
            return import_trash_from_url(
                db,
                payload.url,
                profile_name=payload.profile_name,
                media_type=payload.media_type,
                replace_formats=payload.replace_formats,
            )
        if payload.data is not None:
            return import_trash_into_profile(
                db,
                data=payload.data,
                profile_name=payload.profile_name,
                media_type=payload.media_type,
                replace_formats=payload.replace_formats,
            )
        raise HTTPException(400, "Provide url or data")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@router.get("/trash/presets")
def trash_presets():
    from app.services.trash_import import TRASH_CF_MOVIE_URL, TRASH_CF_TV_URL
    return {
        "movie_hd_bluray_web": TRASH_CF_MOVIE_URL,
        "tv_hd_bluray_web": TRASH_CF_TV_URL,
        "notes": "Paste any TRaSH custom format JSON or formatItems export; URLs may move — prefer local paste if fetch fails.",
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
