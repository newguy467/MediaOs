"""Editable quality scoring matrices (resolution / source / codec / hdr / audio / groups / edition).

Defaults live in profiles.py. Overrides persist under data/quality_matrix.json
and are applied into the live dicts used by attr_base_score / GROUP_BOOST.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger("mediaos.quality.matrix")
_lock = threading.Lock()
_PATH = Path("data/quality_matrix.json")

MATRIX_KEYS = (
    "resolution",
    "source",
    "codec",
    "hdr",
    "audio",
    "groups",
    "edition",
)

_DEFAULT_ATTR = {
    "resolution": "RESOLUTION_SCORE",
    "source": "SOURCE_SCORE",
    "codec": "CODEC_SCORE",
    "hdr": "HDR_SCORE",
    "audio": "AUDIO_SCORE",
    "groups": "GROUP_BOOST",
    "edition": "EDITION_SCORE",
}


def _profiles_mod():
    from app.services.quality import profiles as qp
    return qp


def _ensure_edition(qp) -> dict:
    if not hasattr(qp, "EDITION_SCORE") or not isinstance(qp.EDITION_SCORE, dict):
        qp.EDITION_SCORE = {
            "directors-cut": 100,
            "extended": 80,
            "imax": 120,
            "criterion": 150,
            "theatrical": 0,
            "unrated": 40,
            "remastered": 50,
        }
    return qp.EDITION_SCORE


def defaults() -> dict[str, dict[str, int]]:
    qp = _profiles_mod()
    _ensure_edition(qp)
    return {
        "resolution": dict(qp.RESOLUTION_SCORE),
        "source": dict(qp.SOURCE_SCORE),
        "codec": dict(qp.CODEC_SCORE),
        "hdr": dict(qp.HDR_SCORE),
        "audio": dict(qp.AUDIO_SCORE),
        "groups": dict(qp.GROUP_BOOST),
        "edition": dict(qp.EDITION_SCORE),
    }


def _load_file() -> dict[str, dict[str, int]]:
    if not _PATH.exists():
        return {}
    try:
        data = json.loads(_PATH.read_text())
        out: dict[str, dict[str, int]] = {}
        for k in MATRIX_KEYS:
            if isinstance(data.get(k), dict):
                out[k] = {str(kk).lower(): int(vv) for kk, vv in data[k].items()}
        return out
    except Exception as e:
        log.warning("quality matrix load failed: %s", e)
        return {}


def _save_file(overrides: dict[str, dict[str, int]]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(overrides, indent=2, sort_keys=True))


def apply_overrides(overrides: dict[str, dict[str, int]] | None = None) -> None:
    """Merge overrides into live module dicts (in-place)."""
    qp = _profiles_mod()
    _ensure_edition(qp)
    ov = overrides if overrides is not None else _load_file()
    with _lock:
        for key, attr in _DEFAULT_ATTR.items():
            base = getattr(qp, attr, None)
            if not isinstance(base, dict):
                continue
            for name, score in (ov.get(key) or {}).items():
                base[str(name).lower()] = int(score)


def get_matrix(family: str | None = None) -> dict[str, Any]:
    apply_overrides()
    qp = _profiles_mod()
    _ensure_edition(qp)
    full = {
        "resolution": dict(sorted(qp.RESOLUTION_SCORE.items(), key=lambda x: -x[1])),
        "source": dict(sorted(qp.SOURCE_SCORE.items(), key=lambda x: -x[1])),
        "codec": dict(sorted(qp.CODEC_SCORE.items(), key=lambda x: -x[1])),
        "hdr": dict(sorted(qp.HDR_SCORE.items(), key=lambda x: -x[1])),
        "audio": dict(sorted(qp.AUDIO_SCORE.items(), key=lambda x: -x[1])),
        "groups": dict(sorted(qp.GROUP_BOOST.items(), key=lambda x: (-x[1], x[0]))),
        "edition": dict(sorted(qp.EDITION_SCORE.items(), key=lambda x: -x[1])),
    }
    if family:
        if family not in full:
            raise KeyError(family)
        return {"family": family, "cells": full[family], "count": len(full[family])}
    return {
        "families": {
            k: {"count": len(v), "sample": dict(list(v.items())[:5])}
            for k, v in full.items()
        },
        "matrices": full,
    }


def set_cell(family: str, name: str, score: int) -> dict[str, Any]:
    if family not in MATRIX_KEYS:
        raise KeyError(family)
    name = str(name).strip().lower()
    if not name:
        raise ValueError("empty name")
    with _lock:
        ov = _load_file()
        ov.setdefault(family, {})[name] = int(score)
        _save_file(ov)
    apply_overrides(ov)
    return {"ok": True, "family": family, "name": name, "score": int(score)}


def set_family(family: str, cells: dict[str, int], *, replace: bool = False) -> dict[str, Any]:
    if family not in MATRIX_KEYS:
        raise KeyError(family)
    cleaned = {str(k).strip().lower(): int(v) for k, v in (cells or {}).items() if str(k).strip()}
    with _lock:
        ov = _load_file()
        if replace:
            ov[family] = cleaned
        else:
            ov.setdefault(family, {}).update(cleaned)
        _save_file(ov)
    apply_overrides(ov)
    return {"ok": True, "family": family, "count": len(ov.get(family) or {})}


def delete_cell(family: str, name: str) -> dict[str, Any]:
    if family not in MATRIX_KEYS:
        raise KeyError(family)
    name = str(name).strip().lower()
    with _lock:
        ov = _load_file()
        if family in ov:
            ov[family].pop(name, None)
            _save_file(ov)
        apply_overrides(ov)
    return {"ok": True, "family": family, "name": name}


def reset_family(family: str | None = None) -> dict[str, Any]:
    with _lock:
        ov = _load_file()
        if family is None:
            ov = {}
        else:
            if family not in MATRIX_KEYS:
                raise KeyError(family)
            ov.pop(family, None)
        _save_file(ov)
    apply_overrides(ov)
    return {"ok": True, "reset": family or "all"}
