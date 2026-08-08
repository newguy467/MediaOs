from app.services.sse import publish as sse_publish
from sqlalchemy.orm import Session

from app.models import Activity


# Events that also push Discord / Telegram / Apprise (avoid spam on high-frequency noise)
_NOTIFY_EVENTS = frozenset({
    "grabbed", "grab", "organized", "download", "downloaded",
    "failed", "failure", "import", "imported",
    "request", "request_approved", "request_denied",
    "upgrade", "blocklist", "migrate", "migrate_radarr", "migrate_sonarr",
    "cleanup", "convert", "converted", "subtitle",
})


def log_activity(
    db: Session,
    event: str,
    message: str,
    *,
    media_type: str | None = None,
    media_item_id: int | None = None,
    release_title: str | None = None,
    notify: bool | None = None,
) -> None:
    row = Activity(
        event=event,
        message=message,
        media_type=media_type,
        media_item_id=media_item_id,
        release_title=release_title,
    )
    db.add(row)
    db.commit()
    try:
        sse_publish("activity", {"event": event, "message": message, "media_item_id": media_item_id})
    except Exception:
        pass
    # Fan-out notifications for important lifecycle events
    should = notify if notify is not None else (event in _NOTIFY_EVENTS)
    if should:
        try:
            from app.services.hooks import notify_event
            notify_event(event, message)
        except Exception:
            pass
