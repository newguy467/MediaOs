#!/usr/bin/env python3
"""Static UI health checks: icons, critical imports, no dead v2 monolith required."""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ui" / "src"


def main() -> int:
    if not SRC.is_dir():
        print("ERROR: ui/src missing", file=sys.stderr)
        return 1
    errors: list[str] = []

    icons_path = SRC / "icons.jsx"
    icons_text = icons_path.read_text(encoding="utf-8") if icons_path.exists() else ""
    keys = set(re.findall(r"^\s{2}(\w+):\s+", icons_text, re.M))

    used: set[str] = set()
    for p in SRC.rglob("*.jsx"):
        t = p.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"\bIc\.(\w+)", t):
            used.add(m.group(1))
        # api import
        if re.search(r"\bapi\.", t) and not re.search(r"import\s+\{[^}]*\bapi\b", t):
            if p.name != "api.js":
                errors.append(f"{p.relative_to(SRC)}: uses api. without importing api")

    missing = used - keys
    if missing:
        errors.append(f"icons.jsx missing keys: {sorted(missing)}")

    app = (SRC / "app.jsx").read_text(encoding="utf-8", errors="ignore")
    for mod in ("games", "manga", "podcasts", "youtube", "adult"):
        if f"mod: '{mod}'" not in app and f'mod: "{mod}"' not in app:
            errors.append(f"app.jsx: sidebar missing mod gate for {mod}")

    if "function LoginModal" not in app and "LoginModal" not in app:
        errors.append("app.jsx: LoginModal missing")

    v2 = SRC / "pages" / "v2.jsx"
    if v2.exists() and v2.stat().st_size > 5000:
        errors.append("pages/v2.jsx still looks like a large monolith; prefer split pages")

    if errors:
        print("UI static check FAILED:", file=sys.stderr)
        for e in errors:
            print(" -", e, file=sys.stderr)
        return 1
    print(f"UI static check OK ({len(list(SRC.rglob('*.jsx')))} jsx files, {len(used)} icons used)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
