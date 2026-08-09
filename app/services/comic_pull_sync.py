"""Scheduled comic pull-list sync (Mylar-inspired).

Sources (in order):
  1. ComicVine new issues for monitored comic series (if COMICVINE_API_KEY set)
  2. Local comic_issues with cover_date in the next N days for monitored volumes
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ComicIssue, ComicPullList, ItemStatus, MediaItem, MediaType

log = logging.getLogger("mediaos.comic_pull")
CV_API = "https://comicvine.gamespot.com/api"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _cv_headers() -> dict:
    return {"User-Agent": "MediaOs/3.7 (pull-list sync)"}


def sync_from_local_issues(db: Session, *, days_ahead: int = 21) -> dict[str, Any]:
    """Add pull-list rows from monitored comic volumes' issues with near-term cover dates."""
    today = _utcnow().date()
    end = today + timedelta(days=days_ahead)
    volumes = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.comic, MediaItem.monitored.is_(True))
        .all()
    )
    added = 0
    scanned = 0
    for vol in volumes:
        issues = db.query(ComicIssue).filter(ComicIssue.media_item_id == vol.id).all()
        for iss in issues:
            scanned += 1
            cd = (iss.cover_date or "")[:10]
            if not cd or len(cd) < 8:
                continue
            try:
                d = datetime.strptime(cd[:10], "%Y-%m-%d").date()
            except Exception:
                continue
            if d < today - timedelta(days=3) or d > end:
                continue
            exists = (
                db.query(ComicPullList)
                .filter(
                    ComicPullList.series_name == vol.title,
                    ComicPullList.issue_number == (iss.issue_number or ""),
                )
                .first()
            )
            if exists:
                continue
            db.add(ComicPullList(
                series_name=vol.title,
                issue_number=iss.issue_number,
                publisher=None,
                release_date=cd[:10],
                comicvine_id=iss.external_id if (iss.external_source or "").lower() == "comicvine" else None,
                media_item_id=vol.id,
                watched=True,
                grabbed=bool(iss.file_path) or (iss.status == ItemStatus.downloaded if hasattr(ItemStatus, "downloaded") else False),
            ))
            added += 1
    db.commit()
    return {"source": "local_issues", "scanned": scanned, "added": added}


def sync_from_comicvine(db: Session, *, days_ahead: int = 14) -> dict[str, Any]:
    """Query ComicVine for recent issues of monitored series that have a CV id."""
    key = (getattr(settings, "comicvine_api_key", None) or "").strip()
    if not key:
        return {"source": "comicvine", "skipped": True, "reason": "COMICVINE_API_KEY not set"}

    volumes = (
        db.query(MediaItem)
        .filter(
            MediaItem.media_type == MediaType.comic,
            MediaItem.monitored.is_(True),
            MediaItem.external_source.isnot(None),
        )
        .all()
    )
    added = 0
    errors = []
    checked = 0
    for vol in volumes:
        src = (vol.external_source or "").lower()
        if "comicvine" not in src and src not in ("cv", "comic_vine"):
            # still try if external_id looks usable and source empty-ish
            if src and "comic" not in src:
                continue
        if not vol.external_id:
            continue
        checked += 1
        try:
            # volume issues endpoint
            url = f"{CV_API}/issues/"
            params = {
                "api_key": key,
                "format": "json",
                "filter": f"volume:{vol.external_id}",
                "field_list": "id,name,issue_number,cover_date,volume",
                "limit": 20,
                "sort": "cover_date:desc",
            }
            r = httpx.get(url, params=params, headers=_cv_headers(), timeout=25)
            r.raise_for_status()
            results = (r.json().get("results") or [])
            today = _utcnow().date()
            end = today + timedelta(days=days_ahead)
            for row in results:
                cd = (row.get("cover_date") or "")[:10]
                if not cd:
                    continue
                try:
                    d = datetime.strptime(cd, "%Y-%m-%d").date()
                except Exception:
                    continue
                if d < today - timedelta(days=7) or d > end:
                    continue
                num = str(row.get("issue_number") or "")
                exists = (
                    db.query(ComicPullList)
                    .filter(
                        ComicPullList.series_name == vol.title,
                        ComicPullList.issue_number == num,
                    )
                    .first()
                )
                if exists:
                    continue
                db.add(ComicPullList(
                    series_name=vol.title,
                    issue_number=num,
                    release_date=cd,
                    comicvine_id=row.get("id"),
                    media_item_id=vol.id,
                    watched=True,
                    grabbed=False,
                ))
                added += 1
        except Exception as e:
            errors.append(f"{vol.title}: {e}")
            log.info("comicvine pull sync failed for %s: %s", vol.title, e)
    db.commit()
    return {"source": "comicvine", "checked_volumes": checked, "added": added, "errors": errors[:10]}


