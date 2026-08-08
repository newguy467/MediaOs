"""jdupes integration — find (and optionally hardlink) duplicate library files."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from app.config import settings

log = logging.getLogger(__name__)


def _binary() -> str | None:
    path = settings.jdupes_path or "jdupes"
    return path if shutil.which(path) or Path(path).exists() else None


def scan_duplicates(paths: list[str], *, apply_hardlinks: bool = False) -> dict:
    """Run jdupes -r on paths. Returns groups of duplicate files."""
    if not settings.jdupes_enabled:
        return {"ok": False, "error": "jdupes disabled", "groups": []}
    bin_ = _binary()
    if not bin_:
        return {"ok": False, "error": "jdupes binary not found on PATH", "groups": []}
    existing = [p for p in paths if Path(p).exists()]
    if not existing:
        return {"ok": False, "error": "no library paths exist", "groups": []}

    cmd = [bin_, "-r", "-A"]  # recurse, no hidden
    if apply_hardlinks and settings.jdupes_hardlink:
        cmd.append("-L")  # hardlink
    cmd.extend(existing)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        # jdupes prints groups separated by blank lines
        groups: list[list[str]] = []
        cur: list[str] = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if not line:
                if len(cur) > 1:
                    groups.append(cur)
                cur = []
            else:
                cur.append(line)
        if len(cur) > 1:
            groups.append(cur)
        return {
            "ok": True,
            "groups": groups,
            "group_count": len(groups),
            "duplicate_files": sum(len(g) for g in groups),
            "applied_hardlinks": bool(apply_hardlinks and settings.jdupes_hardlink),
            "stderr": (r.stderr or "")[:500],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "groups": []}
