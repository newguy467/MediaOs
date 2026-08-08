"""
Library maintenance rules engine (Maintainerr-inspired).

Users define rules such as:
  - Movies older than N days AND quality below X → unmonitor / delete / notify
  - TV seasons fully downloaded → remove from wanted
  - Tag-based or collection-based cleanup

Foundation provides the rule shape and evaluation stub.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

log = logging.getLogger("mediaos.maintenance_rules")

# Example rule shape (stored as JSON in settings or a rules table later)
EXAMPLE_RULES = [
    {
        "id": "old-low-quality-movies",
        "name": "Old low-quality movies",
        "media_types": ["movie"],
        "conditions": {
            "min_age_days": 365,
            "max_quality_score": 5000,
            "has_file": True,
        },
        "actions": ["notify", "unmonitor"],  # future: delete, move, etc.
        "enabled": False,
    }
]


def list_rules() -> list[dict[str, Any]]:
    return EXAMPLE_RULES


def evaluate_rules(db: Session) -> dict[str, Any]:
    """
    Run enabled rules and return proposed actions.
    Real implementation will query MediaItem + file metadata and apply actions.
    """
    enabled = [r for r in EXAMPLE_RULES if r.get("enabled")]
    return {
        "rules_evaluated": len(enabled),
        "actions_proposed": 0,
        "message": "Maintenance rules engine foundation ready for condition evaluators.",
    }
