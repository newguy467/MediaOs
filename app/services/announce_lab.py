"""
Announce Lab — autobrr-inspired filters inside MediaOS (no extra container).

Polls configured Torznab/RSS sources, matches release titles against user filters,
and pushes magnets/URLs straight into the download client + queue.

This lives under Homelab (lab panel), not as a sidecar service.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy.orm import Session

from app.models import AppSetting, Download, Indexer

log = logging.getLogger("mediaos.announce_lab")

FILTERS_KEY = "announce_lab_filters_json"
STATE_KEY = "announce_lab_state_json"
HITS_KEY = "announce_lab_hits_json"  # recent matches (cap)
MAX_HITS = 200


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


def list_filters(db: Session) -> list[dict[str, Any]]:
    data = _get_json(db, FILTERS_KEY, [])
    return data if isinstance(data, list) else []


def save_filters(db: Session, filters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for f in filters:
        if not isinstance(f, dict):
            continue
        fid = str(f.get("id") or f.get("name") or "").strip()
        if not fid:
            continue
        cleaned.append(
            {
                "id": re.sub(r"[^a-zA-Z0-9._-]", "_", fid)[:64],
                "name": str(f.get("name") or fid)[:120],
                "enabled": bool(f.get("enabled", True)),
                # Match: any of these regexes (case-insensitive) against release title
                "match_regex": str(f.get("match_regex") or f.get("match") or "").strip(),
                "except_regex": str(f.get("except_regex") or f.get("except") or "").strip(),
                "categories": f.get("categories") or [],  # optional torznab cats
                "indexer_ids": f.get("indexer_ids") or [],  # empty = all enabled indexers
                "max_size_mb": f.get("max_size_mb"),
                "min_size_mb": f.get("min_size_mb"),
                "actions": f.get("actions") or ["download"],  # download | notify
                "priority": int(f.get("priority") or 0),
            }
        )
    cleaned.sort(key=lambda x: (-x["priority"], x["name"]))
    _set_json(db, FILTERS_KEY, cleaned)
    return cleaned


def recent_hits(db: Session) -> list[dict[str, Any]]:
    data = _get_json(db, HITS_KEY, [])
    return data if isinstance(data, list) else []


def _push_hit(db: Session, hit: dict[str, Any]) -> None:
    hits = recent_hits(db)
    hits.insert(0, hit)
    _set_json(db, HITS_KEY, hits[:MAX_HITS])


def _title_matches(filter_row: dict[str, Any], title: str) -> bool:
    title = title or ""
    mr = filter_row.get("match_regex") or ""
    er = filter_row.get("except_regex") or ""
    if mr:
        try:
            if not re.search(mr, title, re.I):
                return False
        except re.error:
            return False
    else:
        return False  # require a match pattern
    if er:
        try:
            if re.search(er, title, re.I):
                return False
        except re.error:
            pass
    return True


def _size_ok(filter_row: dict[str, Any], size_bytes: int | None) -> bool:
    if size_bytes is None:
        return True
    mb = size_bytes / (1024 * 1024)
    mn = filter_row.get("min_size_mb")
    mx = filter_row.get("max_size_mb")
    if mn is not None and mb < float(mn):
        return False
    if mx is not None and mb > float(mx):
        return False
    return True


def _fetch_torznab_rss(url: str, apikey: str | None, limit: int = 40) -> list[dict[str, Any]]:
    """Fetch recent releases via Torznab search with empty/broad query."""
    params = {"t": "search", "q": "", "limit": str(limit)}
    if apikey:
        params["apikey"] = apikey
    # Some indexers need t=search with cat
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            text = r.text
    except Exception as e:
        log.debug("torznab fetch %s: %s", url, e)
        return []

    out: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    ns = {"t": "http://torznab.com/schemas/2015/feed"}
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link or title).strip()
        size = None
        magnet = ""
        for attr in item.findall("t:attr", ns) + item.findall("{http://torznab.com/schemas/2015/feed}attr"):
            name = attr.attrib.get("name", "")
            val = attr.attrib.get("value", "")
            if name == "size":
                try:
                    size = int(val)
                except ValueError:
                    pass
            if name == "magneturl":
                magnet = val
        enclosure = item.find("enclosure")
        if enclosure is not None and not link:
            link = enclosure.attrib.get("url") or link
        out.append(
            {
                "title": title,
                "link": link,
                "magnet": magnet,
                "guid": guid,
                "size": size,
            }
        )
    return out


def _already_seen(state: dict, guid: str) -> bool:
    seen = state.get("seen_guids") or []
    return guid in seen


def _mark_seen(state: dict, guid: str) -> None:
    seen = list(state.get("seen_guids") or [])
    if guid not in seen:
        seen.insert(0, guid)
    state["seen_guids"] = seen[:2000]


def _enqueue_download(db: Session, release: dict[str, Any], filter_name: str) -> dict[str, Any]:
    """Send magnet/URL to qBittorrent (or record queue row)."""
    from app.config import settings
    from app.clients.qbittorrent import qbittorrent_client

    url = release.get("magnet") or release.get("link") or ""
    title = release.get("title") or "announce"
    if not url:
        return {"ok": False, "error": "no url/magnet"}

    from app.services.vpn import vpn_allows_grabs
    vpn_ok, vpn_reason = vpn_allows_grabs()
    if not vpn_ok:
        log.warning("Announce Lab enqueue blocked: %s", vpn_reason)
        return {"ok": False, "error": vpn_reason}

    client_ok = False
    err = None
    try:
        if getattr(qbittorrent_client, "enabled", lambda: False)() or getattr(settings, "qbit_url", ""):
            save = getattr(settings, "downloads_path", None) or "/downloads"
            qbittorrent_client.add_torrent(url, save_path=str(save), category="mediaos-announce")
            client_ok = True
    except Exception as e:
        err = str(e)
        log.warning("announce enqueue qbit failed: %s", e)

    row = Download(
        media_item_id=None,
        episode_id=None,
        indexer=release.get("indexer") or "announce-lab",
        release_title=title[:500],
        download_url=url[:2000],
        torrent_hash=None,
        status="grabbed" if client_ok else "failed",
    )
    # Optional columns may not all exist — use setattr carefully
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        dl_id = row.id
    except Exception as e:
        db.rollback()
        log.warning("announce Download row: %s", e)
        dl_id = None

    return {
        "ok": client_ok or dl_id is not None,
        "download_id": dl_id,
        "client": "qbittorrent" if client_ok else None,
        "error": err,
        "filter": filter_name,
    }


def run_cycle(db: Session, *, limit_per_indexer: int = 30) -> dict[str, Any]:
    """One poll cycle: fetch from indexers, match filters, enqueue."""
    filters = [f for f in list_filters(db) if f.get("enabled")]
    if not filters:
        return {"ok": True, "matched": 0, "checked": 0, "message": "no enabled filters"}

    state = _get_json(db, STATE_KEY, {"seen_guids": []})
    if not isinstance(state, dict):
        state = {"seen_guids": []}

    indexers = (
        db.query(Indexer)
        .filter(Indexer.enabled.is_(True))
        .all()
    )
    checked = 0
    matched = 0
    actions: list[dict] = []

    for ix in indexers:
        url = (ix.url or "").strip()
        if not url:
            continue
        releases = _fetch_torznab_rss(url, getattr(ix, "api_key", None), limit=limit_per_indexer)
        for rel in releases:
            rel["indexer"] = ix.name or str(ix.id)
            checked += 1
            guid = rel.get("guid") or rel.get("title") or ""
            if not guid or _already_seen(state, guid):
                continue
            title = rel.get("title") or ""
            for f in filters:
                # indexer scope
                allowed = f.get("indexer_ids") or []
                if allowed and ix.id not in allowed and str(ix.id) not in [str(a) for a in allowed]:
                    continue
                if not _title_matches(f, title):
                    continue
                if not _size_ok(f, rel.get("size")):
                    continue
                # match!
                _mark_seen(state, guid)
                matched += 1
                result = {"title": title, "filter": f.get("name"), "indexer": rel["indexer"]}
                if "download" in (f.get("actions") or ["download"]):
                    enq = _enqueue_download(db, rel, f.get("name") or f.get("id"))
                    result["enqueue"] = enq
                hit = {
                    "at": _utcnow().isoformat(),
                    "title": title,
                    "filter_id": f.get("id"),
                    "filter_name": f.get("name"),
                    "indexer": rel["indexer"],
                    "guid": guid,
                    "result": result.get("enqueue"),
                }
                _push_hit(db, hit)
                actions.append(hit)
                break  # first matching filter wins

    state["last_run_at"] = _utcnow().isoformat()
    state["last_checked"] = checked
    state["last_matched"] = matched
    _set_json(db, STATE_KEY, state)

    return {
        "ok": True,
        "checked": checked,
        "matched": matched,
        "actions": actions[:20],
        "filters": len(filters),
        "indexers": len(indexers),
    }


def status(db: Session) -> dict[str, Any]:
    state = _get_json(db, STATE_KEY, {})
    return {
        "filters": list_filters(db),
        "filter_count": len(list_filters(db)),
        "enabled_count": sum(1 for f in list_filters(db) if f.get("enabled")),
        "recent_hits": recent_hits(db)[:50],
        "last_run_at": state.get("last_run_at") if isinstance(state, dict) else None,
        "last_checked": state.get("last_checked") if isinstance(state, dict) else None,
        "last_matched": state.get("last_matched") if isinstance(state, dict) else None,
        "seen_count": len((state or {}).get("seen_guids") or []) if isinstance(state, dict) else 0,
    }
