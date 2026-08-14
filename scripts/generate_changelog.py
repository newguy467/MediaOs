#!/usr/bin/env python3
"""
MediaOS changelog automation.

Usage:
  python scripts/generate_changelog.py                    # preview from VERSION + git/fragments
  python scripts/generate_changelog.py --write             # prepend to CHANGELOG.md + RELEASE_NOTES.md
  python scripts/generate_changelog.py --version 2.0.20-dev --write
  python scripts/generate_changelog.py --note "Fix sidebar Games gate" --note "Add /login"
  python scripts/generate_changelog.py --from-git --write  # commits since last tag/VERSION bump
  python scripts/generate_changelog.py --from-fragments --write  # changelog.d/*.md then archive

Fragment files (optional): changelog.d/*.md
  Each file is one bullet section; filename prefix orders them (e.g. 10-sidebar.md).

Exit codes: 0 ok, 1 error, 2 nothing to release
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
CHANGELOG = ROOT / "CHANGELOG.md"
RELEASE_NOTES = ROOT / "RELEASE_NOTES.md"
FRAGMENTS_DIR = ROOT / "changelog.d"
ARCHIVE_DIR = FRAGMENTS_DIR / "released"


def read_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0-dev"


def write_version(version: str) -> None:
    VERSION_FILE.write_text(version.rstrip() + "\n", encoding="utf-8")


def bump_package_json(version: str) -> None:
    pj = ROOT / "package.json"
    if not pj.exists():
        return
    text = pj.read_text(encoding="utf-8")
    text2, n = re.subn(r'"version":\s*"[^"]+"', f'"version": "{version}"', text, count=1)
    if n:
        pj.write_text(text2, encoding="utf-8")


def bump_package_lock(version: str) -> None:
    pl = ROOT / "package-lock.json"
    if not pl.exists():
        return
    text = pl.read_text(encoding="utf-8")
    # lockfileVersion 3 repeats name/version at the top level AND inside
    # packages[""] (the self-referencing root package entry) — both must be
    # patched or the lockfile is left internally inconsistent after a bump.
    text2, n = re.subn(
        r'("name":\s*"mediaos-ui",\s*"version":\s*)"[^"]+"',
        rf'\1"{version}"',
        text,
    )
    if n:
        pl.write_text(text2, encoding="utf-8")


def git_available() -> bool:
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT,
                       capture_output=True, check=True)
        return True
    except Exception:
        return False


def git_log_since() -> list[str]:
    """Commits since latest tag, or last 50 if no tags."""
    if not git_available():
        return []
    try:
        tags = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if tags.returncode == 0 and tags.stdout.strip():
            rng = f"{tags.stdout.strip()}..HEAD"
        else:
            rng = "HEAD"
        r = subprocess.run(
            ["git", "log", rng, "--pretty=format:%s", "-n", "50"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
        # skip merge noise
        return [ln for ln in lines if not ln.lower().startswith("merge ")]
    except Exception:
        return []


def load_fragments() -> list[tuple[str, str]]:
    """Return list of (name, body) from changelog.d/*.md (not in released/)."""
    if not FRAGMENTS_DIR.is_dir():
        return []
    out = []
    for path in sorted(FRAGMENTS_DIR.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        body = path.read_text(encoding="utf-8").strip()
        if body:
            out.append((path.name, body))
    return out


def archive_fragments(version: str) -> None:
    frags = list(FRAGMENTS_DIR.glob("*.md"))
    frags = [p for p in frags if p.name.upper() != "README.MD"]
    if not frags:
        return
    dest = ARCHIVE_DIR / version.replace("/", "-")
    dest.mkdir(parents=True, exist_ok=True)
    for p in frags:
        target = dest / p.name
        target.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        p.unlink()


def normalize_bullets(notes: list[str]) -> list[str]:
    bullets = []
    for n in notes:
        n = n.strip()
        if not n:
            continue
        if n.startswith("#"):
            # keep markdown sections as-is later
            bullets.append(n)
            continue
        if not n.startswith("-") and not n.startswith("*"):
            n = "- " + n
        bullets.append(n)
    return bullets


def render_entry(
    version: str,
    date: str,
    bullets: list[str],
    fragment_bodies: list[str],
    highlight: str | None = None,
) -> str:
    lines = [
        f"# MediaOS {version}",
        "",
        f"**Date:** {date}",
        "",
    ]
    if highlight:
        lines += ["## Highlights", "", highlight.strip(), ""]
    if fragment_bodies:
        lines.append("## Changes")
        lines.append("")
        for body in fragment_bodies:
            lines.append(body.rstrip())
            lines.append("")
    if bullets:
        if not fragment_bodies:
            lines.append("## Changes")
            lines.append("")
        for b in bullets:
            if b.startswith("#"):
                lines.append("")
                lines.append(b)
                lines.append("")
            else:
                lines.append(b)
        lines.append("")
    if not bullets and not fragment_bodies:
        lines += ["## Changes", "", "- (no notes provided)", ""]
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def prepend_file(path: Path, header: str) -> None:
    prev = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(header + prev, encoding="utf-8")


def replace_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def suggest_next_version(current: str) -> str:
    """2.0.19-dev -> 2.0.20-dev; 2.0.19 -> 2.0.20."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(.*)$", current.strip())
    if not m:
        return current + ".1"
    major, minor, patch, suffix = m.group(1), m.group(2), int(m.group(3)), m.group(4)
    return f"{major}.{minor}.{patch + 1}{suffix}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate MediaOS changelog entries")
    p.add_argument("--version", help="Version string (default: VERSION file)")
    p.add_argument("--bump", action="store_true", help="Patch-bump VERSION before writing")
    p.add_argument("--date", default=dt.date.today().isoformat(), help="Release date ISO")
    p.add_argument("--note", action="append", default=[], help="Bullet note (repeatable)")
    p.add_argument("--highlight", default="", help="Optional highlights paragraph")
    p.add_argument("--from-git", action="store_true", help="Include git commit subjects")
    p.add_argument("--from-fragments", action="store_true", help="Include changelog.d/*.md")
    p.add_argument("--write", action="store_true", help="Write CHANGELOG.md + RELEASE_NOTES.md")
    p.add_argument("--release-notes-only", action="store_true", help="Only overwrite RELEASE_NOTES.md")
    p.add_argument("--archive-fragments", action="store_true", help="Move fragments to changelog.d/released/<ver>/")
    p.add_argument("--dry-run", action="store_true", help="Print only (default if no --write)")
    args = p.parse_args(argv)

    version = args.version or read_version()
    if args.bump:
        version = suggest_next_version(version)

    notes: list[str] = list(args.note)
    if args.from_git:
        notes.extend(git_log_since())

    fragment_bodies: list[str] = []
    if args.from_fragments or (not notes and FRAGMENTS_DIR.is_dir()):
        for _name, body in load_fragments():
            fragment_bodies.append(body)

    notes = normalize_bullets(notes)
    if not notes and not fragment_bodies:
        print("Nothing to release (no --note, git commits, or changelog.d fragments).", file=sys.stderr)
        return 2

    entry = render_entry(
        version=version,
        date=args.date,
        bullets=notes,
        fragment_bodies=fragment_bodies,
        highlight=args.highlight or None,
    )

    print(entry)

    if args.dry_run or (not args.write and not args.release_notes_only):
        print("(dry-run — pass --write to update files)", file=sys.stderr)
        return 0

    if args.bump or args.version:
        write_version(version)
        bump_package_json(version)
        bump_package_lock(version)
        print(f"VERSION -> {version}", file=sys.stderr)

    if args.release_notes_only:
        # Honor "only" literally — don't also touch CHANGELOG.md or the
        # per-version snapshot file, and don't claim to have written them.
        replace_file(RELEASE_NOTES, entry)
        print(f"Wrote {RELEASE_NOTES.name}", file=sys.stderr)
    else:
        prepend_file(CHANGELOG, entry)
        replace_file(RELEASE_NOTES, entry)
        # Dedicated per-version snapshot
        snap = ROOT / f"CHANGELOG_{version.replace('/', '-')}.md"
        replace_file(snap, entry)
        print(f"Wrote {CHANGELOG.name}, {RELEASE_NOTES.name}, {snap.name}", file=sys.stderr)

    if args.archive_fragments or args.from_fragments:
        archive_fragments(version)
        print(f"Archived fragments under changelog.d/released/{version}/", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
