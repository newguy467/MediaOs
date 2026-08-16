"""ComicInfo.xml metadata write-back for comics/manga (gap item O).

Two problems fixed here, both flagged in the Comics gap analysis:

  1. No `_assert_under_library` path-safety check before writing to
     disk — every other file-writing service in this repo validates
     the target first (lyrics.py, tag_editor.py, comic_reader.py,
     media_player.py). The old inline version in the router didn't.

  2. ComicInfo.xml was written as a *sidecar* next to the archive.
     Real comic readers/taggers (ComicTagger, Kavita, ComicRack)
     don't look at a sidecar file — they expect ComicInfo.xml
     **inside** the .cbz/.zip as a zip member at the archive root.

For .cbz/.zip: rewritten via the same atomic-temp-copy pattern
app/services/tag_editor.py already uses for audio tags — build a
whole new zip in a temp file (copying every existing member except
any prior ComicInfo.xml, then adding the new one), and only
os.replace() it into place once the rebuild has fully succeeded.
zipfile has no in-place "replace this one member" API, so a
member-preserving rebuild is the correct way to swap one file out of
an existing zip without corrupting or duplicating entries.

.cbr/.rar can't be modified in place the same way — RAR write
support is a licensing/tooling mess (unrar, the CLI this repo
already shells out to for *reading* .cbr in comic_reader.py, is
read-only; RAR's own SDK is proprietary and not worth vendoring for
one feature). Documented here as a known limitation rather than
half-implemented. write_sidecar() below is the fallback for those
(and for any other archive kind with no embed path) so the metadata
isn't lost outright — just not embedded the way a dedicated tagger
would do it.
"""
from __future__ import annotations

import html
import os
import tempfile
import zipfile
from pathlib import Path

from app.services.media_player import _assert_under_library

# Formats embed_comicinfo() can write into directly (zip container).
EMBEDDABLE_EXTENSIONS = (".cbz", ".zip")
# Formats known to have no write-in-place path — see module docstring.
NO_EMBED_EXTENSIONS = (".cbr", ".rar")


class ComicMetaError(Exception):
    """Safe-to-surface error for a metadata-write failure."""


def build_comicinfo_xml(meta: dict) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<ComicInfo>\n"
        f"  <Title>{html.escape(str(meta.get('title') or ''))}</Title>\n"
        f"  <Series>{html.escape(str(meta.get('series') or ''))}</Series>\n"
        f"  <Number>{html.escape(str(meta.get('number') or ''))}</Number>\n"
        f"  <Year>{html.escape(str(meta.get('year') or ''))}</Year>\n"
        f"  <Summary>{html.escape(str(meta.get('summary') or ''))}</Summary>\n"
        f"  <Publisher>{html.escape(str(meta.get('publisher') or ''))}</Publisher>\n"
        "</ComicInfo>\n"
    )


def _safe_target(path: str) -> Path:
    """Validate `path` is under a library root and actually exists.
    Unlike comic_reader.py's _safe_path, this allows a directory too —
    metatag_comic has always accepted either a single archive file or
    a folder-based comic (write_sidecar needs the folder case)."""
    p = Path(path)
    try:
        _assert_under_library(p)
    except PermissionError as e:
        raise ComicMetaError(str(e)) from e
    if not p.exists():
        raise ComicMetaError(f"Path not found: {path}")
    return p


def embed_comicinfo(path: str, meta: dict) -> str:
    """Write ComicInfo.xml as a member inside a .cbz/.zip archive,
    replacing any existing one of the same name. Returns the in-zip
    member name. Raises ComicMetaError if `path` isn't a zip
    container this can embed into, or the rebuild fails for any
    reason (original file is left untouched either way)."""
    p = _safe_target(path)
    if not p.is_file() or p.suffix.lower() not in EMBEDDABLE_EXTENSIONS:
        raise ComicMetaError(f"Cannot embed metadata into {p.suffix or 'this'} files")

    xml = build_comicinfo_xml(meta)
    fd, tmp_name = tempfile.mkstemp(dir=str(p.parent), prefix=".metatag-", suffix=p.suffix)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with zipfile.ZipFile(p, "r") as zin, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename.lower() == "comicinfo.xml":
                    continue  # dropped here — the new one is added below
                zout.writestr(item, zin.read(item.filename))
            zout.writestr("ComicInfo.xml", xml)
        os.replace(tmp_path, p)
    except Exception as e:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:  # pragma: no cover
            pass
        raise ComicMetaError(f"Embed failed: {e}") from e
    return "ComicInfo.xml"


def write_sidecar(path: str, meta: dict) -> str:
    """Fallback for anything embed_comicinfo() can't handle (.cbr/.rar,
    or any other extension) — a ComicInfo.xml written next to the
    file, or inside the folder for a folder-based comic. This is the
    behavior metatag_comic always had; only the path-safety check is
    new. Not visible to readers that expect metadata embedded, but
    keeps it from being lost outright for formats with no write-in-
    place support."""
    p = _safe_target(path)
    xml = build_comicinfo_xml(meta)
    target = p.parent if p.is_file() else p
    out = target / "ComicInfo.xml"
    try:
        out.write_text(xml, encoding="utf-8")
    except OSError as e:
        raise ComicMetaError(f"Sidecar write failed: {e}") from e
    return str(out)
