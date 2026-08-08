"""Jellyfin-compatible rename / folder structure tools."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import Episode, MediaItem, MediaType
from app.services import naming as naming_svc

log = logging.getLogger(__name__)
router = APIRouter(prefix="/library", tags=["library"])


class RenamePreview(BaseModel):
    item_id: int
    episode_id: int | None = None


class RenameApply(BaseModel):
    item_id: int
    episode_id: int | None = None
    dry_run: bool = False


def _movie_target(item: MediaItem) -> tuple[Path, Path] | None:
    if not item.file_path:
        return None
    src = Path(item.file_path)
    if not src.exists():
        return None
    from app.config import settings
    lib = Path(settings.movies_library_path or "/movies")
    folder = naming_svc.movie_folder(item.title, item.year, tmdb_id=item.external_id if item.external_source == "tmdb" else None)
    dest_dir = lib / folder
    dest = dest_dir / f"{naming_svc.movie_file(item.title, item.year)}{src.suffix}"
    return src, dest


def _episode_target(series: MediaItem, ep: Episode) -> tuple[Path, Path] | None:
    if not ep.file_path:
        return None
    src = Path(ep.file_path)
    if not src.exists():
        return None
    from app.config import settings
    lib = Path(settings.tv_library_path or "/tv")
    folder = naming_svc.series_folder(series.title, series.year, tmdb_id=series.external_id if series.external_source == "tmdb" else None)
    dest_dir = lib / folder / naming_svc.season_folder(ep.season_number or 0)
    stem = naming_svc.episode_file(series.title, ep.season_number or 0, ep.episode_number or 0, ep.title)
    dest = dest_dir / f"{stem}{src.suffix}"
    return src, dest


@router.post("/rename/preview")
def rename_preview(payload: RenamePreview, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    item = db.get(MediaItem, payload.item_id)
    if not item:
        raise HTTPException(404, "Not found")
    if payload.episode_id:
        ep = db.get(Episode, payload.episode_id)
        if not ep or ep.series_id != item.id:
            raise HTTPException(404, "Episode not found")
        pair = _episode_target(item, ep)
    else:
        pair = _movie_target(item)
    if not pair:
        return {"ok": False, "error": "No file on disk"}
    src, dest = pair
    return {
        "ok": True,
        "from": str(src),
        "to": str(dest),
        "needs_move": src.resolve() != dest.resolve(),
        "jellyfin_compatible": True,
    }


@router.post("/rename/apply")
def rename_apply(payload: RenameApply, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    item = db.get(MediaItem, payload.item_id)
    if not item:
        raise HTTPException(404, "Not found")
    ep = None
    if payload.episode_id:
        ep = db.get(Episode, payload.episode_id)
        if not ep or ep.series_id != item.id:
            raise HTTPException(404, "Episode not found")
        pair = _episode_target(item, ep)
    else:
        pair = _movie_target(item)
    if not pair:
        raise HTTPException(400, "No file on disk")
    src, dest = pair
    if payload.dry_run:
        return {"ok": True, "dry_run": True, "from": str(src), "to": str(dest)}
    if src.resolve() == dest.resolve():
        return {"ok": True, "moved": False, "path": str(src)}
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    if ep:
        ep.file_path = str(dest)
        db.add(ep)
    else:
        item.file_path = str(dest)
        db.add(item)
    db.commit()
    log.info("Renamed %s → %s", src, dest)
    return {"ok": True, "moved": True, "from": str(src), "to": str(dest)}


@router.get("/naming/templates")
def naming_templates():
    """Document Jellyfin-compatible templates."""
    return {
        "jellyfin": {
            "movie_folder": naming_svc.JELLYFIN_MOVIE_FOLDER,
            "movie_example": "The Matrix (1999)/The Matrix (1999).mkv",
            "series_folder": naming_svc.JELLYFIN_SERIES_FOLDER,
            "season_folder": "Season 01",
            "episode_file": naming_svc.JELLYFIN_EPISODE,
            "episode_example": "Breaking Bad (2008)/Season 01/Breaking Bad - S01E01 - Pilot.mkv",
            "music": "Artist/Album (Year)/01 - Track.mp3",
            "books": "Author/Title (Year)/",
        },
        "notes": "MediaOs organize uses these templates by default. TMDB/TVDB IDs may be appended as {tmdb-123} for *arr parity; Jellyfin ignores unknown braces.",
    }
