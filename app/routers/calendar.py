"""Calendar — TV air dates + movie releases (Prismarr-dense)."""
from __future__ import annotations

from datetime import date, timedelta

from app.auth import require_permission
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Episode, ItemStatus, MediaItem, MediaType

router = APIRouter(
    prefix="/calendar",
    tags=["calendar"],
    dependencies=[Depends(require_permission("calendar.view", "library.view"))],
)


class CalendarItem(BaseModel):
    air_date: str
    kind: str = "episode"  # episode | movie
    series_id: int | None = None
    series_title: str | None = None
    episode_id: int | None = None
    season_number: int | None = None
    episode_number: int | None = None
    episode_title: str | None = None
    movie_id: int | None = None
    movie_title: str | None = None
    status: str
    monitored: bool
    has_file: bool
    poster_path: str | None = None
    year: int | None = None


@router.get("", response_model=list[CalendarItem])
def get_calendar(
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None, description="YYYY-MM-DD"),
    days: int = Query(30, ge=1, le=90),
    include_movies: bool = Query(True),
    db: Session = Depends(get_db),
):
    today = date.today()
    if start:
        try:
            start_d = date.fromisoformat(start)
        except ValueError:
            start_d = today - timedelta(days=7)
    else:
        start_d = today - timedelta(days=7)

    if end:
        try:
            end_d = date.fromisoformat(end)
        except ValueError:
            end_d = today + timedelta(days=days)
    else:
        end_d = today + timedelta(days=days)

    start_s = start_d.isoformat()
    end_s = end_d.isoformat()

    out: list[CalendarItem] = []

    rows = (
        db.query(Episode)
        .join(MediaItem)
        .options(joinedload(Episode.series))
        .filter(
            MediaItem.media_type == MediaType.tv,
            Episode.air_date.isnot(None),
            Episode.air_date >= start_s,
            Episode.air_date <= end_s,
        )
        .order_by(Episode.air_date, MediaItem.title, Episode.season_number, Episode.episode_number)
        .all()
    )

    for ep in rows:
        series = ep.series
        if not series:
            continue
        out.append(
            CalendarItem(
                air_date=ep.air_date or "",
                kind="episode",
                series_id=series.id,
                series_title=series.title,
                episode_id=ep.id,
                season_number=ep.season_number,
                episode_number=ep.episode_number,
                episode_title=ep.title,
                status=ep.status.value if ep.status else "unknown",
                monitored=bool(ep.monitored),
                has_file=bool(ep.file_path),
                poster_path=series.poster_path,
                year=series.year,
            )
        )

    if include_movies:
        # Movies with year in range approximate: use added_at date or year-only as Jan 1
        movies = (
            db.query(MediaItem)
            .filter(MediaItem.media_type == MediaType.movie, MediaItem.monitored.is_(True))
            .all()
        )
        for m in movies:
            # Prefer a stored release-ish date if present in overview isn't reliable;
            # use added_at date when it falls in window, else skip dense movie noise.
            if m.added_at:
                ad = m.added_at.date() if hasattr(m.added_at, "date") else None
                if ad and start_d <= ad <= end_d:
                    out.append(
                        CalendarItem(
                            air_date=ad.isoformat(),
                            kind="movie",
                            movie_id=m.id,
                            movie_title=m.title,
                            status=m.status.value if m.status else "unknown",
                            monitored=bool(m.monitored),
                            has_file=bool(m.file_path),
                            poster_path=m.poster_path,
                            year=m.year,
                        )
                    )

    out.sort(key=lambda x: (x.air_date, x.kind, x.series_title or x.movie_title or ""))
    return out
