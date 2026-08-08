"""Stream-without-download (.strm) helpers — Cinephage-inspired."""
from __future__ import annotations

from pathlib import Path
from sqlalchemy.orm import Session

from app.config import settings
from app.models import StreamLink


def write_strm_file(strm_path: str, url: str) -> str:
    p = Path(strm_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(url.strip() + "\n", encoding="utf-8")
    return str(p)


def create_stream_link(
    db: Session,
    *,
    title: str,
    stream_url: str,
    media_item_id: int | None = None,
    episode_id: int | None = None,
    provider: str | None = None,
    library_subdir: str = "streams",
) -> StreamLink:
    base = Path(getattr(settings, "movies_library_path", "/movies")).parent / library_subdir
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:120].strip() or "stream"
    strm_path = str(base / f"{safe}.strm")
    write_strm_file(strm_path, stream_url)
    row = StreamLink(
        title=title,
        stream_url=stream_url,
        strm_path=strm_path,
        media_item_id=media_item_id,
        episode_id=episode_id,
        provider=provider,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_links(db: Session, limit: int = 100) -> list[StreamLink]:
    return db.query(StreamLink).order_by(StreamLink.id.desc()).limit(limit).all()


# --- v4 helpers -------------------------------------------------------------

def stream_option_payload(
    *,
    title: str,
    stream_url: str,
    media_item_id: int | None = None,
    episode_id: int | None = None,
    provider: str | None = None,
) -> dict:
    """
    Shape returned to the UI so detail views and interactive search can show
    an “Add as stream” action next to Grab (Cinephage-inspired primary path).
    """
    return {
        "action": "add_as_stream",
        "title": title,
        "stream_url": stream_url,
        "media_item_id": media_item_id,
        "episode_id": episode_id,
        "provider": provider,
        "label": "Add as stream",
    }
