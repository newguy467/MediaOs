"""
Import tracking data from Trakt / MAL / AniList / Steam (Yamtrack-inspired).

POST /api/tracking/import/trakt
POST /api/tracking/import/mal
POST /api/tracking/import/anilist
POST /api/tracking/import/steam
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database import get_db
from app.models import TrackedItem, TrackingHistory, MediaItem, Game, MediaType

log = logging.getLogger("mediaos.import_tracking")
router = APIRouter(prefix="/tracking/import", tags=["tracking-import"])


def _stable_int_id(key: str) -> int:
    """Deterministic string -> int id, stable across process restarts.

    Same fix pattern as app/clients/openlibrary.py / audnexus.py /
    app/services/arr_migrator.py — Python's built-in hash() is per-process
    salted for str objects, so it must not be used for anything persisted
    and looked up again later (external_id here).
    """
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % 10_000_000


class ImportBody(BaseModel):
    items: list[dict] = []
    # each item: {title, status?, rating?, media_type?, year?, external_id?, progress?}


def _status_map(s: str) -> str:
    s = (s or "planned").lower().replace(" ", "_")
    mapping = {
        "watching": "in_progress",
        "completed": "completed",
        "complete": "completed",
        "dropped": "dropped",
        "on_hold": "on_hold",
        "paused": "on_hold",
        "plantowatch": "planned",
        "plan_to_watch": "planned",
        "want": "planned",
        "playing": "in_progress",
        "played": "completed",
        "beaten": "completed",
    }
    return mapping.get(s, s if s in ("planned", "in_progress", "completed", "dropped", "on_hold", "repeating") else "planned")


def _import_items(db: Session, items: list[dict], source: str) -> dict:
    created = updated = 0
    for raw in items:
        title = (raw.get("title") or raw.get("name") or "").strip()
        if not title:
            continue
        status = _status_map(raw.get("status") or "planned")
        rating = raw.get("rating") or raw.get("score")
        try:
            rating = float(rating) if rating is not None else None
        except Exception:
            rating = None
        progress = float(raw.get("progress") or raw.get("progress_percent") or 0)
        mt = (raw.get("media_type") or "movie").lower()
        media_item_id = None
        game_id = None
        if mt in ("game", "games"):
            g = db.query(Game).filter(Game.title.ilike(title)).first()
            if not g:
                g = Game(title=title, year=raw.get("year"), monitored=False, status="wanted")
                db.add(g)
                db.flush()
            game_id = g.id
        else:
            q = db.query(MediaItem).filter(MediaItem.title.ilike(title))
            mi = q.first()
            if not mi:
                # lightweight stub row so tracking has a target
                try:
                    mtype = MediaType.movie if mt in ("movie", "film") else MediaType.tv if mt in ("tv", "show", "anime") else MediaType.movie
                    mi = MediaItem(
                        media_type=mtype,
                        external_id=int(raw.get("external_id") or raw.get("tmdb_id") or _stable_int_id(title)),
                        external_source=source,
                        title=title,
                        year=raw.get("year"),
                        monitored=False,
                    )
                    db.add(mi)
                    db.flush()
                except Exception as e:
                    log.debug("skip create media: %s", e)
                    continue
            media_item_id = mi.id

        existing = None
        if media_item_id:
            existing = db.query(TrackedItem).filter(TrackedItem.media_item_id == media_item_id).first()
        elif game_id:
            existing = db.query(TrackedItem).filter(TrackedItem.game_id == game_id).first()

        if existing:
            existing.status = status
            if rating is not None:
                existing.rating = rating
            existing.progress_percent = progress
            updated += 1
            tid = existing.id
        else:
            t = TrackedItem(
                media_item_id=media_item_id,
                game_id=game_id,
                status=status,
                rating=rating,
                progress_percent=progress,
            )
            db.add(t)
            db.flush()
            tid = t.id
            created += 1
        db.add(TrackingHistory(
            tracked_item_id=tid,
            media_item_id=media_item_id,
            game_id=game_id,
            action="imported",
            detail=f"source={source}; status={status}",
        ))
    db.commit()
    return {"ok": True, "source": source, "created": created, "updated": updated, "total": created + updated}


@router.post("/trakt")
def import_trakt(body: ImportBody, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Accept pre-fetched Trakt watchlist/history rows as JSON items."""
    return _import_items(db, body.items, "trakt")


@router.post("/mal")
def import_mal(body: ImportBody, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    return _import_items(db, body.items, "mal")


@router.post("/anilist")
def import_anilist(body: ImportBody, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    return _import_items(db, body.items, "anilist")


@router.post("/steam")
def import_steam(body: ImportBody, db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """Steam games as tracking + Game rows (playtime in progress_percent crude map)."""
    items = []
    for raw in body.items:
        playtime = raw.get("playtime_forever") or raw.get("playtime_minutes") or 0
        items.append({
            "title": raw.get("name") or raw.get("title"),
            "media_type": "game",
            "status": "completed" if playtime and int(playtime) > 600 else "in_progress" if playtime else "planned",
            "progress": min(100.0, float(playtime) / 60.0) if playtime else 0,  # rough
            "external_id": raw.get("appid") or raw.get("external_id"),
        })
    return _import_items(db, items, "steam")


@router.post("/trakt/pull")
def trakt_pull(db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    """One-click pull watchlist + history from Trakt (requires TRAKT_ACCESS_TOKEN)."""
    from app.clients.trakt import trakt_client
    items = []
    items.extend(trakt_client.watchlist("movies"))
    items.extend(trakt_client.watchlist("shows"))
    items.extend(trakt_client.history("movies", limit=40))
    items.extend(trakt_client.history("shows", limit=40))
    if not items:
        return {"ok": False, "error": "No items — set TRAKT_CLIENT_ID + TRAKT_ACCESS_TOKEN", "total": 0}
    return _import_items(db, items, "trakt")


@router.post("/steam/pull")
def steam_pull(db: Session = Depends(get_db), _=Depends(require_permission("library"))):
    from app.clients import steam
    games = steam.owned_games()
    if not games:
        return {"ok": False, "error": "No games — set STEAM_API_KEY + STEAM_ID", "total": 0}
    return _import_items(db, games, "steam")
