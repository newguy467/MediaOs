"""
Health trends / metrics snapshots (MediaOS v2).

Lightweight in-DB or in-memory history for indexer success, queue depth, disk.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Any

log = logging.getLogger("mediaos.health_trends")

# in-memory ring buffers (process lifetime). For durable trends, persist later.
_MAX = 288  # ~24h if sampled every 5 min
_indexer_success: dict[str, deque] = defaultdict(lambda: deque(maxlen=_MAX))
_queue_depth: deque = deque(maxlen=_MAX)
_disk_free_gb: deque = deque(maxlen=_MAX)


def record_indexer_result(indexer_key: str, ok: bool) -> None:
    _indexer_success[indexer_key].append({"ts": time.time(), "ok": bool(ok)})


def record_queue_depth(n: int) -> None:
    _queue_depth.append({"ts": time.time(), "depth": int(n)})


def record_disk_free_gb(gb: float) -> None:
    _disk_free_gb.append({"ts": time.time(), "free_gb": float(gb)})


def snapshot() -> dict[str, Any]:
    def _rate(dq: deque) -> float | None:
        if not dq:
            return None
        ok = sum(1 for x in dq if x.get("ok"))
        return round(100.0 * ok / len(dq), 1)

    indexers = {k: {"samples": len(v), "success_pct": _rate(v)} for k, v in _indexer_success.items()}
    return {
        "indexers": indexers,
        "queue_depth_samples": list(_queue_depth)[-48:],
        "disk_free_gb_samples": list(_disk_free_gb)[-48:],
        "generated_at": time.time(),
    }


def persist(db) -> None:
    """Write snapshot to AppSetting for durability across restarts."""
    import json
    from app.models import AppSetting
    snap = snapshot()
    row = db.query(AppSetting).filter(AppSetting.key == "health_trends_snapshot").first()
    payload = json.dumps(snap)
    if not row:
        db.add(AppSetting(key="health_trends_snapshot", value=payload))
    else:
        row.value = payload
    db.commit()


def load_persisted(db) -> dict:
    import json
    from app.models import AppSetting
    row = db.query(AppSetting).filter(AppSetting.key == "health_trends_snapshot").first()
    if not row:
        return snapshot()
    try:
        data = json.loads(row.value)
        # merge live samples if any
        live = snapshot()
        if live.get("indexers"):
            data["indexers"] = {**(data.get("indexers") or {}), **(live.get("indexers") or {})}
        return data
    except Exception:
        return snapshot()
