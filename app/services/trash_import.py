"""Import TRaSH-style custom format / score hints into MediaOs matrices.

Recyclarr-inspired: we do not scrape trash-guides at runtime by default;
accept a JSON payload (exported guide fragment) and merge into quality matrices
and optional custom-format style notes.
"""
from __future__ import annotations

from typing import Any

from app.services.quality.matrix import set_family, set_cell, MATRIX_KEYS


def import_trash_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Expected shapes (any subset):
      {
        "scores": {
          "resolution": {"2160p": 20000, ...},
          "groups": {"framestor": 500, ...},
          ...
        },
        "custom_formats": [
          {"name": "x265 (HD)", "score": 100, "regex": "..."}
        ]
      }
    """
    applied = {"matrices": {}, "custom_formats": 0}
    scores = payload.get("scores") or payload.get("matrices") or {}
    for family, cells in scores.items():
        if family not in MATRIX_KEYS:
            continue
        if isinstance(cells, dict):
            set_family(family, cells, replace=False)
            applied["matrices"][family] = len(cells)
    # custom formats: store as group-like boosts if they look like group names
    for cf in payload.get("custom_formats") or []:
        name = (cf.get("name") or "").strip()
        score = int(cf.get("score") or 0)
        if not name:
            continue
        # map into groups matrix under sanitized key
        key = name.lower().replace(" ", "-")[:64]
        set_cell("groups", key, score)
        applied["custom_formats"] += 1
    return {"ok": True, "applied": applied}
