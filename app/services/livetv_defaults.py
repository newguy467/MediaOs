"""iptv-org playlists + iptv-org/epg (epg-grabber) XMLTV presets.

Playlists: https://github.com/iptv-org/iptv (GitHub Pages)
EPG guides: https://github.com/iptv-org/epg → iptv-org.github.io/epg/guides/...

MediaOs does not embed Node scrapers; it consumes published XMLTV URLs
(the output of epg-grabber / iptv-org/epg) and re-exports for Jellyfin.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import LiveTvSource
from app.services.livetv import sync_source

log = logging.getLogger("mediaos.livetv_defaults")

# Country / category M3U presets
IPTV_ORG_PRESETS: list[dict[str, str]] = [
    {
        "name": "iptv-org · United States",
        "url": "https://iptv-org.github.io/iptv/countries/us.m3u",
        "key": "iptv-org-us",
        "epg_key": "epg-us-tvtv",
    },
    {
        "name": "iptv-org · United Kingdom",
        "url": "https://iptv-org.github.io/iptv/countries/uk.m3u",
        "key": "iptv-org-uk",
        "epg_key": "epg-uk-sky",
    },
    {
        "name": "iptv-org · Canada",
        "url": "https://iptv-org.github.io/iptv/countries/ca.m3u",
        "key": "iptv-org-ca",
        "epg_key": "epg-us-tvtv",
    },
    {
        "name": "iptv-org · Australia",
        "url": "https://iptv-org.github.io/iptv/countries/au.m3u",
        "key": "iptv-org-au",
        "epg_key": "epg-au-ontv",
    },
    {
        "name": "iptv-org · Entertainment",
        "url": "https://iptv-org.github.io/iptv/categories/entertainment.m3u",
        "key": "iptv-org-entertainment",
        "epg_key": "epg-us-tvtv",
    },
    {
        "name": "iptv-org · Documentary",
        "url": "https://iptv-org.github.io/iptv/categories/documentary.m3u",
        "key": "iptv-org-documentary",
        "epg_key": "epg-us-tvtv",
    },
    {
        "name": "iptv-org · Sports",
        "url": "https://iptv-org.github.io/iptv/categories/sports.m3u",
        "key": "iptv-org-sports",
        "epg_key": "epg-us-tvtv",
    },
]

# Published XMLTV from iptv-org/epg (built with epg-grabber)
EPG_PRESETS: list[dict[str, str]] = [
    {
        "key": "epg-us-tvtv",
        "name": "US · tvtv.us",
        "url": "https://iptv-org.github.io/epg/guides/us/tvtv.us.epg.xml",
        "region": "us",
    },
    {
        "key": "epg-us-local",
        "name": "US local · tvtv.us",
        "url": "https://iptv-org.github.io/epg/guides/us-local/tvtv.us.epg.xml",
        "region": "us",
    },
    {
        "key": "epg-uk-sky",
        "name": "UK · sky.com",
        "url": "https://iptv-org.github.io/epg/guides/uk/sky.com.epg.xml",
        "region": "uk",
    },
    {
        "key": "epg-uk-freeview",
        "name": "UK · freeview.co.uk",
        "url": "https://iptv-org.github.io/epg/guides/uk/freeview.co.uk.epg.xml",
        "region": "uk",
    },
    {
        "key": "epg-au-ontv",
        "name": "AU · ontvtonight.com",
        "url": "https://iptv-org.github.io/epg/guides/au/ontvtonight.com.epg.xml",
        "region": "au",
    },
    {
        "key": "epg-ca-tvtv",
        "name": "CA · tvtv (via US guide)",
        "url": "https://iptv-org.github.io/epg/guides/us/tvtv.us.epg.xml",
        "region": "ca",
    },
]

DEFAULT_SEED_KEYS = ("iptv-org-us", "iptv-org-entertainment")


def list_presets() -> list[dict[str, str]]:
    return list(IPTV_ORG_PRESETS)


def list_epg_presets() -> list[dict[str, str]]:
    return list(EPG_PRESETS)


def _preset_by_key(key: str) -> dict[str, str] | None:
    for p in IPTV_ORG_PRESETS:
        if p["key"] == key:
            return p
    return None


def _epg_by_key(key: str) -> dict[str, str] | None:
    for p in EPG_PRESETS:
        if p["key"] == key:
            return p
    return None


def epg_url_for_preset(preset: dict[str, str]) -> str | None:
    ek = preset.get("epg_key")
    if not ek:
        return None
    ep = _epg_by_key(ek)
    return ep["url"] if ep else None


def ensure_source(db: Session, preset: dict[str, str], *, sync: bool = False) -> tuple[LiveTvSource, bool]:
    """Create M3U source for preset if missing; always bind epg_url when known."""
    epg = epg_url_for_preset(preset)
    existing = (
        db.query(LiveTvSource)
        .filter(LiveTvSource.url == preset["url"])
        .first()
    )
    if existing:
        if epg and not (existing.epg_url or "").strip():
            existing.epg_url = epg
            db.add(existing)
            db.commit()
            db.refresh(existing)
        return existing, False
    existing = (
        db.query(LiveTvSource)
        .filter(LiveTvSource.name == preset["name"])
        .first()
    )
    if existing:
        if not existing.url:
            existing.url = preset["url"]
        if epg and not (existing.epg_url or "").strip():
            existing.epg_url = epg
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing, False

    src = LiveTvSource(
        name=preset["name"],
        kind="m3u",
        url=preset["url"],
        enabled=True,
        epg_url=epg,
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
    use_keys = keys or list(DEFAULT_SEED_KEYS)
    created, synced, errors, epg_bound = [], [], [], []
    for key in use_keys:
        preset = _preset_by_key(key)
        if not preset:
            errors.append(f"unknown key {key}")
            continue
        try:
            src, was_new = ensure_source(db, preset, sync=False)
            if was_new:
                created.append(preset["name"])
            if src.epg_url:
                epg_bound.append({"source": src.name, "epg_url": src.epg_url})
            if sync:
                try:
                    n = sync_source(db, src)
                    synced.append({"name": preset["name"], "channels": n})
                except Exception as e:
                    errors.append(f"{preset['name']}: {e}")
        except Exception as e:
            errors.append(f"{key}: {e}")

    # Global extra EPG URLs (multi-merge) — attach as empty sources or refresh
    try:
        from app.services.livetv import fetch_and_index_epg
        stats = fetch_and_index_epg(db)
    except Exception as e:
        stats = {"error": str(e)}
        log.warning("EPG index after seed: %s", e)

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
        "epg_bound": epg_bound,
        "epg_index": stats,
        "logos": logo_result,
        "errors": errors[:15],
        "presets": use_keys,
    }


def seed_if_empty(db: Session) -> dict[str, Any] | None:
    """Auto-seed when empty; when sources exist, still bind missing EPG URLs."""
    if not getattr(settings, "livetv_seed_iptv_org", True):
        return None
    n = db.query(LiveTvSource).count()
    if n == 0:
        log.info("No Live TV sources — seeding iptv-org defaults + EPG URLs")
        return seed_default_sources(db, sync=True)
    # Repair: bind EPG presets onto existing iptv-org sources missing epg_url
    repaired = []
    for src in db.query(LiveTvSource).all():
        if (src.epg_url or "").strip():
            continue
        for p in IPTV_ORG_PRESETS:
            if p["url"] == (src.url or "") or p["name"] == src.name:
                epg = epg_url_for_preset(p)
                if epg:
                    src.epg_url = epg
                    db.add(src)
                    repaired.append({"source": src.name, "epg_url": epg})
                break
    if repaired:
        db.commit()
        log.info("Bound missing EPG URLs: %s", repaired)
        return {"ok": True, "repaired_epg": repaired}
    return None


def resync_iptv_org_sources(db: Session) -> dict[str, Any]:
    results = []
    for src in db.query(LiveTvSource).filter(LiveTvSource.kind == "m3u").all():
        url = (src.url or "")
        if "iptv-org.github.io" not in url and "iptv-org" not in (src.name or "").lower():
            continue
        # re-bind EPG if missing
        for p in IPTV_ORG_PRESETS:
            if p["url"] == url or p["name"] == src.name:
                epg = epg_url_for_preset(p)
                if epg and not (src.epg_url or "").strip():
                    src.epg_url = epg
                    db.add(src)
                break
        try:
            n = sync_source(db, src)
            results.append({"id": src.id, "name": src.name, "channels": n, "epg_url": src.epg_url})
        except Exception as e:
            results.append({"id": src.id, "name": src.name, "error": str(e)})
    db.commit()
    try:
        from app.services.livetv import fetch_and_index_epg
        epg_stats = fetch_and_index_epg(db)
    except Exception as e:
        epg_stats = {"error": str(e)}
    return {"results": results, "epg": epg_stats}
