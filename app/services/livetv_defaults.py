"""iptv-org default playlists — remote URLs that update upstream.

https://github.com/iptv-org/iptv
Playlists are republished on GitHub Pages; MediaOs stores only the URL and
re-syncs on a schedule. We do not vendor channel lists in the image.

Legal note: iptv-org playlists are collections of public stream links (CC0 for
the list). Stream availability/geo varies; prefer country/category slices over
the full world index for a sane default.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import LiveTvSource
from app.services.livetv import sync_source

log = logging.getLogger("mediaos.livetv_defaults")

# Stable GitHub Pages URLs (auto-updated by iptv-org CI)
IPTV_ORG_PRESETS: list[dict[str, str]] = [
    {
        "name": "iptv-org · United States",
        "url": "https://iptv-org.github.io/iptv/countries/us.m3u",
        "key": "iptv-org-us",
    },
    {
        "name": "iptv-org · United Kingdom",
        "url": "https://iptv-org.github.io/iptv/countries/uk.m3u",
        "key": "iptv-org-uk",
    },
    {
        "name": "iptv-org · Canada",
        "url": "https://iptv-org.github.io/iptv/countries/ca.m3u",
        "key": "iptv-org-ca",
    },
    {
        "name": "iptv-org · Entertainment",
        "url": "https://iptv-org.github.io/iptv/categories/entertainment.m3u",
        "key": "iptv-org-entertainment",
    },
    {
        "name": "iptv-org · Documentary",
        "url": "https://iptv-org.github.io/iptv/categories/documentary.m3u",
        "key": "iptv-org-documentary",
    },
    {
        "name": "iptv-org · Sports",
        "url": "https://iptv-org.github.io/iptv/categories/sports.m3u",
        "key": "iptv-org-sports",
    },
]

# Minimal default set when seeding empty installs (US + entertainment)
DEFAULT_SEED_KEYS = ("iptv-org-us", "iptv-org-entertainment")


def list_presets() -> list[dict[str, str]]:
    return list(IPTV_ORG_PRESETS)


def _preset_by_key(key: str) -> dict[str, str] | None:
    for p in IPTV_ORG_PRESETS:
        if p["key"] == key:
            return p
    return None


def ensure_source(db: Session, preset: dict[str, str], *, sync: bool = False) -> tuple[LiveTvSource, bool]:
    """Create M3U source for preset if missing. Returns (source, created)."""
    existing = (
        db.query(LiveTvSource)
        .filter(LiveTvSource.url == preset["url"])
        .first()
    )
    if existing:
        return existing, False
    # also match by name marker
    existing = (
        db.query(LiveTvSource)
        .filter(LiveTvSource.name == preset["name"])
        .first()
    )
    if existing:
        if not existing.url:
            existing.url = preset["url"]
            db.add(existing)
            db.commit()
        return existing, False

    src = LiveTvSource(
        name=preset["name"],
        kind="m3u",
        url=preset["url"],
        enabled=True,
        epg_url=None,
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    if sync:
        try:
            n = sync_source(db, src)
            log.info("Synced %s → %s channels", preset["name"], n)
        except Exception as e:
            log.warning("Initial sync failed for %s: %s", preset["name"], e)
    return src, True


def seed_default_sources(db: Session, *, sync: bool = True, keys: list[str] | None = None) -> dict[str, Any]:
    """Seed iptv-org defaults. Used on empty DB or explicit user action."""
    use_keys = keys or list(DEFAULT_SEED_KEYS)
    created = []
    synced = []
    errors = []
    for key in use_keys:
        preset = _preset_by_key(key)
        if not preset:
            errors.append(f"unknown key {key}")
            continue
        try:
            src, was_new = ensure_source(db, preset, sync=False)
            if was_new:
                created.append(preset["name"])
            if sync:
                try:
                    n = sync_source(db, src)
                    synced.append({"name": preset["name"], "channels": n})
                except Exception as e:
                    errors.append(f"{preset['name']}: {e}")
        except Exception as e:
            errors.append(f"{key}: {e}")
    logo_result = None
    try:
        from app.services.livetv_logos import install_remote_logos
        logo_result = install_remote_logos(db, limit=800)
    except Exception as e:
        log.warning("logo install after seed: %s", e)
    return {
        "ok": True,
        "created": created,
        "synced": synced,
        "logos": logo_result,
        "errors": errors[:10],
        "presets": use_keys,
    }


def seed_if_empty(db: Session) -> dict[str, Any] | None:
    """Auto-seed when no Live TV sources exist and setting allows it."""
    enabled = getattr(settings, "livetv_seed_iptv_org", True)
    if not enabled:
        return None
    count = db.query(LiveTvSource).count()
    if count > 0:
        return None
    log.info("No Live TV sources — seeding iptv-org defaults %s", DEFAULT_SEED_KEYS)
    return seed_default_sources(db, sync=True)


def resync_iptv_org_sources(db: Session) -> dict[str, Any]:
    """Re-fetch all enabled sources whose URL is on iptv-org.github.io."""
    rows = (
        db.query(LiveTvSource)
        .filter(LiveTvSource.enabled.is_(True), LiveTvSource.kind == "m3u")
        .all()
    )
    results = []
    for src in rows:
        url = (src.url or "")
        if "iptv-org.github.io" not in url and "iptv-org" not in (src.name or "").lower():
            continue
        try:
            n = sync_source(db, src)
            results.append({"id": src.id, "name": src.name, "channels": n, "ok": True})
        except Exception as e:
            results.append({"id": src.id, "name": src.name, "ok": False, "error": str(e)[:120]})
    return {"ok": True, "results": results}
