"""
Backup / restore helpers (MediaOS v2 ops).

Creates a zip of config + SQLite DB (or notes for Postgres).
"""
from __future__ import annotations

import json
import logging
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

log = logging.getLogger("mediaos.backup")


def _utcnow_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_backup(dest_dir: str | Path | None = None, *, include_db: bool = True, include_config: bool = True, note: str | None = None) -> dict[str, Any]:
    """
    Bundle SQLite DB + .env-style config snapshot + key JSON settings into a zip.
    Returns path and metadata.
    """
    dest_root = Path(dest_dir or getattr(settings, "data_path", None) or "/data")
    dest_root.mkdir(parents=True, exist_ok=True)
    stamp = _utcnow_slug()
    zip_path = dest_root / f"mediaos-backup-{stamp}.zip"

    db_path = Path(getattr(settings, "database_url", "sqlite:///./mediaos.db").replace("sqlite:///", ""))
    # common docker path
    candidates = [
        db_path,
        Path("/data/mediaos.db"),
        Path("./mediaos.db"),
        Path("data/mediaos.db"),
    ]

    if not include_db and not include_config:
        return {"ok": False, "error": "Nothing to include: enable database and/or config"}
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        meta = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": __import__("app.version", fromlist=["get_version"]).get_version(),
            "include_db": bool(include_db),
            "include_config": bool(include_config),
            "note": (note or "").strip() or None,
            "files": [],
        }
        if include_db:
            for c in candidates:
                if c.exists() and c.is_file():
                    zf.write(c, arcname=f"db/{c.name}")
                    meta["files"].append(f"db/{c.name}")
                    break
        if include_config:
            for name in (".env", "config.json", "settings.json"):
                p = Path(name)
                if p.exists():
                    zf.write(p, arcname=f"config/{name}")
                    meta["files"].append(f"config/{name}")
        zf.writestr("backup-meta.json", json.dumps(meta, indent=2))

    return {
        "ok": True,
        "path": str(zip_path),
        "size_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
        "created_at": meta["created_at"],
        "files": meta["files"],
        "include_db": bool(include_db),
        "include_config": bool(include_config),
        "note": meta.get("note"),
    }


def list_backups(dest_dir: str | Path | None = None) -> list[dict[str, Any]]:
    dest_root = Path(dest_dir or getattr(settings, "data_path", None) or "/data")
    if not dest_root.exists():
        return []
    out = []
    for p in sorted(dest_root.glob("mediaos-backup-*.zip"), reverse=True):
        out.append({
            "name": p.name,
            "path": str(p),
            "size_bytes": p.stat().st_size,
            "modified_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
        })
    return out


def restore_backup(zip_path: str | Path, *, dest_db: str | Path | None = None) -> dict[str, Any]:
    """Restore DB (+ optional config) from a backup zip created by create_backup."""
    zp = Path(zip_path)
    if not zp.exists():
        raise FileNotFoundError(f"Backup not found: {zp}")
    restore_root = Path(getattr(settings, "data_path", None) or "/data")
    restore_root.mkdir(parents=True, exist_ok=True)
    config_root = Path(".").resolve()
    restored = []
    with zipfile.ZipFile(zp, "r") as zf:
        names = zf.namelist()
        meta = {}
        if "backup-meta.json" in names:
            meta = json.loads(zf.read("backup-meta.json").decode())
        for name in names:
            if name.startswith("db/") and not name.endswith("/"):
                # Path(...).name already strips any directory components /
                # traversal segments from the zip entry, so this side was
                # already safe against a malicious zip.
                target = Path(dest_db) if dest_db else restore_root / Path(name).name
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
                restored.append(str(target))
            elif name.startswith("config/") and not name.endswith("/"):
                # Zip-slip guard: a backup zip is an untrusted input (it may
                # have been shared/downloaded, not just self-created), so a
                # crafted entry name like "config/../../etc/cron.d/x" must
                # not be able to write outside config_root. Only the
                # basename is trusted; anything that still resolves outside
                # config_root after that is rejected rather than silently
                # re-rooted, since silently renaming a config file could
                # itself cause confusing restore behavior.
                safe_name = Path(name.split("/", 1)[-1]).name
                if not safe_name:
                    continue
                target = (config_root / safe_name).resolve()
                if target != config_root and config_root not in target.parents:
                    log.warning("Skipping unsafe backup zip entry: %r", name)
                    continue
                with zf.open(name) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
                restored.append(str(target))
    return {
        "ok": True,
        "restored": restored,
        "meta": meta,
        "note": "Restart MediaOS after DB restore so connections pick up the file.",
    }
