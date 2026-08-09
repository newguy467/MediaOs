"""Automatic Cardigann definition sync from Jackett's upstream YAML tree.

On startup (optional) and on a weekly schedule, pulls public/compatible
definitions so new installs work without a manual git/script step.
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

JACKETT_TREE_URL = (
    "https://api.github.com/repos/Jackett/Jackett/git/trees/master"
    "?recursive=1"
)
JACKETT_RAW = (
    "https://raw.githubusercontent.com/Jackett/Jackett/master/"
    "src/Jackett.Common/Definitions"
)

# Prefer these public / widely useful defs first when doing a partial seed
PRIORITY_IDS = {
    "1337x", "thepiratebay", "yts", "eztv", "nyaa", "nyaasi", "limetorrents",
    "torrentdownloads", "bitsearch", "torrentscsv", "knaben", "bt4g",
    "rutracker", "rarbg", "therarbg", "magnetz", "milkie", "torrentgalaxyclone",
    "scenetime", "ncore", "digitalcore", "seedpool", "oldtoonsworld", "kinozal",
    "kinozal-magnet", "solidtorrents", "torrentgalaxy", "zooqle", "glotorrents",
    "showrss", "acgrip", "anidex", "shizaproject", "subsplease", "erai-raws",
}


def _dest_dir() -> Path:
    from app.config import settings
    from app.services.cardigann import definitions_dir

    # Prefer writable config mount for auto-synced files; fall back to image path
    configured = Path(
        getattr(settings, "cardigann_definitions_path", None) or "/app/definitions"
    )
    config_alt = Path("/config/cardigann")
    for candidate in (configured, config_alt, definitions_dir()):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.write_text("ok")
            probe.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue
    return configured


def _list_remote_yml() -> list[str]:
    """Return definition basenames (e.g. yts.yml) via GitHub git trees API."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "MediaOs-DefSync/3.0"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=60.0, headers=headers, follow_redirects=True) as client:
        r = client.get(JACKETT_TREE_URL)
        r.raise_for_status()
        data = r.json()
    out: list[str] = []
    prefix = "src/Jackett.Common/Definitions/"
    for item in data.get("tree") or []:
        path = item.get("path") or ""
        if item.get("type") != "blob":
            continue
        if not path.startswith(prefix):
            continue
        name = path[len(prefix) :]
        if "/" in name:
            continue
        if name.endswith(".yml") or name.endswith(".yaml"):
            out.append(name)
    return sorted(out)


def _download_one(name: str, dest: Path, client: httpx.Client) -> str | None:
    """Download a single def. Returns 'added'|'updated'|'skipped'|None on hard fail."""
    target = dest / name
    # Protect local customizations
    if target.is_file():
        try:
            if "mediaos-local" in target.read_text(encoding="utf-8", errors="ignore"):
                return "skipped"
        except Exception:
            pass
    url = f"{JACKETT_RAW}/{name}"
    try:
        r = client.get(url)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        body = r.text
        if not body.strip().startswith("---") and "id:" not in body[:200]:
            # rough sanity check
            if "name:" not in body[:400]:
                return None
        if target.is_file() and target.read_text(encoding="utf-8", errors="ignore") == body:
            return "skipped"
        target.write_text(body, encoding="utf-8")
        return "updated" if target.is_file() else "added"
    except Exception as e:
        log.debug("def download %s: %s", name, e)
        return None


def sync_definitions(
    *,
    max_files: int | None = None,
    priority_only: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """
    Pull Jackett Cardigann YAML definitions into the local definitions dir.

    - priority_only: only the PRIORITY_IDS set (fast seed for first boot)
    - max_files: cap downloads (rate-limit friendly)
    - force: re-download even if identical
    """
    from app.config import settings

    if not getattr(settings, "cardigann_auto_sync", True) and not force:
        return {"ok": False, "error": "cardigann_auto_sync disabled", "added": 0, "updated": 0}

    dest = _dest_dir()
    started = time.time()
    try:
        names = _list_remote_yml()
    except Exception as e:
        log.warning("definition sync: list remote failed: %s", e)
        return {"ok": False, "error": str(e), "added": 0, "updated": 0, "dest": str(dest)}

    if priority_only:
        names = [n for n in names if Path(n).stem in PRIORITY_IDS]
    if max_files and max_files > 0:
        # priority first, then the rest
        pri = [n for n in names if Path(n).stem in PRIORITY_IDS]
        rest = [n for n in names if n not in pri]
        names = (pri + rest)[:max_files]

    added = updated = skipped = failed = 0
    headers = {"User-Agent": "MediaOs-DefSync/3.0"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
        # modest parallelism
        workers = int(getattr(__import__('app.config', fromlist=['settings']).settings, 'cardigann_sync_workers', 8) or 8)
    with ThreadPoolExecutor(max_workers=max(2, min(workers, 16))) as pool:
            futs = {pool.submit(_download_one, n, dest, client): n for n in names}
            for fut in as_completed(futs):
                result = fut.result()
                if result == "added":
                    added += 1
                elif result == "updated":
                    updated += 1
                elif result == "skipped":
                    skipped += 1
                else:
                    failed += 1

    elapsed = round(time.time() - started, 1)
    # Invalidate cardigann in-memory cache if any
    try:
        from app.services import cardigann as cg
        if hasattr(cg, "_cache_clear"):
            cg._cache_clear()
        # clear list cache by touching module-level if present
        for attr in ("_DEF_CACHE", "_def_cache", "DEFINITION_CACHE"):
            if hasattr(cg, attr):
                setattr(cg, attr, None)
    except Exception:
        pass

    log.info(
        "Cardigann def sync: +%s ~%s skip=%s fail=%s total_remote=%s dest=%s (%.1fs)",
        added, updated, skipped, failed, len(names), dest, elapsed,
    )
    return {
        "ok": True,
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "remote": len(names),
        "dest": str(dest),
        "elapsed_sec": elapsed,
    }


def ensure_seed_definitions() -> dict[str, Any]:
    """If the definitions folder is nearly empty, pull the priority public set."""
    dest = _dest_dir()
    existing = list(dest.glob("*.yml")) + list(dest.glob("*.yaml"))
    # README doesn't count
    ymls = [p for p in existing if p.name.lower() != "readme.md"]
    if len(ymls) >= 15:
        return {"ok": True, "seeded": False, "existing": len(ymls), "dest": str(dest)}
    log.info("Cardigann definitions sparse (%s files) — seeding priority pack", len(ymls))
    result = sync_definitions(priority_only=True, force=True)
    result["seeded"] = True
    return result
