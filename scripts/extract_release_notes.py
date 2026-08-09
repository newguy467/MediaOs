#!/usr/bin/env python3
"""Extract the current version's section from CHANGELOG.md into RELEASE_NOTES.md.

This is the single source of truth going forward: update CHANGELOG.md, bump
VERSION, tag `vX.Y.Z` — release.yml runs this script before building the zip
and publishing the GitHub Release, so RELEASE_NOTES.md (and the release body)
are always derived from CHANGELOG.md, never hand-maintained separately.

Usage:
  python3 scripts/extract_release_notes.py            # uses VERSION file
  python3 scripts/extract_release_notes.py 4.13.2      # explicit version
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extract(version: str, changelog_text: str) -> str:
    """Return the Markdown body of the '## {version} — ...' section."""
    lines = changelog_text.splitlines()
    start = None
    header_pat = re.compile(r"^##\s+" + re.escape(version) + r"\b")
    for i, line in enumerate(lines):
        if header_pat.match(line):
            start = i
            break
    if start is None:
        raise SystemExit(
            f"No '## {version}' section found in CHANGELOG.md. "
            "Add an entry there before tagging."
        )
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    section = lines[start:end]
    # Drop the leading '## {version} — {date}' line, keep the rest as body,
    # trim trailing blank lines.
    body = section[1:]
    while body and not body[-1].strip():
        body.pop()
    header_line = section[0]
    m = re.match(r"^##\s+(\S+)\s*(?:—|-)?\s*(.*)$", header_line)
    date = m.group(2).strip() if m else ""
    title = f"# MediaOs v{version}"
    if date:
        title += f" ({date})"
    return title + "\n\n" + "\n".join(body).strip() + "\n"


def main() -> None:
    version = sys.argv[1] if len(sys.argv) > 1 else (ROOT / "VERSION").read_text().strip()
    changelog = (ROOT / "CHANGELOG.md").read_text()
    notes = extract(version, changelog)
    (ROOT / "RELEASE_NOTES.md").write_text(notes)
    (ROOT / f"GITHUB_RELEASE_v{version}.md").write_text(notes)
    print(f"RELEASE_NOTES.md + GITHUB_RELEASE_v{version}.md generated from CHANGELOG.md")


if __name__ == "__main__":
    main()
