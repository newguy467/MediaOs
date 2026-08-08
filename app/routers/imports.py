"""Manual import from downloads folder."""
from __future__ import annotations

from app.auth import require_permission
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import import_media

router = APIRouter(prefix="/import", tags=["import"])


@router.get("/scan")
def scan_downloads():
    """List video files/folders sitting in the downloads directory."""
    try:
        return import_media.scan_downloads()
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


class MovieImportIn(BaseModel):
    source_path: str
    media_item_id: int | None = None
    title: str | None = None
    year: int | None = None


@router.post("/movie")
def import_movie(payload: MovieImportIn, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    try:
        return import_media.import_to_movie(
            db,
            source_path=payload.source_path,
            media_item_id=payload.media_item_id,
            title=payload.title,
            year=payload.year,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


class EpisodeImportIn(BaseModel):
    source_path: str
    episode_id: int | None = None
    series_id: int | None = None
    season: int | None = None
    episode: int | None = None


@router.post("/episode")
def import_episode(payload: EpisodeImportIn, db: Session = Depends(get_db), _perm: list = Depends(require_permission("library.manage"))):
    try:
        return import_media.import_to_episode(
            db,
            source_path=payload.source_path,
            episode_id=payload.episode_id,
            series_id=payload.series_id,
            season=payload.season,
            episode=payload.episode,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
