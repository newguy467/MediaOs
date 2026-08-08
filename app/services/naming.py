"""TRaSH-Guides-inspired naming tokens applied end-to-end in organize."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.config import settings


def sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", name or "")
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name or "Unknown"


def apply_template(template: str, tokens: dict[str, Any]) -> str:
    """Replace {token} and {token:00} style placeholders."""
    out = template or ""

    def repl(m: re.Match) -> str:
        key = m.group(1)
        width = m.group(2)
        val = tokens.get(key)
        if val is None:
            return ""
        if width and isinstance(val, int):
            return f"{val:0{int(width)}d}"
        return str(val)

    out = re.sub(r"\{([a-zA-Z0-9_]+)(?::0*(\d+))?\}", repl, out)
    out = re.sub(r"\{\s*\}", "", out)
    out = re.sub(r"\s{2,}", " ", out).strip(" .")
    return sanitize(out) if out else "Unknown"


def movie_folder(
    title: str,
    year: int | None = None,
    tmdb_id: int | None = None,
    quality: str | None = None,
    *,
    template: str | None = None,
) -> str:
    tmpl = template or getattr(settings, "movie_naming_folder", None) or "{title} ({year})"
    # Support {tmdb-{tmdb_id}} config form
    if tmdb_id and "{tmdb-" in (tmpl or ""):
        base = f"{sanitize(title)} ({year})" if year else sanitize(title)
        return f"{base} {{tmdb-{tmdb_id}}}"
    tokens = {
        "title": sanitize(title),
        "year": year or "",
        "tmdb_id": tmdb_id or "",
        "tmdb": tmdb_id or "",
        "quality": quality or "",
    }
    folder = apply_template(tmpl, tokens)
    if tmdb_id and f"tmdb-{tmdb_id}" not in folder:
        folder = f"{folder} {{tmdb-{tmdb_id}}}"
    if not folder or folder == "Unknown":
        base = f"{sanitize(title)} ({year})" if year else sanitize(title)
        if tmdb_id:
            base += f" {{tmdb-{tmdb_id}}}"
        return base
    return folder


def movie_file(
    title: str,
    year: int | None,
    quality: str | None = None,
    tmdb_id: int | None = None,
    *,
    template: str | None = None,
) -> str:
    tmpl = template or "{title} ({year})"
    if quality:
        tmpl = tmpl.rstrip() + " - {quality}"
    tokens = {
        "title": sanitize(title),
        "year": year or "",
        "quality": quality or "",
        "tmdb_id": tmdb_id or "",
    }
    return apply_template(tmpl, tokens)


def series_folder(
    title: str,
    year: int | None = None,
    tvdb_id: int | None = None,
    tmdb_id: int | None = None,
) -> str:
    base = f"{sanitize(title)} ({year})" if year else sanitize(title)
    if tvdb_id:
        base += f" {{tvdb-{tvdb_id}}}"
    elif tmdb_id:
        base += f" {{tmdb-{tmdb_id}}}"
    return base


def season_folder(season: int) -> str:
    return f"Season {int(season):02d}"


def episode_file(
    series: str,
    season: int,
    episode: int,
    episode_title: str | None = None,
    quality: str | None = None,
    *,
    template: str | None = None,
) -> str:
    tmpl = template or getattr(settings, "episode_naming", None) or (
        "{series} - S{season:00}E{episode:00} - {title}"
    )
    tokens = {
        "series": sanitize(series),
        "season": int(season),
        "episode": int(episode),
        "title": sanitize(episode_title) if episode_title else "",
        "quality": quality or "",
    }
    name = apply_template(tmpl, tokens)
    if quality and quality not in name:
        name = f"{name} [{quality}]"
    return name


def parse_ids_from_path(path: str | Path) -> dict[str, int]:
    """Extract tmdb/tvdb/imdb IDs embedded in folder/file names (Sonarr/Radarr style)."""
    s = str(path)
    ids: dict[str, int] = {}
    patterns = (
        ("tmdb", r"\{tmdb[-_]?(\d+)\}"),
        ("tvdb", r"\{tvdb[-_]?(\d+)\}"),
        ("imdb", r"\{imdb[-_]?tt(\d+)\}"),
        ("imdb", r"\{imdb[-_]?(\d+)\}"),
        ("tmdb", r"tmdb[-_=](\d+)"),
        ("tvdb", r"tvdb[-_=](\d+)"),
    )
    for key, pattern in patterns:
        if key in ids:
            continue
        m = re.search(pattern, s, re.IGNORECASE)
        if m:
            try:
                ids[key] = int(m.group(1))
            except ValueError:
                pass
    return ids


def quality_token_from_release(title: str | None) -> str | None:
    """Best-effort short quality token for file names from a release title."""
    if not title:
        return None
    t = title.lower()
    parts = []
    for res in ("2160p", "1080p", "720p", "480p"):
        if res in t:
            parts.append(res)
            break
    src_map = [
        ("blu-ray", "BluRay"),
        ("bluray", "BluRay"),
        ("web-dl", "WEB-DL"),
        ("webdl", "WEB-DL"),
        ("webrip", "WEBRip"),
        ("hdtv", "HDTV"),
        ("remux", "Remux"),
    ]
    for needle, label in src_map:
        if needle in t:
            parts.append(label)
            break
    for codec in ("x265", "hevc", "x264", "av1", "xvid"):
        if codec in t:
            parts.append(codec)
            break
    return " ".join(parts) if parts else None


# ── Jellyfin-compatible paths for other libraries ──────────────────────────

def music_album_folder(artist: str, album: str, year: int | None = None) -> str:
    """Jellyfin: Artist/Album (Year)/"""
    a = sanitize(artist) or "Unknown Artist"
    al = sanitize(album) or "Unknown Album"
    if year:
        al = f"{al} ({year})"
    return str(Path(a) / al)


def music_track_file(track_num: int | None, title: str, artist: str | None = None) -> str:
    """Jellyfin: 01 - Track Title"""
    t = sanitize(title) or "Track"
    if track_num:
        return f"{int(track_num):02d} - {t}"
    return t


def book_folder(author: str, title: str, year: int | None = None) -> str:
    """Jellyfin books: Author/Title (Year)/"""
    a = sanitize(author) or "Unknown Author"
    t = sanitize(title) or "Unknown"
    if year:
        t = f"{t} ({year})"
    return str(Path(a) / t)


def audiobook_folder(author: str, title: str, year: int | None = None) -> str:
    return book_folder(author, title, year)


def comic_folder(publisher: str | None, series: str, volume: str | None = None) -> str:
    """Comics: Publisher/Series/ or Series/"""
    s = sanitize(series) or "Unknown"
    if publisher:
        base = Path(sanitize(publisher)) / s
    else:
        base = Path(s)
    if volume:
        base = base / sanitize(f"v{volume}")
    return str(base)


def comic_issue_file(series: str, issue_number: str, year: int | None = None) -> str:
    """Series #012 (Year)"""
    s = sanitize(series) or "Issue"
    num = str(issue_number or "").lstrip("0") or "0"
    try:
        num = f"{int(float(num)):03d}" if "." not in num else num
    except ValueError:
        pass
    name = f"{s} #{num}"
    if year:
        name = f"{name} ({year})"
    return name


# Jellyfin recommended templates (documented defaults)
JELLYFIN_MOVIE_FOLDER = "{title} ({year})"
JELLYFIN_EPISODE = "{series} - S{season:00}E{episode:00} - {title}"
JELLYFIN_SERIES_FOLDER = "{title} ({year})"
