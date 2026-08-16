"""Pre-flight validation + dry-run for *arr imports (Sonarr/Radarr/Lidarr/Readarr).

Protects absorbed cores: connection, schema shape, sample counts, and
side-by-side comparison against MediaOS before a destructive-feeling import.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import MediaItem, MediaType

log = logging.getLogger("mediaos.arr_validation")


def _client(base_url: str, api_key: str) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={"X-Api-Key": api_key},
        timeout=45.0,
    )


_STATUS_PATHS = {
    "sonarr": "/api/v3/system/status",
    "radarr": "/api/v3/system/status",
    "lidarr": "/api/v1/system/status",
    "readarr": "/api/v1/system/status",
    "prowlarr": "/api/v1/system/status",
    "whisparr": "/api/v3/system/status",
}

_LIBRARY_PATHS = {
    "sonarr": ("/api/v3/series", "tv"),
    "radarr": ("/api/v3/movie", "movie"),
    "lidarr": ("/api/v1/artist", "music"),
    "readarr": ("/api/v1/author", "book"),
    "whisparr": ("/api/v3/movie", "adult"),
}


def validate_connection(url: str, api_key: str, kind: str = "sonarr") -> dict[str, Any]:
    """Ping system/status and report version / auth health."""
    kind = (kind or "sonarr").lower().strip()
    path = _STATUS_PATHS.get(kind, "/api/v3/system/status")
    out: dict[str, Any] = {
        "ok": False,
        "kind": kind,
        "url": url.rstrip("/"),
        "status_path": path,
        "http_status": None,
        "version": None,
        "app_name": None,
        "error": None,
    }
    try:
        with _client(url, api_key) as client:
            r = client.get(path)
            out["http_status"] = r.status_code
            if r.status_code >= 400:
                out["error"] = f"HTTP {r.status_code}: {r.text[:200]}"
                return out
            data = {}
            try:
                data = r.json()
            except Exception:
                out["error"] = "Non-JSON status response"
                return out
            out["ok"] = True
            out["version"] = data.get("version") or data.get("appVersion")
            out["app_name"] = data.get("appName") or data.get("instanceName") or kind
            out["is_docker"] = data.get("isDocker")
            out["runtime"] = data.get("runtimeVersion")
    except Exception as e:
        out["error"] = str(e)
    return out


def validate_library_shape(url: str, api_key: str, kind: str = "sonarr") -> dict[str, Any]:
    """Fetch library endpoint and validate expected fields exist on sample rows."""
    kind = (kind or "sonarr").lower().strip()
    lib = _LIBRARY_PATHS.get(kind)
    if not lib:
        return {"ok": False, "error": f"Unsupported kind for library validation: {kind}"}
    path, media_type = lib
    required_by_kind = {
        "sonarr": ["title", "id"],
        "radarr": ["title", "id", "tmdbId"],
        "lidarr": ["artistName", "id"],
        "readarr": ["authorName", "id"],
        "whisparr": ["title", "id"],
    }
    required = required_by_kind.get(kind, ["id"])
    out: dict[str, Any] = {
        "ok": False,
        "kind": kind,
        "media_type": media_type,
        "path": path,
        "count": 0,
        "sample": [],
        "missing_fields": [],
        "error": None,
    }
    try:
        with _client(url, api_key) as client:
            r = client.get(path)
            r.raise_for_status()
            rows = r.json()
            if not isinstance(rows, list):
                out["error"] = "Library endpoint did not return a list"
                return out
            out["count"] = len(rows)
            # sample up to 5
            for row in rows[:5]:
                sample = {k: row.get(k) for k in list(row.keys())[:12]}
                out["sample"].append(sample)
            missing = set()
            for row in rows[:20]:
                for f in required:
                    if row.get(f) in (None, ""):
                        missing.add(f)
            out["missing_fields"] = sorted(missing)
            out["ok"] = len(missing) == 0 or out["count"] == 0
            if out["count"] == 0:
                out["ok"] = True  # empty library is valid
                out["note"] = "Library empty — import would be a no-op"
    except Exception as e:
        out["error"] = str(e)
    return out


def side_by_side(db: Session, url: str, api_key: str, kind: str = "sonarr") -> dict[str, Any]:
    """Compare remote *arr library counts/IDs vs MediaOS without writing."""
    kind = (kind or "sonarr").lower().strip()
    lib = _LIBRARY_PATHS.get(kind)
    if not lib:
        return {"ok": False, "error": f"Unsupported kind: {kind}"}
    path, media_type = lib
    try:
        mt = MediaType(media_type) if media_type in MediaType.__members__.values() or media_type in [e.value for e in MediaType] else None
    except Exception:
        mt = None
    # resolve MediaType enum safely
    mt_enum = None
    for e in MediaType:
        if e.value == media_type:
            mt_enum = e
            break

    remote_ids: set[str] = set()
    remote_titles = 0
    try:
        with _client(url, api_key) as client:
            r = client.get(path)
            r.raise_for_status()
            rows = r.json() if isinstance(r.json(), list) else []
            remote_titles = len(rows)
            for row in rows:
                if kind == "radarr":
                    tid = row.get("tmdbId") or row.get("tmdb_id")
                    if tid:
                        remote_ids.add(f"tmdb:{tid}")
                elif kind == "sonarr":
                    tid = row.get("tvdbId") or row.get("tmdbId") or row.get("id")
                    if tid:
                        remote_ids.add(f"tv:{tid}")
                else:
                    rid = row.get("foreignArtistId") or row.get("foreignAuthorId") or row.get("id")
                    if rid:
                        remote_ids.add(str(rid))
    except Exception as e:
        return {"ok": False, "error": str(e), "kind": kind}

    q = db.query(MediaItem)
    if mt_enum is not None:
        q = q.filter(MediaItem.media_type == mt_enum)
    local_rows = q.all()
    local_ids: set[str] = set()
    for it in local_rows:
        if it.external_id is not None:
            src = (it.external_source or "").lower() or "id"
            local_ids.add(f"{src}:{it.external_id}")
            local_ids.add(str(it.external_id))

    only_remote = sorted(remote_ids - local_ids)[:50]
    only_local_count = max(0, len(local_rows) - len(remote_ids & local_ids))
    overlap = len(remote_ids & local_ids)

    return {
        "ok": True,
        "kind": kind,
        "media_type": media_type,
        "remote_count": remote_titles,
        "local_count": len(local_rows),
        "overlap_estimate": overlap,
        "only_remote_sample": only_remote,
        "would_add_estimate": max(0, remote_titles - overlap),
        "note": "Dry-run only — no rows written. Run POST /api/migrate/{kind} to import.",
    }


def full_preflight(db: Session, url: str, api_key: str, kind: str = "sonarr") -> dict[str, Any]:
    """Connection + library shape + side-by-side in one shot."""
    conn = validate_connection(url, api_key, kind)
    shape = validate_library_shape(url, api_key, kind) if conn.get("ok") else {"ok": False, "skipped": True}
    sbs = side_by_side(db, url, api_key, kind) if conn.get("ok") else {"ok": False, "skipped": True}
    return {
        "ok": bool(conn.get("ok") and shape.get("ok") and sbs.get("ok")),
        "connection": conn,
        "library": shape,
        "side_by_side": sbs,
        "recommendation": (
            "Safe to import" if conn.get("ok") and shape.get("ok")
            else "Fix connection/library issues before import"
        ),
    }