def auto_grab_from_pull_list(db: Session, *, limit: int = 15) -> dict[str, Any]:
    """Grab releases for pull-list rows not yet grabbed (rate-limited)."""
    from app.models import ComicPullList, ComicIssue, MediaItem, MediaType
    from app.services.search import search_comic_releases, search_manga_releases
    from app.services.grab import grab_release

    rows = (
        db.query(ComicPullList)
        .filter(ComicPullList.grabbed.is_(False))
        .order_by(ComicPullList.id.asc())
        .limit(max(1, min(limit, 40)))
        .all()
    )
    grabbed = skipped = errors = 0
    for row in rows:
        try:
            item = None
            # Prefer explicit library link
            mid = getattr(row, "media_item_id", None)
            if mid:
                item = db.get(MediaItem, mid)
            # Legacy / optional fields
            if item is None and getattr(row, "issue_id", None):
                iss = db.get(ComicIssue, row.issue_id)
                if iss and getattr(iss, "volume_id", None):
                    item = db.get(MediaItem, iss.volume_id)
            if item is None and getattr(row, "volume_id", None):
                item = db.get(MediaItem, row.volume_id)
            if item is None:
                title = (getattr(row, "title", None) or getattr(row, "series_name", None) or "").strip()
                if title:
                    item = (
                        db.query(MediaItem)
                        .filter(
                            MediaItem.media_type.in_([MediaType.comic, MediaType.manga]),
                            MediaItem.title.ilike(f"%{title[:80]}%"),
                        )
                        .first()
                    )
            if item is None:
                skipped += 1
                continue
            is_manga = item.media_type == MediaType.manga
            releases = (search_manga_releases if is_manga else search_comic_releases)(item, db=db, limit=5)
            if not releases:
                skipped += 1
                continue
            grab_release(db, item, releases[0])
            row.grabbed = True
            db.add(row)
            grabbed += 1
        except Exception as e:
            log.warning("pull auto-grab failed row=%s: %s", getattr(row, "id", None), e)
            errors += 1
            try:
                db.rollback()
            except Exception:
                pass
    try:
        db.commit()
    except Exception:
        db.rollback()
    return {"grabbed": grabbed, "skipped": skipped, "errors": errors, "examined": len(rows)}


def run_pull_list_sync(db: Session | None = None) -> dict[str, Any]:
    """Sync pull list then optionally auto-grab missing issues."""
    own = db is None
    if own:
        from app.database import SessionLocal
        db = SessionLocal()
    try:
        local = sync_from_local_issues(db)
        cv = sync_from_comicvine(db)
        auto = {"grabbed": 0, "skipped": 0, "errors": 0, "examined": 0}
        from app.config import settings
        if getattr(settings, "comic_pull_auto_grab", True):
            auto = auto_grab_from_pull_list(
                db, limit=int(getattr(settings, "comic_pull_auto_grab_limit", 10) or 10)
            )
        return {"local": local, "comicvine": cv, "auto_grab": auto}
    finally:
        if own:
            db.close()
