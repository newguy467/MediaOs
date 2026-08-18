"""
Comics story-arc + reading-order + pull-list helpers (Mylar3-inspired).
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import ComicPullList, ComicStoryArc, ComicStoryArcIssue

log = logging.getLogger("mediaos.comic_arcs")


def list_arcs(db: Session, *, limit: int = 200) -> list[dict[str, Any]]:
    rows = db.query(ComicStoryArc).order_by(ComicStoryArc.name).limit(limit).all()
    out = []
    for a in rows:
        issues = (
            db.query(ComicStoryArcIssue)
            .filter(ComicStoryArcIssue.arc_id == a.id)
            .order_by(ComicStoryArcIssue.reading_order.nullslast(), ComicStoryArcIssue.id)
            .all()
        )
        out.append({
            "id": a.id,
            "name": a.name,
            "comicvine_id": a.comicvine_id,
            "description": a.description,
            "issue_count": a.issue_count or len(issues),
            "issues_linked": len(issues),
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return out


def get_arc(db: Session, arc_id: int) -> dict[str, Any] | None:
    a = db.get(ComicStoryArc, arc_id)
    if not a:
        return None
    issues = (
        db.query(ComicStoryArcIssue)
        .filter(ComicStoryArcIssue.arc_id == arc_id)
        .order_by(ComicStoryArcIssue.reading_order.nullslast(), ComicStoryArcIssue.id)
        .all()
    )
    return {
        "id": a.id,
        "name": a.name,
        "comicvine_id": a.comicvine_id,
        "description": a.description,
        "issue_count": a.issue_count or len(issues),
        "issues": [
            {
                "id": i.id,
                "series_name": i.series_name,
                "issue_number": i.issue_number,
                "reading_order": i.reading_order,
                "media_item_id": i.media_item_id,
                "comic_issue_id": i.comic_issue_id,
            }
            for i in issues
        ],
    }


def create_arc(
    db: Session,
    *,
    name: str,
    description: str | None = None,
    comicvine_id: int | None = None,
    issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    arc = ComicStoryArc(
        name=name.strip(),
        description=description,
        comicvine_id=comicvine_id,
        issue_count=len(issues or []),
    )
    db.add(arc)
    db.flush()
    for idx, iss in enumerate(issues or []):
        db.add(ComicStoryArcIssue(
            arc_id=arc.id,
            series_name=iss.get("series_name") or name,
            issue_number=str(iss.get("issue_number") or "") or None,
            reading_order=iss.get("reading_order", idx + 1),
            media_item_id=iss.get("media_item_id"),
            comic_issue_id=iss.get("comic_issue_id"),
        ))
    db.commit()
    return get_arc(db, arc.id) or {"id": arc.id, "name": arc.name}


def delete_arc(db: Session, arc_id: int) -> bool:
    a = db.get(ComicStoryArc, arc_id)
    if not a:
        return False
    db.query(ComicStoryArcIssue).filter(ComicStoryArcIssue.arc_id == arc_id).delete()
    db.delete(a)
    db.commit()
    return True


def add_issue_to_arc(
    db: Session,
    arc_id: int,
    *,
    series_name: str,
    issue_number: str | None = None,
    reading_order: int | None = None,
    media_item_id: int | None = None,
    comic_issue_id: int | None = None,
) -> dict[str, Any]:
    arc = db.get(ComicStoryArc, arc_id)
    if not arc:
        raise ValueError("arc not found")
    if reading_order is None:
        last = (
            db.query(ComicStoryArcIssue)
            .filter(ComicStoryArcIssue.arc_id == arc_id)
            .order_by(ComicStoryArcIssue.reading_order.desc().nullslast())
            .first()
        )
        reading_order = (last.reading_order or 0) + 1 if last else 1
    row = ComicStoryArcIssue(
        arc_id=arc_id,
        series_name=series_name,
        issue_number=issue_number,
        reading_order=reading_order,
        media_item_id=media_item_id,
        comic_issue_id=comic_issue_id,
    )
    db.add(row)
    arc.issue_count = (arc.issue_count or 0) + 1
    db.add(arc)
    db.commit()
    return get_arc(db, arc_id) or {}


def list_pull(db: Session, *, week: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    q = db.query(ComicPullList).order_by(ComicPullList.release_date.desc().nullslast(), ComicPullList.id.desc())
    if week:
        q = q.filter(ComicPullList.release_date == week)
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id,
            "series_name": r.series_name,
            "issue_number": r.issue_number,
            "publisher": r.publisher,
            "release_date": r.release_date,
            "comicvine_id": r.comicvine_id,
            "media_item_id": r.media_item_id,
            "watched": r.watched,
            "grabbed": r.grabbed,
            "notes": r.notes,
        }
        for r in rows
    ]


def add_pull_item(
    db: Session,
    *,
    series_name: str,
    issue_number: str | None = None,
    publisher: str | None = None,
    release_date: str | None = None,
    comicvine_id: int | None = None,
    watched: bool = True,
) -> dict[str, Any]:
    row = ComicPullList(
        series_name=series_name.strip(),
        issue_number=issue_number,
        publisher=publisher,
        release_date=release_date,
        comicvine_id=comicvine_id,
        watched=watched,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "series_name": row.series_name,
        "issue_number": row.issue_number,
        "publisher": row.publisher,
        "release_date": row.release_date,
        "watched": row.watched,
        "grabbed": row.grabbed,
    }


def set_pull_flags(db: Session, pull_id: int, *, watched: bool | None = None, grabbed: bool | None = None) -> dict[str, Any] | None:
    row = db.get(ComicPullList, pull_id)
    if not row:
        return None
    if watched is not None:
        row.watched = watched
    if grabbed is not None:
        row.grabbed = grabbed
    db.add(row)
    db.commit()
    return {"id": row.id, "watched": row.watched, "grabbed": row.grabbed}


def suggest_metatags(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "series": issue.get("series_name") or issue.get("title"),
        "issue": issue.get("issue_number"),
        "year": issue.get("year"),
        "publisher": issue.get("publisher"),
        "arc": issue.get("arc_name"),
        "arc_number": issue.get("arc_number") or issue.get("reading_order"),
        "summary": issue.get("overview"),
    }


def auto_link_pull_to_arcs(db: Session, pull_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Best-effort: if series_name matches an arc issue, mark linked."""
    pulls = pull_items or list_pull(db, limit=100)
    linked = 0
    for p in pulls:
        match = (
            db.query(ComicStoryArcIssue)
            .filter(ComicStoryArcIssue.series_name == p.get("series_name"))
            .first()
        )
        if match:
            linked += 1
    return {"linked": linked, "scanned": len(pulls)}
