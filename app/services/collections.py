"""Movie Collections / Sagas — TMDb collection grouping with auto-add-all.

Not present in MediaOs or any arr-ecosystem app: track a saga (MCU, Bond,
Toy Story...) as a single unit, see ownership progress, and pull in every
part with one call.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.clients.tmdb import tmdb_client
from app.models import Collection, ItemStatus, MediaItem, MediaType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def track_collection(db: Session, tmdb_id: int, *, monitored: bool = True) -> Collection:
    """Create (or refresh) a tracked Collection row from TMDb."""
    row = db.query(Collection).filter(Collection.tmdb_id == tmdb_id).first()
    data = tmdb_client.get_collection(tmdb_id)
    if row is None:
        row = Collection(
            tmdb_id=tmdb_id,
            name=data["name"],
            overview=data.get("overview"),
            poster_path=data.get("poster_path"),
            monitored=monitored,
        )
        db.add(row)
    else:
        row.name = data["name"]
        row.overview = data.get("overview")
        row.poster_path = data.get("poster_path")

    row.total_parts = len(data.get("parts", []))
    row.last_synced_at = _utcnow()
    db.commit()
    db.refresh(row)
    return row


def add_all_movies(db: Session, collection: Collection, *, monitored: bool = True) -> dict:
    """Add every part of a collection to the library as a movie MediaItem,
    linking it back to the collection. Skips parts already present."""
    data = tmdb_client.get_collection(collection.tmdb_id)
    collection.total_parts = len(data.get("parts", []))

    added, linked, skipped = [], [], 0
    for part in data.get("parts", []):
        existing = (
            db.query(MediaItem)
            .filter(
                MediaItem.media_type == MediaType.movie,
                MediaItem.external_id == part["external_id"],
            )
            .first()
        )
        if existing:
            if existing.collection_id != collection.id:
                existing.collection_id = collection.id
                db.add(existing)
                linked.append(existing.title)
            else:
                skipped += 1
            continue

        item = MediaItem(
            media_type=MediaType.movie,
            external_id=part["external_id"],
            external_source="tmdb",
            title=part.get("title") or "Unknown",
            year=part.get("year"),
            overview=part.get("overview"),
            poster_path=part.get("poster_path"),
            monitored=monitored,
            status=ItemStatus.wanted,
            quality_profile=collection.quality_profile,
            collection_id=collection.id,
        )
        db.add(item)
        added.append(item.title)

    db.commit()
    return {
        "collection": collection.name,
        "added": len(added),
        "linked_existing": len(linked),
        "already_tracked": skipped,
        "titles_added": added,
    }


def collection_progress(db: Session, collection: Collection) -> dict:
    movies = (
        db.query(MediaItem)
        .filter(MediaItem.collection_id == collection.id)
        .order_by(MediaItem.year)
        .all()
    )
    owned = sum(1 for m in movies if m.status == ItemStatus.downloaded)
    return {
        "id": collection.id,
        "tmdb_id": collection.tmdb_id,
        "name": collection.name,
        "overview": collection.overview,
        "poster_path": collection.poster_path,
        "monitored": collection.monitored,
        "total_parts": collection.total_parts,
        "owned": owned,
        "tracked": len(movies),
        "progress_label": f"{owned}/{collection.total_parts or len(movies)}",
        "movies": [
            {
                "id": m.id,
                "title": m.title,
                "year": m.year,
                "status": m.status.value if hasattr(m.status, "value") else m.status,
                "poster_path": m.poster_path,
                "monitored": m.monitored,
            }
            for m in movies
        ],
    }
