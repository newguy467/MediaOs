#!/usr/bin/env python3
"""Verify VERSION, package.json, and optional package-lock agree."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ver_path = ROOT / "VERSION"
    if not ver_path.exists():
        print("ERROR: VERSION file missing", file=sys.stderr)
        return 1
    version = ver_path.read_text(encoding="utf-8").strip()
    if not version:
        print("ERROR: VERSION empty", file=sys.stderr)
        return 1
    # Accepts strict semver (1.2.3) as well as this project's beta-style
    # tags (e.g. "1.01beta") — just requires a leading `<digits>.<digits>`.
    if not re.match(r"^\d+\.\d+", version):
        print(f"ERROR: VERSION looks invalid: {version!r}", file=sys.stderr)
        return 1

    pj_path = ROOT / "package.json"
    if pj_path.exists():
        pj = json.loads(pj_path.read_text(encoding="utf-8"))
        pj_ver = pj.get("version", "")
        if pj_ver != version:
            print(f"ERROR: package.json version {pj_ver!r} != VERSION {version!r}", file=sys.stderr)
            return 1

    pl_path = ROOT / "package-lock.json"
    if pl_path.exists():
        # soft: only check top-level name mediaos-ui block
        text = pl_path.read_text(encoding="utf-8")
        m = re.search(r'"name":\s*"mediaos-ui",\s*"version":\s*"([^"]+)"', text)
        if m and m.group(1) != version:
            print(
                f"ERROR: package-lock mediaos-ui version {m.group(1)!r} != VERSION {version!r}",
                file=sys.stderr,
            )
            return 1

    # Changelog should mention current version somewhere (soft warning)
    cl = ROOT / "CHANGELOG.md"
    if cl.exists() and version not in cl.read_text(encoding="utf-8", errors="ignore"):
        print(f"WARN: CHANGELOG.md does not mention {version}", file=sys.stderr)

    print(f"Version check OK ({version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
