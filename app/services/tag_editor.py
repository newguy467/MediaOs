"""Metadata write-back for music tracks (batch item H).

Two concerns, kept separate from app/services/lyrics.py on purpose —
that module is read-only (lyrics resolution); this one writes to the
user's files:

  1. Simple text tags (title/artist/album/tracknumber) via mutagen's
     `easy=True` mode, which normalizes ID3/FLAC/MP4 tag names to a
     common key set — one code path works across MP3/FLAC/M4A.
  2. Cover art, which has no unified easy-mode API and needs
     format-specific handling:
       - MP3 (ID3):   APIC frame
       - FLAC:        Picture object
       - MP4/M4A:     MP4Cover

Both write to a temp copy in the same directory and swap it into place
with os.replace() only after a successful save, so a crash or bad tag
value mid-write can't corrupt the original file — mutagen's `.save()`
is not atomic on its own.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from app.services.media_player import _assert_under_library

# mutagen's easy=True key set we support writing. Anything else in a
# payload is silently ignored rather than raising, so callers can pass
# a partial dict (e.g. only `title`) without extra filtering.
EASY_TAG_FIELDS = ("title", "artist", "album", "tracknumber")


class TagWriteError(Exception):
    """Raised for any failure writing tags/artwork — message is safe to
    surface to the API caller (no internal paths beyond what they gave us)."""


def _safe_path(path: str) -> Path:
    p = Path(path)
    try:
        _assert_under_library(p)
    except PermissionError as e:
        raise TagWriteError(str(e)) from e
    if not p.is_file():
        raise TagWriteError(f"File not found: {path}")
    return p


def _atomic_save(p: Path, do_save) -> None:
    """Copy p to a temp file in the same directory, let do_save(tmp_path)
    mutate/save it, then replace the original only on success."""
    fd, tmp_name = tempfile.mkstemp(dir=str(p.parent), prefix=".tagedit-", suffix=p.suffix)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        shutil.copy2(p, tmp_path)
        do_save(tmp_path)
        os.replace(tmp_path, p)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:  # pragma: no cover
            pass
        raise


def write_text_tags(path: str, fields: dict) -> dict:
    """Write title/artist/album/tracknumber into the file's tags.

    `fields` may contain any subset of EASY_TAG_FIELDS (extra keys are
    ignored); an empty-string value clears that tag. Returns the subset
    actually written, so the caller can mirror it into the DB.
    """
    try:
        import mutagen
    except ImportError as e:
        raise TagWriteError("mutagen is not installed") from e

    p = _safe_path(path)
    clean = {k: fields[k] for k in EASY_TAG_FIELDS if fields.get(k) is not None}
    if not clean:
        return {}

    def _save(tmp_path: Path):
        audio = mutagen.File(str(tmp_path), easy=True)
        if audio is None:
            raise TagWriteError("Unsupported or unreadable audio file")
        for key, value in clean.items():
            value = str(value)
            if value == "":
                audio.pop(key, None)
            else:
                audio[key] = value
        audio.save()

    try:
        _atomic_save(p, _save)
    except TagWriteError:
        raise
    except Exception as e:
        raise TagWriteError(f"Tag write failed: {e}") from e
    return clean


def write_artwork(path: str, image_bytes: bytes, mime_type: str) -> None:
    """Embed cover art. No unified easy-mode API for this — dispatch by
    extension to the format-specific mutagen classes."""
    p = _safe_path(path)
    suffix = p.suffix.lower()

    def _save(tmp_path: Path):
        if suffix == ".mp3":
            from mutagen.id3 import ID3, ID3NoHeaderError, APIC
            try:
                tags = ID3(str(tmp_path))
            except ID3NoHeaderError:
                tags = ID3()
            tags.delall("APIC")
            tags.add(APIC(encoding=3, mime=mime_type, type=3, desc="Cover", data=image_bytes))
            tags.save(str(tmp_path))
        elif suffix == ".flac":
            from mutagen.flac import FLAC, Picture
            audio = FLAC(str(tmp_path))
            audio.clear_pictures()
            pic = Picture()
            pic.type = 3
            pic.mime = mime_type
            pic.data = image_bytes
            audio.add_picture(pic)
            audio.save()
        elif suffix in (".m4a", ".mp4", ".alac"):
            from mutagen.mp4 import MP4, MP4Cover
            audio = MP4(str(tmp_path))
            fmt = MP4Cover.FORMAT_PNG if "png" in mime_type else MP4Cover.FORMAT_JPEG
            audio["covr"] = [MP4Cover(image_bytes, imageformat=fmt)]
            audio.save()
        else:
            raise TagWriteError(f"Cover art isn't supported for {suffix or 'this'} files")

    try:
        _atomic_save(p, _save)
    except TagWriteError:
        raise
    except Exception as e:
        raise TagWriteError(f"Artwork write failed: {e}") from e
