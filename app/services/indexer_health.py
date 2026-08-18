"""Indexer health monitoring — Prowlarr-style fail tracking / auto-disable."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Indexer

log = logging.getLogger(__name__)


def run_indexer_health_cycle(db: Session) -> dict:
    """Test enabled indexers; record last_ok/last_error; disable after N consecutive fails."""
    # Inline test instead
    from app.clients.torznab import torznab_client
    from app.services import cardigann as cardigann_svc
    import json

    fail_limit = int(getattr(settings, "indexer_health_fail_disable", 5) or 5)
    if not getattr(settings, "indexer_health_enabled", True):
        return {"ok": True, "skipped": True}

    rows = db.query(Indexer).filter(Indexer.enabled.is_(True)).order_by(Indexer.priority).limit(40).all()
    ok = fail = disabled = 0
    for row in rows:
        creds = {}
        if row.credentials_json:
            try:
                creds = json.loads(row.credentials_json)
            except Exception:
                pass
        try:
            results = []
            if row.kind == "cardigann":
                def_id = creds.get("cardigann_id") or row.name
                results = cardigann_svc.search_definition(def_id, "ubuntu", config=creds, limit=3)
            elif row.kind == "builtin":
                from app.services import builtin_indexers
                bid = (creds.get("cardigann_id") or "").replace("builtin:", "") or row.name.lower()
                results = builtin_indexers.search(bid, "ubuntu", limit=3)
            else:
                results = torznab_client.search(row.url, query="ubuntu", apikey=row.api_key, limit=3)
            row.last_ok_at = datetime.now(timezone.utc)
            row.last_error = None
            # reset fail streak in credentials meta
            creds["fail_streak"] = 0
            row.credentials_json = json.dumps(creds)
            ok += 1
        except Exception as e:
            fail += 1
            row.last_error = str(e)[:500]
            streak = int(creds.get("fail_streak") or 0) + 1
            creds["fail_streak"] = streak
            row.credentials_json = json.dumps(creds)
            if streak >= fail_limit:
                row.enabled = False
                disabled += 1
                log.warning("Indexer auto-disabled after %s fails: %s", streak, row.name)
        db.add(row)
    db.commit()
    return {"checked": ok + fail, "ok": ok, "failed": fail, "disabled": disabled, "fail_limit": fail_limit}
