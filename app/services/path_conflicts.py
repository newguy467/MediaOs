"""Detect shared / conflicting library and download paths (Hubstarr-style footgun guard)."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import PathMap
from app.services import modules as modsvc

# settings attribute → human label
PATH_KEYS = [
    ("movies_library_path", "Movies library"),
    ("tv_library_path", "TV library"),
    ("music_library_path", "Music library"),
    ("books_library_path", "Books library"),
    ("audiobooks_library_path", "Audiobooks library"),
    ("comics_library_path", "Comics library"),
    ("manga_library_path", "Manga library"),
    ("youtube_library_path", "YouTube library"),
    ("podcasts_library_path", "Podcasts library"),
    ("games_library_path", "Games library"),
    ("adult_library_path", "Adult library"),
    ("downloads_path", "Downloads"),
]


def _norm(p: str | None) -> str | None:
    if not p or not str(p).strip():
        return None
    s = str(p).strip().replace("\\", "/")
    while "//" in s:
        s = s.replace("//", "/")
    if len(s) > 1 and s.endswith("/"):
        s = s[:-1]
    return s.lower()


def _is_host_looking(path: str) -> bool:
    """Heuristic: Windows drive or /mnt /Users /home often mean host path mistaken for container."""
    p = path.replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        return True
    low = p.lower()
    for prefix in ("/users/", "/home/", "/mnt/", "/volumes/", "/media/", "c:/", "d:/"):
        if low.startswith(prefix) or low.startswith(prefix.lstrip("/")):
            return True
    return False


def scan_settings_paths() -> list[dict[str, Any]]:
    """Return configured paths from settings with metadata."""
    rows = []
    for key, label in PATH_KEYS:
        raw = getattr(settings, key, None) or ""
        norm = _norm(raw)
        rows.append({
            "key": key,
            "label": label,
            "path": str(raw).strip() if raw else "",
            "normalized": norm,
            "empty": not norm,
            "looks_like_host_path": _is_host_looking(str(raw)) if raw else False,
        })
    return rows


def detect_duplicate_paths(paths: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    paths = paths if paths is not None else scan_settings_paths()
    by_norm: dict[str, list[dict]] = {}
    for p in paths:
        n = p.get("normalized")
        if not n:
            continue
        by_norm.setdefault(n, []).append(p)
    issues = []
    for n, owners in by_norm.items():
        if len(owners) < 2:
            continue
        # downloads sharing with a library is especially dangerous
        keys = [o["key"] for o in owners]
        severity = "error" if "downloads_path" in keys else "warning"
        issues.append({
            "type": "duplicate_path",
            "severity": severity,
            "path": owners[0].get("path"),
            "normalized": n,
            "keys": keys,
            "labels": [o["label"] for o in owners],
            "message": f"Same path used by: {', '.join(o['label'] for o in owners)}",
        })
    return issues


def detect_host_path_warnings(paths: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    paths = paths if paths is not None else scan_settings_paths()
    out = []
    for p in paths:
        if p.get("looks_like_host_path"):
            out.append({
                "type": "host_path_heuristic",
                "severity": "warning",
                "key": p["key"],
                "label": p["label"],
                "path": p["path"],
                "message": (
                    f"{p['label']} looks like a host path ({p['path']}). "
                    "Inside Docker, apps usually need the container path "
                    "(e.g. /movies). Map host→container with PathMap."
                ),
            })
    return out


def detect_pathmap_gaps(db: Session) -> list[dict[str, Any]]:
    rows = db.query(PathMap).filter(PathMap.enabled.is_(True)).all() if hasattr(db, "query") else []
    issues = []
    if not rows:
        # only warn if any path looks host-like
        if detect_host_path_warnings():
            issues.append({
                "type": "pathmap_missing",
                "severity": "info",
                "message": "Host-like paths detected and no PathMap rules enabled. Add container→host maps under Library tools.",
            })
    return issues


def detect_module_path_gaps(db: Session) -> list[dict[str, Any]]:
    st = modsvc.status(db)
    issues = []
    for m in st.get("catalog") or []:
        if m.get("needs_path_setup"):
            issues.append({
                "type": "module_path_missing",
                "severity": "warning",
                "module": m.get("id"),
                "label": m.get("label"),
                "path_key": m.get("requires_path"),
                "message": f"Module '{m.get('label')}' is on but path is empty ({m.get('path_label') or m.get('requires_path')})",
            })
    for c in st.get("conflicts") or []:
        issues.append({**c, "severity": c.get("severity") or "warning"})
    return issues


def full_report(db: Session) -> dict[str, Any]:
    paths = scan_settings_paths()
    issues = []
    issues.extend(detect_duplicate_paths(paths))
    issues.extend(detect_host_path_warnings(paths))
    issues.extend(detect_pathmap_gaps(db))
    issues.extend(detect_module_path_gaps(db))
    return {
        "ok": not any(i.get("severity") == "error" for i in issues),
        "paths": paths,
        "issues": issues,
        "counts": {
            "error": sum(1 for i in issues if i.get("severity") == "error"),
            "warning": sum(1 for i in issues if i.get("severity") == "warning"),
            "info": sum(1 for i in issues if i.get("severity") == "info"),
        },
    }
