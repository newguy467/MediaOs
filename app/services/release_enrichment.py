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
    raw_unit = m.group(2).upper()
    is_binary = "I" in raw_unit
    base = raw_unit.replace("I", "")  # KB / MB / GB / TB
    if is_binary:
        mult = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}.get(base, 1)
    else:
        mult = {"KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4}.get(base, 1)
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
