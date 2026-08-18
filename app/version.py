"""Single source of version for runtime, diagnostics, backup metadata."""
from __future__ import annotations
import os
from pathlib import Path

_VERSION_FALLBACK = "1.02beta"


def get_version() -> str:
    env = (os.environ.get("APP_VERSION") or "").strip()
    if env:
        return env
    for candidate in (Path("VERSION"), Path("/app/VERSION")):
        try:
            if candidate.exists():
                return candidate.read_text().strip() or _VERSION_FALLBACK
        except Exception:
            pass
    return _VERSION_FALLBACK
