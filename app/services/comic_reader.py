"""In-app comic/manga page reader.

Covers every extension organize.py already recognizes as a comic
(COMIC_EXTENSIONS in app/services/organize.py):
  - .cbz / .zip  → stdlib zipfile
  - .cbt         → stdlib tarfile
  - .cbr / .rar  → shells out to the `unrar` CLI (same tool
                   app/services/unpack.py already uses for torrent
                   extraction — no new Python archive dependency)
  - .cb7         → shells out to `7z` (ditto, mirrors unpack.py)
  - .pdf         → PyMuPDF (fitz), rendered to PNG per page

Nothing is extracted to a temp directory: every page is read straight
out of the archive (or rasterized on the fly for PDF) into memory and
handed back as raw bytes, so opening a 300-page volume doesn't leave
300 loose files on disk.
"""
from __future__ import annotations

import re
import subprocess
import tarfile
import zipfile
from pathlib import Path

from app.services.media_player import _assert_under_library

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
MIME_BY_EXT = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
}
_CMD_TIMEOUT = 30


class ComicReadError(Exception):
    """Safe-to-surface error for a page-list/page-read failure."""


def _safe_path(path: str) -> Path:
    p = Path(path)
    try:
        _assert_under_library(p)
    except PermissionError as e:
        raise ComicReadError(str(e)) from e
    if not p.is_file():
        raise ComicReadError(f"File not found: {path}")
    return p


def _natural_key(name: str):
    """Sort page1/page2/page10 in numeric order, not lexicographic."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def _mime_for(name: str) -> str:
    return MIME_BY_EXT.get(Path(name).suffix.lower(), "application/octet-stream")


def _zip_pages(p: Path) -> list[str]:
    with zipfile.ZipFile(p) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/") and Path(n).suffix.lower() in IMAGE_EXTS]
    return sorted(names, key=_natural_key)


def _tar_pages(p: Path) -> list[str]:
    with tarfile.open(p) as tf:
        names = [m.name for m in tf.getmembers() if m.isfile() and Path(m.name).suffix.lower() in IMAGE_EXTS]
    return sorted(names, key=_natural_key)


def _rar_pages(p: Path) -> list[str]:
    # `unrar lb` = bare listing, one filename per line, no headers.
    try:
        out = subprocess.run(["unrar", "lb", str(p)], capture_output=True, text=True, timeout=_CMD_TIMEOUT)
    except FileNotFoundError as e:
        raise ComicReadError("unrar is not installed on this server") from e
    if out.returncode != 0:
        raise ComicReadError(f"unrar listing failed: {out.stderr.strip()[:200]}")
    names = [ln.strip() for ln in out.stdout.splitlines() if Path(ln.strip()).suffix.lower() in IMAGE_EXTS]
    return sorted(names, key=_natural_key)


def _sevenzip_pages(p: Path) -> list[str]:
    # `7z l -ba` = bare listing (no header/summary rows); filename is the
    # last whitespace-separated field on each line.
    try:
        out = subprocess.run(["7z", "l", "-ba", str(p)], capture_output=True, text=True, timeout=_CMD_TIMEOUT)
    except FileNotFoundError as e:
        raise ComicReadError("7z is not installed on this server") from e
    if out.returncode != 0:
        raise ComicReadError(f"7z listing failed: {out.stderr.strip()[:200]}")
    names = []
    for line in out.stdout.splitlines():
        line = line.rstrip()
        if not line:
            continue
        parts = line.split(None, 5)
        name = parts[-1] if len(parts) == 6 else line
        if Path(name).suffix.lower() in IMAGE_EXTS:
            names.append(name)
    return sorted(names, key=_natural_key)


def _pdf_page_count(p: Path) -> int:
    import fitz  # PyMuPDF
    with fitz.open(str(p)) as doc:
        return doc.page_count


def list_pages(path: str) -> dict:
    """Returns {kind, count, pages}. `pages` is the ordered list of
    in-archive filenames for archive formats, or None for PDF (pages
    there are addressed by index alone, there's nothing to list)."""
    p = _safe_path(path)
    suffix = p.suffix.lower()
    if suffix in (".cbz", ".zip"):
        pages = _zip_pages(p)
        return {"kind": "zip", "count": len(pages), "pages": pages}
    if suffix == ".cbt":
        pages = _tar_pages(p)
        return {"kind": "tar", "count": len(pages), "pages": pages}
    if suffix in (".cbr", ".rar"):
        pages = _rar_pages(p)
        return {"kind": "rar", "count": len(pages), "pages": pages}
    if suffix == ".cb7":
        pages = _sevenzip_pages(p)
        return {"kind": "7z", "count": len(pages), "pages": pages}
    if suffix == ".pdf":
        return {"kind": "pdf", "count": _pdf_page_count(p), "pages": None}
    raise ComicReadError(f"Unsupported comic format: {suffix or path}")


def read_page(path: str, index: int) -> tuple[bytes, str]:
    """Returns (image_bytes, mime_type) for the page at `index` (0-based,
    in the order list_pages() returned for archive formats)."""
    p = _safe_path(path)
    suffix = p.suffix.lower()

    if suffix in (".cbz", ".zip"):
        pages = _zip_pages(p)
        if not 0 <= index < len(pages):
            raise ComicReadError("Page index out of range")
        name = pages[index]
        with zipfile.ZipFile(p) as zf:
            return zf.read(name), _mime_for(name)

    if suffix == ".cbt":
        pages = _tar_pages(p)
        if not 0 <= index < len(pages):
            raise ComicReadError("Page index out of range")
        name = pages[index]
        with tarfile.open(p) as tf:
            member = tf.getmember(name)
            f = tf.extractfile(member)
            if f is None:
                raise ComicReadError("Could not read page from archive")
            return f.read(), _mime_for(name)

    if suffix in (".cbr", ".rar"):
        pages = _rar_pages(p)
        if not 0 <= index < len(pages):
            raise ComicReadError("Page index out of range")
        name = pages[index]
        # `unrar p -inul` prints the file's raw bytes to stdout — no
        # extraction to disk.
        try:
            out = subprocess.run(["unrar", "p", "-inul", str(p), name], capture_output=True, timeout=_CMD_TIMEOUT)
        except FileNotFoundError as e:
            raise ComicReadError("unrar is not installed on this server") from e
        if out.returncode != 0:
            raise ComicReadError(f"unrar extract failed: {out.stderr.decode(errors='replace')[:200]}")
        return out.stdout, _mime_for(name)

    if suffix == ".cb7":
        pages = _sevenzip_pages(p)
        if not 0 <= index < len(pages):
            raise ComicReadError("Page index out of range")
        name = pages[index]
        try:
            out = subprocess.run(["7z", "x", "-so", str(p), name], capture_output=True, timeout=_CMD_TIMEOUT)
        except FileNotFoundError as e:
            raise ComicReadError("7z is not installed on this server") from e
        if out.returncode != 0:
            raise ComicReadError(f"7z extract failed: {out.stderr.decode(errors='replace')[:200]}")
        return out.stdout, _mime_for(name)

    if suffix == ".pdf":
        import fitz  # PyMuPDF
        with fitz.open(str(p)) as doc:
            if not 0 <= index < doc.page_count:
                raise ComicReadError("Page index out of range")
            page = doc.load_page(index)
            pix = page.get_pixmap(dpi=150)
            return pix.tobytes("png"), "image/png"

    raise ComicReadError(f"Unsupported comic format: {suffix or path}")
