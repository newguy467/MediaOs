from sqlalchemy.orm import Session

from app.models import Blocklist
from app.services.activity import log_activity


def add_to_blocklist(
    db: Session,
    release_title: str,
    *,
    reason: str | None = None,
    torrent_hash: str | None = None,
    media_item_id: int | None = None,
) -> Blocklist:
    row = Blocklist(
        release_title=release_title,
        torrent_hash=torrent_hash,
        reason=reason,
        media_item_id=media_item_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_activity(
        db,
        "blocked",
        f"Blocklisted: {release_title}" + (f" ({reason})" if reason else ""),
        media_item_id=media_item_id,
        release_title=release_title,
    )
    return row



