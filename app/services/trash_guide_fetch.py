"""
Live TRaSH Guides sync — Recyclarr-inspired.

Goals for MediaOs v4:
- Fetch real TRaSH Guide definitions (custom formats, quality profiles, scores,
  quality definitions, naming) instead of only a builtin JSON snapshot.
- Apply them into the MediaOs quality engine so every media type benefits.
- Provide status + last-sync info for the admin UI.
- Remain usable offline via the conservative builtin fallback.

Configuration (settings / env):
  TRASH_GUIDE_URL          — primary remote guide endpoint (JSON)
  TRASH_GUIDE_PATH         — optional local override file
  TRASH_GUIDE_AUTO_SYNC    — enable periodic sync (scheduler)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.trash_import import import_trash_payload

log = logging.getLogger("mediaos.trash_fetch")

# Conservative built-in snapshot so the system works offline / first-run.
# This is intentionally smaller than full TRaSH; live fetch replaces it.
_BUILTIN = {
    "version": "builtin-4.7-fallback",
    "scores": {
        "resolution": {
            "2160p": 20000, "4k": 20000, "uhd": 20000,
            "1080p": 10000, "720p": 5000, "480p": 1000,
        },
        "source": {
            "remux": 8000, "bluray": 6000, "webdl": 4500, "webrip": 3500,
            "hdtv": 2000, "cam": -5000, "ts": -3000,
        },
        "codec": {"av1": 1200, "x265": 800, "hevc": 800, "x264": 400, "xvid": -200},
        "hdr": {"dv": 1500, "hdr10+": 900, "hdr10": 700, "hdr": 500, "sdr": 0},
        "audio": {"truehd": 500, "dts-hd": 400, "atmos": 600, "dd+": 200, "aac": 50},
        "groups": {
            "framestor": 500, "criterion": 450, "ctrlhd": 300, "flux": 250,
            "ntb": 220, "sparks": 180, "rarbg": 50,
        },
    },
    "custom_formats": [
        {"name": "Remux", "score": 100, "conditions": ["source:remux"]},
        {"name": "x265-HD", "score": 100, "conditions": ["codec:x265", "resolution:1080p|720p"]},
        {"name": "AV1", "score": 150, "conditions": ["codec:av1"]},
        {"name": "Repack", "score": 5, "conditions": ["repack"]},
        {"name": "Proper", "score": 5, "conditions": ["proper"]},
        {"name": "HDR", "score": 50, "conditions": ["hdr"]},
    ],
    "quality_definitions": {
        "movie": {"min": 0, "preferred": 50, "max": 400},
        "episode": {"min": 0, "preferred": 40, "max": 200},
    },
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _load_url(url: str) -> dict[str, Any]:
    r = httpx.get(
        url,
        timeout=45,
        follow_redirects=True,
        headers={"User-Agent": "MediaOs/4.7.2 (TRaSH-sync)"},
    )
    r.raise_for_status()
    return r.json()


def fetch_and_apply(
    *,
    url: str | None = None,
    use_builtin_fallback: bool = True,
) -> dict[str, Any]:
    """
    Fetch guide JSON and apply via trash_import.
    Returns a status dict suitable for the admin UI / API.
    """
    url = (url or getattr(settings, "trash_guide_url", None) or "").strip()
    payload: dict[str, Any] | None = None
    source: str | None = None
    errors: list[str] = []

    if url:
        try:
            payload = _load_url(url)
            source = url
            log.info("TRaSH guide fetched from %s", url)
        except Exception as e:
            errors.append(f"url:{e}")
            log.warning("trash guide fetch failed %s: %s", url, e)

    # Optional local file path
    local = Path(getattr(settings, "trash_guide_path", "") or "")
    if payload is None and local and str(local) not in (".", "") and local.exists():
        try:
            payload = json.loads(local.read_text(encoding="utf-8"))
            source = str(local)
            log.info("TRaSH guide loaded from local file %s", local)
        except Exception as e:
            errors.append(f"local:{e}")

    if payload is None and use_builtin_fallback:
        payload = _BUILTIN
        source = "builtin"
        log.info("Using builtin TRaSH-style fallback snapshot")

    if payload is None:
        return {
            "ok": False,
            "source": None,
            "applied": False,
            "errors": errors or ["no payload"],
            "synced_at": None,
        }

    try:
        result = import_trash_payload(payload)
        return {
            "ok": True,
            "source": source,
            "applied": True,
            "result": result,
            "errors": errors,
            "synced_at": _utcnow().isoformat(),
            "custom_formats": len(payload.get("custom_formats") or []),
            "has_scores": bool(payload.get("scores")),
        }
    except Exception as e:
        log.exception("trash import failed")
        return {
            "ok": False,
            "source": source,
            "applied": False,
            "errors": errors + [str(e)],
            "synced_at": None,
        }


def get_sync_status() -> dict[str, Any]:
    """Lightweight status for the Quality / TRaSH admin UI."""
    # In a full implementation this would read last-sync metadata from DB/settings.
    return {
        "auto_sync": bool(getattr(settings, "trash_guide_auto_sync", False)),
        "configured_url": bool(getattr(settings, "trash_guide_url", None)),
        "message": "Call POST /api/quality/trash/sync to refresh from live guides.",
    }
