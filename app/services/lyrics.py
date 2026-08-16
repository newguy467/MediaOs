"""Lyrics resolution for music tracks.

Resolution order:
  1. .lrc sidecar  → synced lyrics
  2. .txt sidecar  → plain lyrics
  3. embedded tags (mutagen: SYLT/USLT/LYRICS/UNSYNCEDLYRICS/©lyr)
  4. LRCLIB API    → synced (fallback plain)
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.services.media_player import _assert_under_library

log = logging.getLogger(__name__)

LRCLIB_URL = "https://lrclib.net/api/get"


def _read_sidecar(path: Path, ext: str) -> str | None:
    side = path.with_suffix(ext)
    try:
        if side.is_file():
            return side.read_text(encoding="utf-8", errors="replace")
    except Exception as e:  # pragma: no cover
        log.debug("sidecar read failed %s: %s", side, e)
    return None


def _embedded(path: Path) -> tuple[str | None, str | None]:
    """Return (synced, plain) from embedded tags. mutagen optional."""
    try:
        import mutagen  # type: ignore
    except Exception:
        return None, None
    synced = None
    plain = None
    try:
        audio = mutagen.File(str(path), easy=False)
        if audio is None:
            return None, None
        tags = getattr(audio, "tags", None)
        if not tags:
            return None, None
        # ID3 (mp3)
        for key in list(tags.keys()):
            k = key.upper()
            if k.startswith("SYLT"):
                try:
                    frames = tags.getall("SYLT") if hasattr(tags, "getall") else []
                    for fr in frames:
                        lines = [t for t, _ in getattr(fr, "text", [])]
                        if lines:
                            synced = synced or "\n".join(lines)
                except Exception:
                    pass
            if k.startswith("USLT"):
                try:
                    frames = tags.getall("USLT") if hasattr(tags, "getall") else []
                    for fr in frames:
                        txt = getattr(fr, "text", None)
                        if txt:
                            plain = plain or str(txt)
                except Exception:
                    pass
        # Vorbis/FLAC/MP4 generic
        for key in ("LYRICS", "UNSYNCEDLYRICS", "©lyr", "lyrics"):
            try:
                v = tags.get(key)
                if v:
                    val = v[0] if isinstance(v, (list, tuple)) else v
                    plain = plain or str(val)
            except Exception:
                pass
    except Exception as e:  # pragma: no cover
        log.debug("embedded lyrics failed %s: %s", path, e)
    return synced, plain


def _lrclib(title: str, artist: str, album: str, duration: int | None) -> tuple[str | None, str | None]:
    try:
        import httpx  # type: ignore
    except Exception:
        return None, None
    params = {"track_name": title or "", "artist_name": artist or "", "album_name": album or ""}
    if duration:
        params["duration"] = duration
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.get(LRCLIB_URL, params=params)
            if r.status_code == 404:
                # loose retry without album/duration
                r = client.get(LRCLIB_URL, params={"track_name": title or "", "artist_name": artist or ""})
            if r.status_code != 200:
                return None, None
            d = r.json()
            return d.get("syncedLyrics"), d.get("plainLyrics")
    except Exception as e:  # pragma: no cover
        log.debug("lrclib failed: %s", e)
        return None, None


def find_lyrics(path: str, title: str = "", artist: str = "", album: str = "", duration: int | None = None) -> dict:
    """Resolve lyrics for a track. Returns {synced, plain, source}."""
    result = {"synced": None, "plain": None, "source": None}
    if not path:
        return result
    p = Path(path)
    try:
        _assert_under_library(p)
    except PermissionError:
        return result

    # 1. .lrc sidecar
    lrc = _read_sidecar(p, ".lrc")
    if lrc:
        result.update(synced=lrc, source="sidecar-lrc")
        return result
    # 2. .txt sidecar
    txt = _read_sidecar(p, ".txt")
    if txt:
        result.update(plain=txt, source="sidecar-txt")
        return result
    # 3. embedded
    esynced, eplain = _embedded(p)
    if esynced or eplain:
        result.update(synced=esynced, plain=eplain, source="embedded")
        return result
    # 4. LRCLIB
    lsynced, lplain = _lrclib(title, artist, album, duration)
    if lsynced or lplain:
        result.update(synced=lsynced, plain=lplain, source="lrclib")
    return result
