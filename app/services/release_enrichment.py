"""Release enrichment — normalize size/seeders/freeleech and boost scores."""
from __future__ import annotations

import re
from typing import Any


_SIZE_RE = re.compile(r"([\d.]+)\s*(Ki?B|Mi?B|Gi?B|Ti?B|KB|MB|GB|TB)", re.I)
_FREELEECH_RE = re.compile(r"\b(freeleech|free\s*leech|FL)\b", re.I)
_PACK_RE = re.compile(r"\b(season\s*pack|complete\s*series|S\d{2}\s*pack)\b", re.I)


def parse_size_bytes(val: Any) -> int | None:
    if val is None:
        return None
    if isinstance(val, (int, float)) and val > 0:
        # Heuristic: values < 1e6 might already be MB from some indexers
        return int(val)
    s = str(val).strip()
    if s.isdigit():
        return int(s)
    m = _SIZE_RE.search(s.replace(",", ""))
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2).upper().replace("I", "")
    mult = {"KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4}.get(unit[:2] + ("B" if not unit.endswith("B") else ""), 1)
    if unit in ("KB", "MB", "GB", "TB", "KIB", "MIB", "GIB", "TIB"):
        # prefer binary for iB
        if "I" in m.group(2).upper():
            mult = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}[unit.replace("I", "") if False else unit[:2] + "B"]
            mult = {"KIB": 1024, "MIB": 1024**2, "GIB": 1024**3, "TIB": 1024**4}.get(m.group(2).upper(), mult)
        else:
            mult = {"KB": 1000, "MB": 1_000_000, "GB": 1_000_000_000, "TB": 1_000_000_000_000}.get(unit, 1)
    return int(num * mult)


def enrich_release(rel: dict[str, Any]) -> dict[str, Any]:
    """Mutate+return release with normalized fields and enrichment flags."""
    title = rel.get("title") or rel.get("release_title") or ""
    size = parse_size_bytes(rel.get("size") or rel.get("size_bytes"))
    if size is not None:
        rel["size_bytes"] = size
        rel["size"] = size
    seeders = rel.get("seeders")
    try:
        rel["seeders"] = int(seeders) if seeders is not None else None
    except Exception:
        rel["seeders"] = None
    rel["freeleech"] = bool(rel.get("freeleech")) or bool(_FREELEECH_RE.search(title))
    rel["season_pack"] = bool(rel.get("season_pack")) or bool(_PACK_RE.search(title))
    # Soft score boosts used by search ranking
    boost = 0
    if rel.get("freeleech"):
        boost += 5
    if rel.get("seeders") and rel["seeders"] >= 50:
        boost += 3
    elif rel.get("seeders") and rel["seeders"] >= 10:
        boost += 1
    if rel.get("season_pack"):
        boost += 2
    rel["enrichment_boost"] = boost
    return rel


def enrich_many(releases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_release(r) for r in releases]
