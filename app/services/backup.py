"""
Backup / restore helpers (MediaOS v2 ops).

Creates a zip of config + database (Postgres via pg_dump, or SQLite file
directly) + key JSON settings.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

log = logging.getLogger("mediaos.backup")

# Matches the /app/data volume mount declared in docker-compose.yml
# (${MEDIAOS_DATA_PATH:-./data/mediaos}:/app/data). Do not confuse this
# in-container path with the MEDIAOS_DATA_PATH env var, which sets the
# *host* side of that same mount.
DEFAULT_DATA_DIR = "/app/data"

_PG_TIMEOUT_SECONDS = 300


def _utcnow_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_postgres(url: str) -> bool:
    return url.startswith("postgresql://") or url.startswith("postgres://")


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite:///")


def _pg_dump(database_url: str) -> tuple[bool, bytes, str]:
    """Run pg_dump against database_url. Returns (ok, sql_bytes, error)."""
    pg_dump_bin = shutil.which("pg_dump") or "pg_dump"
    try:
        proc = subprocess.run(
            [pg_dump_bin, "--no-owner", "--no-privileges", "--dbname", database_url],
            capture_output=True, timeout=_PG_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return False, b"", "pg_dump not found on PATH (postgresql-client not installed in image)"
    except subprocess.TimeoutExpired:
        return False, b"", f"pg_dump timed out after {_PG_TIMEOUT_SECONDS}s"
    if proc.returncode != 0:
        return False, b"", (proc.stderr or b"").decode(errors="replace")[:2000]
    return True, proc.stdout, ""


def _psql_restore(database_url: str, sql_bytes: bytes) -> tuple[bool, str]:
    psql_bin = shutil.which("psql") or "psql"
    try:
        proc = subprocess.run(
            [psql_bin, "--dbname", database_url, "-v", "ON_ERROR_STOP=1"],
            input=sql_bytes, capture_output=True, timeout=_PG_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return False, "psql not found on PATH (postgresql-client not installed in image)"
    except subprocess.TimeoutExpired:
        return False, f"psql timed out after {_PG_TIMEOUT_SECONDS}s"
    if proc.returncode != 0:
        return False, (proc.stderr or b"").decode(errors="replace")[:2000]
    return True, ""


def create_backup(dest_dir: str | Path | None = None, *, include_db: bool = True, include_config: bool = True, note: str | None = None) -> dict[str, Any]:
    """
    Bundle the database (Postgres dump or SQLite file) + .env-style config
    snapshot into a zip. Returns path and metadata, including any warnings
    about content that could not be captured (callers should surface these
    rather than treat `ok: True` as "everything was backed up").
    """
    dest_root = Path(dest_dir or DEFAULT_DATA_DIR)
    dest_root.mkdir(parents=True, exist_ok=True)
    stamp = _utcnow_slug()
    zip_path = dest_root / f"mediaos-backup-{stamp}.zip"

    if not include_db and not include_config:
        return {"ok": False, "error": "Nothing to include: enable database and/or config"}

    warnings: list[str] = []
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
            db_url = getattr(settings, "database_url", "") or ""
            if _is_postgres(db_url):
                ok, dump_bytes, err = _pg_dump(db_url)
                if ok:
                    zf.writestr("db/postgres-dump.sql", dump_bytes)
                    meta["files"].append("db/postgres-dump.sql")
                    meta["db_engine"] = "postgresql"
                else:
                    warnings.append(f"Database NOT backed up (Postgres): {err}")
                    log.warning("Postgres backup failed: %s", err)
            elif _is_sqlite(db_url):
                db_path = Path(db_url.replace("sqlite:///", ""))
                candidates = [db_path, Path(DEFAULT_DATA_DIR) / "mediaos.db", Path("./mediaos.db"), Path("data/mediaos.db")]
                for c in candidates:
                    if c.exists() and c.is_file():
                        zf.write(c, arcname=f"db/{c.name}")
                        meta["files"].append(f"db/{c.name}")
                        meta["db_engine"] = "sqlite"
                        break
                else:
                    warnings.append("Database NOT backed up: no SQLite file found at expected paths")
            else:
                warnings.append(f"Database NOT backed up: unrecognized DATABASE_URL scheme ({db_url.split(':')[0] if db_url else 'unset'})")
        if include_config:
            for name in (".env", "config.json", "settings.json"):
                p = Path(name)
                if p.exists():
                    zf.write(p, arcname=f"config/{name}")
                    meta["files"].append(f"config/{name}")
        meta["warnings"] = warnings
        zf.writestr("backup-meta.json", json.dumps(meta, indent=2))

    db_backed_up = any(f.startswith("db/") for f in meta["files"])
    return {
        "ok": True,
        "path": str(zip_path),
        "size_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
        "created_at": meta["created_at"],
        "files": meta["files"],
        "include_db": bool(include_db),
        "include_config": bool(include_config),
        "db_backed_up": db_backed_up,
        "warnings": warnings,
        "note": meta.get("note"),
    }


def list_backups(dest_dir: str | Path | None = None) -> list[dict[str, Any]]:
    dest_root = Path(dest_dir or DEFAULT_DATA_DIR)
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
    """
    Restore DB (+ optional config) from a backup zip created by create_backup.

    `dest_db` is overloaded to match the entry being restored: for a SQLite
    entry it's treated as a destination file path; for a Postgres dump it's
    treated as a destination connection URL (falls back to the current
    DATABASE_URL if not given).
    """
    zp = Path(zip_path)
    if not zp.exists():
        raise FileNotFoundError(f"Backup not found: {zp}")
    restore_root = Path(DEFAULT_DATA_DIR)
    restore_root.mkdir(parents=True, exist_ok=True)
    config_root = Path(".").resolve()
    restored = []
    warnings: list[str] = []
    with zipfile.ZipFile(zp, "r") as zf:
        names = zf.namelist()
        meta = {}
        if "backup-meta.json" in names:
            meta = json.loads(zf.read("backup-meta.json").decode())
        for name in names:
            if name == "db/postgres-dump.sql":
                sql_bytes = zf.read(name)
                target_url = str(dest_db) if dest_db else (getattr(settings, "database_url", "") or "")
                if _is_postgres(target_url):
                    ok, err = _psql_restore(target_url, sql_bytes)
                    if ok:
                        restored.append("postgresql (via psql)")
                    else:
                        warnings.append(f"Postgres restore failed: {err}")
                else:
                    warnings.append("Backup contains a Postgres dump but the target DATABASE_URL is not Postgres; skipped")
            elif name.startswith("db/") and not name.endswith("/"):
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
        "warnings": warnings,
        "meta": meta,
        "note": "Restart MediaOS after DB restore so connections pick up the changes.",
    }
