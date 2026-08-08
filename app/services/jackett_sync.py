"""Sync Jackett configured indexers into mediaos Indexer rows (Torznab)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.clients.jackett import jackett_client
from app.config import settings
from app.models import Indexer
from app.services.activity import log_activity
from app.services.sse import publish as sse_publish

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sync_jackett_indexers(db: Session, *, enable_new: bool = True) -> dict:
    """
    Pull configured indexers from Jackett and upsert local Torznab Indexer rows.

    - name: Jackett indexer name (unique)
    - url:  Jackett Torznab results URL for that indexer
    - api_key: shared Jackett API key
    - kind: torznab
    """
    if not jackett_client.enabled():
        return {"ok": False, "error": "Jackett not configured", "added": 0, "updated": 0, "total": 0}

    remote = jackett_client.list_indexers()
    key = getattr(settings, "jackett_api_key", None) or ""
    added = updated = skipped = 0
    details: list[dict] = []

    for ix in remote:
        jid = str(ix.get("id") or ix.get("ID") or "").strip()
        name = (ix.get("name") or ix.get("Name") or jid or "").strip()
        if not jid or not name:
            skipped += 1
            continue
        # Prefer configured + healthy
        configured = ix.get("configured", ix.get("Configured", True))
        if configured is False:
            skipped += 1
            continue

        torznab = jackett_client.torznab_url(jid)
        row = db.query(Indexer).filter(Indexer.name == name).first()
        if row is None:
            # also match by URL suffix
            row = (
                db.query(Indexer)
                .filter(Indexer.url.contains(f"/indexers/{jid}/"))
                .first()
            )
        if row is None:
            row = Indexer(
                name=name[:120],
                url=torznab,
                api_key=key,
                kind="torznab",
                enabled=bool(enable_new),
                categories=None,
                priority=25,
                last_ok_at=_utcnow() if (ix.get("status") or ix.get("Status") or 0) == 1 or ix.get("state") == "success" else None,
            )
            db.add(row)
            added += 1
            details.append({"name": name, "action": "added", "id": jid})
        else:
            row.url = torznab
            row.api_key = key
            row.kind = "torznab"
            if (ix.get("status") or ix.get("Status") or 0) == 1 or str(ix.get("state") or "").lower() in ("success", "ok"):
                row.last_ok_at = _utcnow()
                row.last_error = None
            db.add(row)
            updated += 1
            details.append({"name": name, "action": "updated", "id": jid})

    db.commit()
    log_activity(
        db,
        "jackett_sync",
        f"Jackett sync: +{added} ~{updated} (remote {len(remote)})",
    )
    try:
        sse_publish("indexers", {"added": added, "updated": updated, "total": len(remote)})
    except Exception:
        pass
    return {
        "ok": True,
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "remote": len(remote),
        "details": details[:100],
    }
