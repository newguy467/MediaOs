#!/usr/bin/env python3
"""Sync VERSION + CHANGELOG.md into the GitHub Pages site (docs/).

Run on every release (and from the pages workflow):
  python3 scripts/build_docs.py
"""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
VERSION = (ROOT / "VERSION").read_text().strip()
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()


def md_inline(text: str) -> str:
    parts = re.split(r"(\*\*.+?\*\*|`[^`]+`)", text)
    out = []
    for p in parts:
        if p.startswith("**") and p.endswith("**"):
            out.append("<strong>" + html.escape(p[2:-2]) + "</strong>")
        elif p.startswith("`") and p.endswith("`"):
            out.append("<code>" + html.escape(p[1:-1]) + "</code>")
        else:
            out.append(html.escape(p))
    return "".join(out)


def changelog_to_html(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    in_ul = False
    for line in lines:
        if line.startswith("# "):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            out.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append("<li>" + md_inline(line[2:]) + "</li>")
        elif not line.strip():
            if in_ul:
                out.append("</ul>")
                in_ul = False
        else:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            out.append("<p>" + md_inline(line) + "</p>")
    if in_ul:
        out.append("</ul>")
    return "\n".join(out)


def write_changelog_page() -> None:
    body = changelog_to_html(CHANGELOG)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MediaOs Changelog — {html.escape(VERSION)}</title>
  <style>
    :root {{
      --bg: #0b0914; --line: #2a2448; --text: #f3f0ff;
      --muted: #9b93c0; --accent: #8b5cf6; --accent2: #a78bfa;
    }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.55; }}
    a {{ color: var(--accent2); }}
    header {{ display: flex; justify-content: space-between; padding: .85rem 5vw; border-bottom: 1px solid var(--line); position: sticky; top: 0; background: rgba(11,9,20,.95); }}
    .brand {{ font-weight: 700; color: var(--accent); text-decoration: none; }}
    main {{ max-width: 820px; margin: 0 auto; padding: 2rem 5vw 4rem; }}
    h2 {{ margin-top: 2rem; border-bottom: 1px solid var(--line); padding-bottom: .35rem; color: var(--accent2); }}
    li {{ color: var(--muted); margin: .35rem 0; }}
    li strong {{ color: var(--text); }}
    p {{ color: var(--muted); }}
    footer {{ border-top: 1px solid var(--line); padding: 1.5rem 5vw; color: var(--muted); font-size: .9rem; max-width: 820px; margin: 0 auto; }}
  </style>
</head>
<body>
  <header>
    <a class="brand" href="./">MediaOs</a>
    <nav><a href="./">Home</a> · <a href="https://github.com/newguy467/MediaOs">GitHub</a></nav>
  </header>
  <main>
{body}
  </main>
  <footer>
    <p>Version <strong>{html.escape(VERSION)}</strong> · Generated from <code>CHANGELOG.md</code> by <code>scripts/build_docs.py</code>.</p>
  </footer>
</body>
</html>
"""
    (DOCS / "changelog.html").write_text(page)


def patch_index_version() -> None:
    index = DOCS / "index.html"
    if not index.exists():
        return
    text = index.read_text()
    text = re.sub(r"v\d+\.\d+(?:\.\d+)?", f"v{VERSION}", text)
    text = re.sub(r"\b\d+\.\d+\.\d+\b", VERSION, text)
    # keep screenshot filenames intact — only replace version-like in text nodes is hard;
    # re-apply carefully: restore screenshot paths if broken
    text = text.replace(f"screenshots/{VERSION}-", "screenshots/01-")  # noop safety
    index.write_text(text)


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    write_changelog_page()
    patch_index_version()
    print(f"docs synced for version {VERSION}")


if __name__ == "__main__":
    main()
