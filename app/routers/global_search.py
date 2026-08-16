"""Global search — searches the LOCAL library across all media types.

Distinct from each module's GET /api/<module>/search (movies.py, tv.py,
music.py, books.py, comics.py, audiobooks.py), which hits external metadata
providers (TMDB, MusicBrainz, OpenLibrary, ComicVine/MangaDex) to find new
things to add. This endpoint only looks at what's already in the library
(MediaItem, plus the separate Game table).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database import get_db
from app.models import MediaItem, MediaType

router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(require_permission("library.view"))],
)

# Kept in sync with app/services/dashboard_widgets.CONTINUE_PAGE_MAP — both
# map a media_type value to the frontend page slug + a display label.
MODULE_MAP: dict[MediaType, tuple[str, str]] = {
    MediaType.movie: ("movies", "Movies"),
    MediaType.tv: ("tv", "TV"),
    MediaType.music: ("music", "Music"),
    MediaType.book: ("books", "Books"),
    MediaType.audiobook: ("audiobooks", "Audiobooks"),
    MediaType.comic: ("comics", "Comics"),
    MediaType.manga: ("manga", "Manga"),
    MediaType.adult: ("adult", "Adult"),
}


@router.get("")
def global_search(
    query: str = Query(..., min_length=1),
    limit: int = Query(6, le=25),
    db: Session = Depends(get_db),
):
    q = (query or "").strip()
    if not q:
        return {"query": q, "groups": [], "total": 0}
    like = f"%{q}%"
    groups: list[dict] = []
    total = 0
    for mt, (page, label) in MODULE_MAP.items():
        rows = (
            db.query(MediaItem)
            .filter(
                MediaItem.media_type == mt,
                (MediaItem.title.ilike(like)) | (MediaItem.artist_name.ilike(like)),
            )
            .order_by(MediaItem.title)
            .limit(limit)
            .all()
        )
        if not rows:
            continue
        items = [
            {
                "id": r.id,
                "title": r.title,
                "subtitle": r.artist_name if mt == MediaType.music else (str(r.year) if r.year else None),
                "year": r.year,
                "poster_path": r.poster_path,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "media_type": mt.value,
                "page": page,
            }
            for r in rows
        ]
        groups.append({"media_type": mt.value, "label": label, "page": page, "items": items})
        total += len(items)

    # Games live in a separate table, not MediaItem. Wrapped defensively in
    # case a given install hasn't migrated/enabled the games module.
    try:
        from app.models import Game

        game_rows = (
            db.query(Game)
            .filter(Game.title.ilike(like))
            .order_by(Game.title)
            .limit(limit)
            .all()
        )
        if game_rows:
            items = [
                {
                    "id": g.id,
                    "title": g.title,
                    "subtitle": str(g.year) if g.year else None,
                    "year": g.year,
                    "poster_path": g.poster_path,
                    "status": g.status,
                    "media_type": "game",
                    "page": "games",
                }
                for g in game_rows
            ]
            groups.append({"media_type": "game", "label": "Games", "page": "games", "items": items})
            total += len(items)
    except Exception:
        pass

    return {"query": q, "groups": groups, "total": total}
