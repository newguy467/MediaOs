"""
Library maintenance rules engine (Maintainerr-inspired).

Rules are stored in AppSetting key `maintenance_rules_json`.
Default seed rules ship disabled until the user enables them.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import AppSetting, ItemStatus, MediaItem, MediaType

log = logging.getLogger("mediaos.maintenance_rules")

SETTING_KEY = "maintenance_rules_json"
HISTORY_KEY = "maintenance_rules_history_json"
MAX_HISTORY = 100

DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "id": "old-low-quality-movies",
        "name": "Old low-quality movies",
        "media_types": ["movie"],
        "conditions": {
            "min_age_days": 365,
            "max_quality_score": 5000,
            "has_file": True,
            "monitored_only": True,
        },
        "actions": ["notify", "unmonitor"],
        "enabled": False,
        "dry_run_default": True,
    },
    {
        "id": "ended-series-complete",
        "name": "Ended series fully on disk",
        "media_types": ["tv"],
        "conditions": {
            "has_file": True,
            "series_status_in": ["ended", "canceled"],
            "monitored_only": True,
        },
        "actions": ["notify"],
        "enabled": False,
        "dry_run_default": True,
    },
    {
        "id": "stale-wanted-movies",
        "name": "Stale wanted movies (no file)",
        "media_types": ["movie"],
        "conditions": {
            "min_age_days": 180,
            "has_file": False,
            "status_in": ["wanted", "missing"],
            "monitored_only": True,
        },
        "actions": ["notify", "unmonitor"],
        "enabled": False,
        "dry_run_default": True,
    },
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_json(db: Session, key: str, default: Any) -> Any:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not row or not row.value:
        return default
    try:
        return json.loads(row.value)
    except Exception:
        return default


def _set_json(db: Session, key: str, value: Any) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    payload = json.dumps(value)
    if row:
        row.value = payload
    else:
        db.add(AppSetting(key=key, value=payload))
    db.commit()


def list_rules(db: Session | None = None) -> list[dict[str, Any]]:
    if db is None:
        return list(DEFAULT_RULES)
    data = _get_json(db, SETTING_KEY, None)
    if not isinstance(data, list) or not data:
        _set_json(db, SETTING_KEY, DEFAULT_RULES)
        return list(DEFAULT_RULES)
    return data


def save_rules(db: Session, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for r in rules:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        cleaned.append(
            {
                "id": str(r["id"])[:64],
                "name": str(r.get("name") or r["id"])[:120],
                "media_types": list(r.get("media_types") or ["movie"]),
                "conditions": dict(r.get("conditions") or {}),
                "actions": list(r.get("actions") or ["notify"]),
                "enabled": bool(r.get("enabled")),
                "dry_run_default": bool(r.get("dry_run_default", True)),
            }
        )
    _set_json(db, SETTING_KEY, cleaned)
    return cleaned


def _item_age_days(item: MediaItem) -> float | None:
    added = getattr(item, "added_at", None)
    if not added:
        return None
    if added.tzinfo is None:
        added = added.replace(tzinfo=timezone.utc)
    return (_utcnow() - added).total_seconds() / 86400.0


def _status_str(item: MediaItem) -> str:
    st = getattr(item, "status", None)
    if st is None:
        return ""
    return st.value if hasattr(st, "value") else str(st)


def _matches(item: MediaItem, rule: dict[str, Any]) -> bool:
    cond = rule.get("conditions") or {}
    types = rule.get("media_types") or []
    mt = item.media_type.value if hasattr(item.media_type, "value") else str(item.media_type or "")
    if types and mt not in types:
        return False

    if cond.get("monitored_only") and not bool(getattr(item, "monitored", True)):
        return False

    has_file = bool(getattr(item, "file_path", None))
    if "has_file" in cond and bool(cond["has_file"]) != has_file:
        return False

    min_age = cond.get("min_age_days")
    if min_age is not None:
        age = _item_age_days(item)
        if age is None or age < float(min_age):
            return False

    max_q = cond.get("max_quality_score")
    if max_q is not None:
        qs = getattr(item, "quality_score", None)
        if qs is None or int(qs) > int(max_q):
            return False

    status_in = cond.get("status_in") or []
    if status_in:
        if _status_str(item).lower() not in [s.lower() for s in status_in]:
            return False

    series_in = cond.get("series_status_in") or []
    if series_in:
        ss = (getattr(item, "series_status", None) or "").lower()
        if ss not in [s.lower() for s in series_in]:
            return False

    return True


def _apply_actions(
    db: Session,
    item: MediaItem,
    actions: list[str],
    *,
    dry_run: bool,
) -> list[str]:
    done: list[str] = []
    for act in actions:
        act = (act or "").lower()
        if act == "notify":
            done.append("notify")
            if not dry_run:
                try:
                    from app.services.hooks import notify_event
                    notify_event(
                        "maintenance",
                        f"{item.title} matched maintenance rule",
                        title="Maintenance",
                    )
                except Exception:
                    pass
        elif act == "unmonitor":
            done.append("unmonitor")
            if not dry_run and getattr(item, "monitored", False):
                item.monitored = False
                db.add(item)
        elif act == "delete_file":
            # Safety: only propose unless explicitly allowed later
            done.append("delete_file(proposed)")
        else:
            done.append(f"unknown:{act}")
    return done


def evaluate_rules(
    db: Session,
    *,
    dry_run: bool | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Evaluate enabled rules against the library and optionally apply safe actions."""
    rules = [r for r in list_rules(db) if r.get("enabled")]
    if not rules:
        return {
            "ok": True,
            "rules_evaluated": 0,
            "actions_proposed": 0,
            "actions_applied": 0,
            "matches": [],
            "message": "No enabled maintenance rules",
        }

    items = db.query(MediaItem).limit(limit * 3).all()
    matches: list[dict[str, Any]] = []
    applied = 0

    for rule in rules:
        rule_dry = dry_run if dry_run is not None else bool(rule.get("dry_run_default", True))
        hit = 0
        for item in items:
            if hit >= limit:
                break
            if not _matches(item, rule):
                continue
            hit += 1
            actions_done = _apply_actions(
                db, item, list(rule.get("actions") or []), dry_run=rule_dry
            )
            if not rule_dry:
                applied += 1
            matches.append(
                {
                    "rule_id": rule.get("id"),
                    "rule_name": rule.get("name"),
                    "media_item_id": item.id,
                    "title": item.title,
                    "media_type": item.media_type.value
                    if hasattr(item.media_type, "value")
                    else str(item.media_type),
                    "actions": actions_done,
                    "dry_run": rule_dry,
                }
            )

    if applied:
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            log.warning("maintenance commit failed: %s", e)

    hist = _get_json(db, HISTORY_KEY, [])
    if not isinstance(hist, list):
        hist = []
    hist.insert(
        0,
        {
            "at": _utcnow().isoformat(),
            "rules_evaluated": len(rules),
            "matches": len(matches),
            "applied": applied,
        },
    )
    _set_json(db, HISTORY_KEY, hist[:MAX_HISTORY])

    try:
        from app.services.plugins import run_hook
        run_hook("maintenance", matches)
    except Exception:
        pass

    return {
        "ok": True,
        "rules_evaluated": len(rules),
        "actions_proposed": len(matches),
        "actions_applied": applied,
        "matches": matches[:100],
        "message": f"Evaluated {len(rules)} rules → {len(matches)} matches"
        + (" (dry-run)" if dry_run is not False else ""),
    }


def status(db: Session) -> dict[str, Any]:
    rules = list_rules(db)
    hist = _get_json(db, HISTORY_KEY, [])
    return {
        "rules": rules,
        "enabled_count": sum(1 for r in rules if r.get("enabled")),
        "history": hist[:20] if isinstance(hist, list) else [],
    }
