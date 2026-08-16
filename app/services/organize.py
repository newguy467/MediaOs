import logging
import os
import re
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.clients.qbittorrent import qbittorrent_client
from app.config import settings
from app.models import Download, Episode, ItemStatus, MediaItem, MediaType
from app.services.activity import log_activity
from app.services.unpack import unpack_path
from app.services.crossseed import notify_cross_seed
from app.services.library_gaps import apply_path_map
from app.services import naming as trash_naming

def _series_dir(series) -> Path:
    tvdb_id = tmdb_id = None
    src = (series.external_source or "").lower()
    try:
        if src == "tvdb" and series.external_id:
            tvdb_id = int(series.external_id)
        elif src == "tmdb" and series.external_id:
            tmdb_id = int(series.external_id)
    except (TypeError, ValueError):
        pass
    folder = trash_naming.series_folder(series.title, series.year, tvdb_id=tvdb_id, tmdb_id=tmdb_id)
    return Path(settings.tv_library_path) / folder


def _episode_dest(series, season: int, episode: int, ep_title: str | None, release_title: str | None, suffix: str) -> Path:
    qtoken = trash_naming.quality_token_from_release(release_title)
    stem = trash_naming.episode_file(series.title, season, episode, ep_title, quality=qtoken)
    return _series_dir(series) / trash_naming.season_folder(season) / f"{stem}{suffix}"


log = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".mov", ".m2ts", ".ts"}
BOOK_EXTENSIONS = {".epub", ".mobi", ".azw", ".azw3", ".pdf", ".cbz", ".cbr"}
COMIC_EXTENSIONS = {".cbz", ".cbr", ".cbt", ".cb7", ".pdf", ".zip", ".rar"}
AUDIOBOOK_EXTENSIONS = {
    ".mp3", ".m4b", ".m4a", ".flac", ".aac", ".ogg", ".opus", ".wav",
} | VIDEO_EXTENSIONS

# S01E02, s1e2, 1x02, Season 1 Episode 2, S01.E02, S01_E02
_SE_PATTERNS = [
    re.compile(r"[Ss](\d{1,2})[ ._\-]?[Ee][Pp]?(\d{1,3})"),
    re.compile(r"(?<!\d)(\d{1,2})[xX](\d{1,3})(?!\d)"),
    re.compile(r"[Ss]eason[ ._\-]?(\d{1,2})[ ._\-]*[Ee](?:p(?:isode)?)?[ ._\-]?(\d{1,3})", re.I),
]
_SEASON_ONLY = re.compile(r"[Ss](?:eason)?[ ._\-]?(\d{1,2})\b", re.I)
_EP_ONLY = re.compile(r"(?:^|[ ._\-])[Ee](?:p(?:isode)?)?[ ._\-]?(\d{1,3})(?:\D|$)", re.I)
_MULTI_SEASON = re.compile(
    r"(?:[Ss]easons?[ ._\-]?)(\d{1,2})\s*[-–to]+\s*(\d{1,2})|"
    r"[Ss](\d{1,2})\s*[-–]+\s*[Ss]?(\d{1,2})|"
    r"\bcomplete\s+series\b|\ball\s+seasons\b",
    re.I,
)


def _sanitize(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "Unknown"


def _folder_name(title: str, year: int | None) -> str:
    if year:
        return _sanitize(f"{title} ({year})")
    return _sanitize(title)


def _find_video_file(root: Path) -> Path | None:
    if not root.exists():
        return None
    if root.is_file() and root.suffix.lower() in VIDEO_EXTENSIONS:
        return root
    if root.is_dir():
        candidates = [
            p
            for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
        ]
        real = [
            p
            for p in candidates
            if "sample" not in p.name.lower() and "trailer" not in p.name.lower()
        ]
        pool = real or candidates
        if pool:
            return max(pool, key=lambda p: p.stat().st_size)
    return None


def _all_video_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file() and root.suffix.lower() in VIDEO_EXTENSIONS:
        return [root]
    if root.is_dir():
        return sorted(
            [
                p
                for p in root.rglob("*")
                if p.is_file()
                and p.suffix.lower() in VIDEO_EXTENSIONS
                and "sample" not in p.name.lower()
                and "trailer" not in p.name.lower()
            ],
            key=lambda p: p.name.lower(),
        )
    return []


def _files_with_ext(root: Path, extensions: set[str]) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file() and root.suffix.lower() in extensions:
        return [root]
    if root.is_dir():
        return sorted(
            [
                p
                for p in root.rglob("*")
                if p.is_file() and p.suffix.lower() in extensions
            ],
            key=lambda p: p.name.lower(),
        )
    return []


def _parse_se(name: str) -> tuple[int, int] | None:
    for pat in _SE_PATTERNS:
        m = pat.search(name)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def _parse_se_with_hint(name: str, season_hint: int | None = None) -> tuple[int, int] | None:
    se = _parse_se(name)
    if se:
        return se
    if season_hint is not None:
        # 101 / E01 / Ep01 with known season
        m = re.search(r"(?<!\d)" + str(season_hint) + r"(\d{2})(?!\d)", name)
        if m:
            return season_hint, int(m.group(1))
        m = re.search(r"(?:^|[ ._\-])[Ee](?:p)?[ ._\-]?(\d{1,3})(?:\D|$)", name, re.I)
        if m:
            return season_hint, int(m.group(1))
    return None


def _parse_season_only(name: str) -> int | None:
    m = _SEASON_ONLY.search(name)
    if m:
        return int(m.group(1))
    return None


def _is_season_pack_title(title: str) -> bool:
    t = (title or "").lower()
    if re.search(r"\bseason[\s._-]?\d{1,2}\b", t) or re.search(r"\bcomplete\b", t):
        return True
    if re.search(r"[Ss]\d{1,2}\b", t) and not re.search(r"[Ee]\d{1,3}", t):
        return True
    if _MULTI_SEASON.search(t):
        return True
    return False


def _is_multi_season_title(title: str) -> bool:
    return bool(_MULTI_SEASON.search(title or ""))


def _natural_file_key(path: Path):
    nums = re.findall(r"\d+", path.name)
    return tuple(int(n) for n in nums) if nums else (path.name.lower(),)


def _assign_unlabeled_episodes(
    unlabeled: list[Path],
    series: MediaItem,
    seasons_hint: set[int],
) -> list[tuple[Path, int, int]]:
    """
    Assign unlabeled pack files to wanted episodes in order.
    Prefer seasons in seasons_hint; fall back to all monitored missing eps.
    """
    wanted = [
        e
        for e in sorted(
            series.episodes or [],
            key=lambda x: (x.season_number, x.episode_number),
        )
        if e.monitored
        and e.status != ItemStatus.downloaded
        and (not seasons_hint or e.season_number in seasons_hint)
    ]
    if not wanted and seasons_hint:
        wanted = [
            e
            for e in sorted(series.episodes or [], key=lambda x: (x.season_number, x.episode_number))
            if e.monitored and e.season_number in seasons_hint
        ]
    assigned: list[tuple[Path, int, int]] = []
    unlabeled_sorted = sorted(unlabeled, key=_natural_file_key)
    for vf, ep in zip(unlabeled_sorted, wanted):
        assigned.append((vf, ep.season_number, ep.episode_number))
    return assigned


def _resolve_torrent(download: Download, category: str | None = None) -> dict | None:
    """Find the qB torrent for a Download row.

    Tries the preferred category first, then all torrents (hash / name match).
    Categories differ by media type (mediaos, mediaos-tv, mediaos-adult, …).
    """
    def _collect(cat: str | None) -> list[dict]:
        try:
            return qbittorrent_client.list_torrents(category=cat)
        except Exception as exc:
            log.warning("list_torrents(%s) failed: %s", cat, exc)
            return []

    torrents = _collect(category)
    # Also search uncategorized / all when hash known or category miss
    seen = {(t.get("hash") or "") for t in torrents}
    for extra in (None,) if category else ():
        for t in _collect(extra):
            h = t.get("hash") or ""
            if h and h not in seen:
                torrents.append(t)
                seen.add(h)

    by_hash = {(t.get("hash") or "").lower(): t for t in torrents if t.get("hash")}
    want = (download.torrent_hash or "").strip().lower()
    if want and want in by_hash:
        return by_hash[want]
    # Case-preserving hash from client
    if want:
        for h, t in by_hash.items():
            if h == want:
                return t

    title = (download.release_title or "").strip().lower()
    if not title:
        return None
    for t in torrents:
        name = (t.get("name") or "").lower()
        if name == title or title in name or name in title:
            if t.get("hash") and not download.torrent_hash:
                download.torrent_hash = t["hash"]
            return t
    return None


def _same_filesystem(a: Path, b: Path) -> bool:
    """Return True if both paths are on the same device (hardlink possible)."""
    try:
        a_dev = a.stat().st_dev
        target = b if b.exists() else b.parent
        return a_dev == target.stat().st_dev
    except OSError:
        return False



def _map_path(db, path: Path | str, media_type: str | None = None) -> Path:
    """Apply enabled PathMap rules (container → host) when present."""
    raw = str(path or "")
    if not raw:
        return Path(raw)
    try:
        mt = None
        if media_type is not None:
            mt = media_type.value if hasattr(media_type, "value") else str(media_type)
        mapped = apply_path_map(db, raw, mt)
        return Path(mapped)
    except Exception:
        return Path(raw)

def _place_file(src: Path, dest_path: Path, *, replace: bool = True) -> str:
    """Place *src* at *dest_path*.

    Returns ``"hardlink"`` or ``"move"`` so callers can preserve seeding.

    When ``settings.library_prefer_hardlink`` is True and both paths share a
    filesystem, create a hardlink (torrent client keeps seeding the original).
    Otherwise fall back to ``shutil.move``.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists():
        if replace:
            try:
                # Only unlink if not the same inode as src (already linked)
                try:
                    if dest_path.stat().st_ino == src.stat().st_ino:
                        log.info("Already hardlinked %s ↔ %s", src, dest_path)
                        return "hardlink"
                except OSError:
                    pass
                dest_path.unlink()
            except OSError as exc:
                log.warning("Could not remove old file %s: %s", dest_path, exc)
                return "skip"
        else:
            log.warning("Destination already exists, skipping: %s", dest_path)
            return "skip"

    prefer_link = bool(getattr(settings, "library_prefer_hardlink", True))
    if prefer_link:
        # Try hardlink even when st_dev check is uncertain (Docker bind mounts).
        same = _same_filesystem(src, dest_path.parent)
        if same or prefer_link:
            try:
                os.link(str(src), str(dest_path))
                log.info("Hardlinked %s → %s", src, dest_path)
                return "hardlink"
            except OSError as exc:
                # EXDEV = cross-device; anything else also falls back
                log.warning("Hardlink failed (%s); falling back to move: %s", src, exc)

    shutil.move(str(src), str(dest_path))
    log.info("Moved %s → %s", src, dest_path)
    return "move"


def _move_video(video_file: Path, dest_path: Path, *, replace: bool = True) -> str:
    """Backward-compatible alias used by movie/TV organize paths. """
    return _place_file(video_file, dest_path, replace=replace)


def _cleanup_torrent(
    download: Download,
    content_path: Path | None,
    *,
    placed: str = "move",
) -> None:
    """Remove download client item after organize.

    Hardlink path: keep seeding by default (do not delete torrent or files).
    Move path: remove torrent and leftover download files.
    """
    keep_seed = bool(getattr(settings, "library_prefer_hardlink", True)) and placed == "hardlink"
    remove_after_link = bool(getattr(settings, "library_remove_download_after_hardlink", False))

    if keep_seed and not remove_after_link:
        log.info(
            "Keeping torrent %s for seeding (hardlinked into library)",
            (download.torrent_hash or "")[:12],
        )
        return

    try:
        if download.torrent_hash:
            # Hardlinked: never deleteFiles — would only drop one name, but
            # removing the torrent stops seeding; if operator asked to remove
            # the client item, keep files on disk.
            delete_files = placed != "hardlink"
            qbittorrent_client.delete_torrent(
                download.torrent_hash,
                delete_files=delete_files,
            )
            if placed == "hardlink":
                return
    except Exception as exc:
        log.warning("qB delete_torrent failed: %s", exc)

    # Only remove download-folder leftovers after a real move
    if placed == "hardlink":
        return
    if content_path and content_path.exists():
        try:
            if content_path.is_dir():
                shutil.rmtree(content_path, ignore_errors=True)
            elif content_path.is_file():
                content_path.unlink(missing_ok=True)
        except Exception as exc:
            log.warning("Could not clean leftover path %s: %s", content_path, exc)




def _library_root_for(item: MediaItem) -> Path:
    if item.media_type == MediaType.adult:
        return Path(getattr(settings, "adult_library_path", None) or settings.movies_library_path)
    if item.media_type == MediaType.movie:
        return Path(settings.movies_library_path)
    return Path(settings.movies_library_path)

def process_completed_movie_downloads(db: Session) -> list[MediaItem]:
    """Organize finished movie torrents. Skips strm-mode rows (already organized)."""
    organized: list[MediaItem] = []
    placed = "move"
    downloads = (
        db.query(Download)
        .filter(Download.status == "grabbed", Download.episode_id.is_(None))
        .all()
    )
    for download in downloads:
        item = download.media_item
        if not item or item.media_type not in (MediaType.movie, MediaType.adult):
            continue
        # strm grabs are marked organized immediately
        if (download.release_title or "").startswith("STRM:") or (
            item.file_path and str(item.file_path).endswith(".strm") and not download.torrent_hash
        ):
            download.status = "organized"
            db.add(download)
            continue

        # Movies → mediaos; adult → mediaos-adult (grab category), then fallbacks
        if item.media_type == MediaType.adult:
            torrent = (
                _resolve_torrent(download, "mediaos-adult")
                or _resolve_torrent(download, "mediaos")
                or _resolve_torrent(download, None)
            )
        else:
            torrent = (
                _resolve_torrent(download, "mediaos")
                or _resolve_torrent(download, None)
            )
        if not torrent or torrent.get("progress", 0) < 1.0:
            continue
        content_path = Path(torrent.get("content_path") or torrent.get("save_path") or "")
        content_path = _map_path(db, content_path, getattr(item, "media_type", None))
        try:
            unpack_path(content_path)
        except Exception:
            pass
        video_file = _find_video_file(content_path)
        if not video_file:
            log.warning(
                "No video file yet for movie download id=%s path=%s",
                download.id,
                content_path,
            )
            continue
        tmdb_id = None
        try:
            if (item.external_source or "").lower() == "tmdb" and item.external_id:
                tmdb_id = int(item.external_id)
        except (TypeError, ValueError):
            tmdb_id = None
        qtoken = trash_naming.quality_token_from_release(download.release_title)
        folder = trash_naming.movie_folder(item.title, item.year, tmdb_id=tmdb_id, quality=qtoken)
        file_stem = trash_naming.movie_file(item.title, item.year, quality=qtoken, tmdb_id=tmdb_id)
        dest_dir = _library_root_for(item) / folder
        dest_path = dest_dir / f"{file_stem}{video_file.suffix.lower()}"
        dest_path = _map_path(db, dest_path, getattr(item, "media_type", None))
        try:
            placed = _move_video(video_file, dest_path)
        except Exception as exc:
            log.error("Move failed for movie %s: %s", item.title, exc)
            continue

        # Optional sidecar .strm pointing at the local file (for some clients)
        if getattr(settings, "movie_write_strm_sidecar", False):
            try:
                sidecar = dest_dir / f"{folder}.strm"
                sidecar.write_text(str(dest_path) + "\n", encoding="utf-8")
            except Exception as exc:
                log.debug("Sidecar strm failed: %s", exc)

        item.status = ItemStatus.downloaded
        item.file_path = str(dest_path)
        if download.quality_score is not None:
            item.quality_score = download.quality_score
        download.status = "organized"
        db.add(item)
        db.add(download)
        organized.append(item)
        log_activity(
            db,
            "organized",
            f"Organized movie: {item.title} → {dest_path}",
            media_type="movie",
            media_item_id=item.id,
            release_title=download.release_title,
        )
        _cleanup_torrent(download, content_path, placed=placed)
        try:
            notify_cross_seed(info_hash=download.torrent_hash, path=str(dest_path))
        except Exception:
            pass
        try:
            from app.services.hooks import after_organize

            after_organize(db, item, dest_path)
        except Exception:
            pass
    db.commit()
    return organized


def process_completed_tv_downloads(db: Session) -> list[Episode]:  # unpack + cross-seed hooked
    """
    Organize finished TV torrents.
    Season packs: move every SxxExx file and mark matching episodes downloaded.
    """
    organized: list[Episode] = []
    placed = "move"
    downloads = (
        db.query(Download)
        .filter(Download.status == "grabbed", Download.episode_id.isnot(None))
        .all()
    )

    for download in downloads:
        torrent = _resolve_torrent(download, "mediaos-tv") or _resolve_torrent(download, None)
        if not torrent or torrent.get("progress", 0) < 1.0:
            continue

        content_path = Path(torrent.get("content_path") or "")
        content_path = _map_path(db, content_path, "tv")
        try:
            unpack_path(content_path)
        except Exception:
            pass
        episode = download.episode
        series = download.media_item
        if not episode or not series:
            continue

        videos = _all_video_files(content_path)
        if not videos:
            log.warning("No videos for TV download id=%s", download.id)
            continue

        season_hint = episode.season_number
        release_title = download.release_title or ""
        multi_season = _is_multi_season_title(release_title)

        # Map files to episode numbers when possible
        file_map: list[tuple[Path, int | None, int | None]] = []
        unlabeled: list[Path] = []
        for vf in videos:
            se = (_parse_se_with_hint(vf.name, season_hint) or _parse_se_with_hint(str(vf.parent), season_hint)
                  or _parse_se(vf.name) or _parse_se(str(vf.parent)) or _parse_se(str(vf)))
            if se:
                file_map.append((vf, se[0], se[1]))
            else:
                s_only = _parse_season_only(vf.name) or _parse_season_only(str(vf.parent))
                if s_only is not None:
                    unlabeled.append(vf)
                    file_map.append((vf, s_only, None))
                else:
                    unlabeled.append(vf)
                    file_map.append((vf, None, None))

        multi = len(videos) > 1 or _is_season_pack_title(release_title)
        moved_any = False
        placed_mode = "move"

        if multi:
            by_key = {
                (e.season_number, e.episode_number): e for e in (series.episodes or [])
            }
            seasons_from_labels = {s for _, s, e in file_map if s is not None}
            if not seasons_from_labels:
                seasons_from_labels = {season_hint}

            # Assign fully unlabeled (or season-only) files to wanted episodes
            pure_unlabeled = [vf for vf, s, e in file_map if e is None]
            if pure_unlabeled:
                seasons_for_assign = seasons_from_labels if not multi_season else set()
                # multi-season pack without labels → any missing monitored
                assigned = _assign_unlabeled_episodes(
                    pure_unlabeled, series, seasons_for_assign
                )
                assign_map = {vf: (s, e) for vf, s, e in assigned}
                new_map: list[tuple[Path, int | None, int | None]] = []
                for vf, s, e in file_map:
                    if e is None and vf in assign_map:
                        new_map.append((vf, assign_map[vf][0], assign_map[vf][1]))
                    else:
                        new_map.append((vf, s, e))
                file_map = new_map

            for vf, s, e in file_map:
                if s is None or e is None:
                    # still unparsed — drop into season-hint folder with original name
                    s = s or season_hint
                    dest_dir = (
                        _series_dir(series) / trash_naming.season_folder(s)
                    )
                    dest_path = dest_dir / vf.name
                    dest_path = _map_path(db, dest_path, "tv")
                    try:
                        pl = _move_video(vf, dest_path)
                        if pl == "hardlink":
                            placed_mode = "hardlink"
                        moved_any = True
                        log.info(
                            "Unlabeled pack file kept as-is: %s → %s",
                            vf.name,
                            dest_path,
                        )
                    except Exception as exc:
                        log.error("Pack file move failed: %s", exc)
                    continue

                ep_row = by_key.get((s, e))
                dest_dir = (
                    _series_dir(series) / trash_naming.season_folder(s)
                )
                stem = trash_naming.episode_file(series.title, s, e, (ep_row.title if ep_row else None), quality=trash_naming.quality_token_from_release(release_title))
                dest_path = dest_dir / f"{stem}{vf.suffix.lower()}"
                dest_path = _map_path(db, dest_path, "tv")
                try:
                    pl = _move_video(vf, dest_path)
                    if pl == "hardlink":
                        placed_mode = "hardlink"
                    moved_any = True
                except Exception as exc:
                    log.error("Pack ep move failed: %s", exc)
                    continue
                if ep_row:
                    ep_row.status = ItemStatus.downloaded
                    ep_row.file_path = str(dest_path)
                    if download.quality_score is not None:
                        ep_row.quality_score = download.quality_score
                    db.add(ep_row)
                    organized.append(ep_row)

            seasons_touched = {s for _, s, e in file_map if s is not None}
            if not seasons_touched:
                seasons_touched = {season_hint}

            # Complete-season packs: mark remaining monitored eps in touched seasons
            # only when title claims complete AND we matched most files
            matched_count = sum(1 for _, s, e in file_map if s is not None and e is not None)
            if (
                _is_season_pack_title(release_title)
                and len(videos) >= 2
                and matched_count >= max(1, len(videos) // 2)
                and not multi_season
            ):
                for season in seasons_touched:
                    monitored_in_season = [
                        e for e in (series.episodes or [])
                        if e.season_number == season and e.monitored
                    ]
                    matched_in_season = sum(
                        1 for _, s, e in file_map
                        if s == season and e is not None
                    )
                    # only auto-mark remainder when we matched most of the season
                    if monitored_in_season and matched_in_season < max(
                        1, int(len(monitored_in_season) * 0.7)
                    ):
                        continue
                    for ep_row in monitored_in_season:
                        if ep_row.status != ItemStatus.downloaded:
                            # only mark if a real file exists for this ep or sibling
                            has_sibling = any(
                                e.file_path for e in monitored_in_season if e.id != ep_row.id
                            )
                            if not has_sibling and not ep_row.file_path:
                                continue
                            ep_row.status = ItemStatus.downloaded
                            if not ep_row.file_path:
                                ep_row.file_path = str(
                                    _series_dir(series) / trash_naming.season_folder(ep_row.season_number)
                                )
                            db.add(ep_row)
                            if ep_row not in organized:
                                organized.append(ep_row)

            if moved_any:
                download.status = "organized"
                db.add(download)
                log_activity(
                    db,
                    "organized",
                    f"Organized season pack: {series.title} ({release_title})",
                    media_type="tv",
                    media_item_id=series.id,
                    release_title=release_title,
                )
                _cleanup_torrent(download, content_path, placed=placed_mode)
                try:
                    from app.services.hooks import after_organize_series

                    after_organize_series(db, series)
                except Exception:
                    pass
        else:
            # Single episode
            video_file = max(videos, key=lambda p: p.stat().st_size)
            se = _parse_se(video_file.name)
            s = se[0] if se else episode.season_number
            e = se[1] if se else episode.episode_number
            dest_dir = (
                _series_dir(series) / trash_naming.season_folder(s)
            )
            stem = trash_naming.episode_file(series.title, s, e, (episode.title if episode else None), quality=trash_naming.quality_token_from_release(release_title))
            dest_path = dest_dir / f"{stem}{video_file.suffix.lower()}"
            dest_path = _map_path(db, dest_path, "tv")
            try:
                placed = _move_video(video_file, dest_path)
            except Exception as exc:
                log.error("Move failed TV: %s", exc)
                continue
            episode.status = ItemStatus.downloaded
            episode.file_path = str(dest_path)
            if download.quality_score is not None:
                episode.quality_score = download.quality_score
            download.status = "organized"
            db.add(episode)
            db.add(download)
            organized.append(episode)
            log_activity(
                db,
                "organized",
                f"Organized {series.title} S{s:02d}E{e:02d} → {dest_path}",
                media_type="tv",
                media_item_id=series.id,
                release_title=download.release_title,
            )
            _cleanup_torrent(download, content_path, placed=placed)
            try:
                from app.services.hooks import after_organize_episode

                after_organize_episode(db, series, episode, dest_path)
            except Exception:
                pass
            try:
                notify_cross_seed(info_hash=download.torrent_hash, path=str(dest_path))
            except Exception:
                pass

    db.commit()
    
    # Episode-aware tracking sync for unique series
    try:
        from app.services.tracking_aggregate import sync_series_tracking
        series_ids = {getattr(ep, "media_item_id", None) for ep in organized}
        for sid in series_ids:
            if sid:
                sync_series_tracking(db, sid)
    except Exception:
        pass
    return organized


def process_completed_music_downloads(db: Session) -> list[MediaItem]:
    organized: list[MediaItem] = []
    placed = "move"
    downloads = (
        db.query(Download)
        .filter(Download.status == "grabbed", Download.episode_id.is_(None))
        .all()
    )
    for download in downloads:
        item = download.media_item
        if not item or item.media_type != MediaType.music:
            continue
        torrent = _resolve_torrent(download, "mediaos-music")
        if not torrent and download.torrent_hash:
            torrent = _resolve_torrent(download, "mediaos")
        if not torrent or torrent.get("progress", 0) < 1.0:
            continue
        content_path = Path(torrent.get("content_path") or "")
        if not content_path.exists():
            continue
        title = item.title or "Unknown"
        artist = item.artist_name or (
            title.split(" - ", 1)[0] if " - " in title else "Unknown Artist"
        )
        album = title
        dest_dir = Path(settings.music_library_path) / _sanitize(artist) / _sanitize(album)
        dest_dir.mkdir(parents=True, exist_ok=True)
        audio_ext = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wav", ".opus"} | VIDEO_EXTENSIONS
        try:
            if content_path.is_dir():
                for f in content_path.rglob("*"):
                    if f.is_file() and f.suffix.lower() in audio_ext:
                        target = dest_dir / f.name
                        if not target.exists():
                            placed = _place_file(f, target)
            elif content_path.is_file():
                _place_file(content_path, dest_dir / content_path.name)
        except Exception as exc:
            log.error("Music organize failed for %s: %s", title, exc)
            continue
        item.status = ItemStatus.downloaded
        item.file_path = str(dest_dir)
        download.status = "organized"
        db.add(item)
        db.add(download)
        organized.append(item)
        log_activity(
            db,
            "organized",
            f"Organized music: {artist} - {album} → {dest_dir}",
            media_type="music",
            media_item_id=item.id,
            release_title=download.release_title,
        )
        _cleanup_torrent(download, content_path, placed=placed)
    db.commit()
    return organized


def process_completed_book_downloads(db: Session) -> list[MediaItem]:
    """Organize finished book / eBook torrents into BOOKS_LIBRARY_PATH."""
    organized: list[MediaItem] = []
    placed = "move"
    downloads = (
        db.query(Download)
        .filter(Download.status == "grabbed", Download.episode_id.is_(None))
        .all()
    )
    for download in downloads:
        item = download.media_item
        if not item or item.media_type != MediaType.book:
            continue
        torrent = _resolve_torrent(download, "mediaos-books") or _resolve_torrent(
            download, "mediaos"
        )
        if not torrent or torrent.get("progress", 0) < 1.0:
            continue
        content_path = Path(torrent.get("content_path") or "")
        files = _files_with_ext(content_path, BOOK_EXTENSIONS)
        if not files:
            # fallback: any non-sample file
            if content_path.is_file():
                files = [content_path]
            elif content_path.is_dir():
                files = [
                    p
                    for p in content_path.rglob("*")
                    if p.is_file() and "sample" not in p.name.lower()
                ]
                files = sorted(files, key=lambda p: p.stat().st_size, reverse=True)[:5]
        if not files:
            log.warning("No book files for download id=%s", download.id)
            continue

        author = (item.overview or "Unknown").split(",")[0].strip() or "Unknown"
        dest_dir = (
            Path(settings.books_library_path)
            / _sanitize(author)
            / _folder_name(item.title, item.year)
        )
        dest_dir.mkdir(parents=True, exist_ok=True)
        primary: Path | None = None
        try:
            for f in files:
                target = dest_dir / f.name
                if not target.exists():
                    placed = _place_file(f, target)
                if primary is None or f.suffix.lower() in {".epub", ".mobi", ".pdf"}:
                    primary = target if target.exists() else dest_dir / f.name
        except Exception as exc:
            log.error("Book organize failed for %s: %s", item.title, exc)
            continue

        item.status = ItemStatus.downloaded
        item.file_path = str(primary or dest_dir)
        download.status = "organized"
        db.add(item)
        db.add(download)
        organized.append(item)
        log_activity(
            db,
            "organized",
            f"Organized book: {item.title} → {dest_dir}",
            media_type="book",
            media_item_id=item.id,
            release_title=download.release_title,
        )
        _cleanup_torrent(download, content_path, placed=placed)
        try:
            from app.services.hooks import after_organize

            after_organize(db, item, Path(item.file_path))
        except Exception:
            pass
    db.commit()
    return organized


def process_completed_audiobook_downloads(db: Session) -> list[MediaItem]:
    """Organize finished audiobook torrents into AUDIOBOOKS_LIBRARY_PATH."""
    organized: list[MediaItem] = []
    placed = "move"
    downloads = (
        db.query(Download)
        .filter(Download.status == "grabbed", Download.episode_id.is_(None))
        .all()
    )
    for download in downloads:
        item = download.media_item
        if not item or item.media_type != MediaType.audiobook:
            continue
        torrent = _resolve_torrent(download, "mediaos-audiobooks") or _resolve_torrent(
            download, "mediaos"
        )
        if not torrent or torrent.get("progress", 0) < 1.0:
            continue
        content_path = Path(torrent.get("content_path") or "")
        files = _files_with_ext(content_path, AUDIOBOOK_EXTENSIONS)
        if not files:
            log.warning("No audiobook files for download id=%s", download.id)
            continue

        author = (item.overview or "Unknown").split(",")[0].strip() or "Unknown"
        dest_dir = (
            Path(settings.audiobooks_library_path)
            / _sanitize(author)
            / _folder_name(item.title, item.year)
        )
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            if content_path.is_dir() and len(files) > 1:
                # keep chapter structure under author/title/
                for f in files:
                    rel = f.relative_to(content_path) if content_path in f.parents else Path(f.name)
                    target = dest_dir / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists():
                        placed = _place_file(f, target)
            else:
                for f in files:
                    target = dest_dir / f.name
                    if not target.exists():
                        placed = _place_file(f, target)
        except Exception as exc:
            log.error("Audiobook organize failed for %s: %s", item.title, exc)
            continue

        item.status = ItemStatus.downloaded
        item.file_path = str(dest_dir)
        download.status = "organized"
        db.add(item)
        db.add(download)
        organized.append(item)
        log_activity(
            db,
            "organized",
            f"Organized audiobook: {item.title} → {dest_dir}",
            media_type="audiobook",
            media_item_id=item.id,
            release_title=download.release_title,
        )
        _cleanup_torrent(download, content_path, placed=placed)
    db.commit()
    return organized


def _extract_comic_issue_number(stem: str) -> str | None:
    """Extract an issue/chapter number from a release filename stem.

    Handles common scene / retailer / scanlation patterns and avoids treating
    years (19xx/20xx) as issue numbers.
    """
    import re as _re
    patterns = (
        r"(?:issue|iss(?:ue)?|ch(?:apter)?|#)[\s._#-]*(\d{1,4}(?:\.\d+)?)",
        r"(?:^|[\s._-])v(?:ol(?:ume)?)?\.?\s*\d+[\s._-]+(\d{1,4}(?:\.\d+)?)",
        r"(?:^|[\s#._-])(\d{1,4}(?:\.\d+)?)(?:$|[\s._-]|(?:\s*\())",
        r"(\d{1,3})\s*(?:of|/)\s*\d{1,3}",
        r"[\(\[{](\d{1,4}(?:\.\d+)?)[\)\]}]",
        r"[\s._-]0*(\d{2,4})(?:[\s._-]|$)",
        r"(?:^|\b)c(\d{1,4})(?:\b|$)",
        r"(?:^|\b)n(\d{1,4})(?:\b|$)",
        r"(\d{1,4})p(?:\d+)?b",
        # One Piece style: Chapter 1095 / Ch.1095
        r"(?:^|[\s._-])(?:ch(?:apter)?)\.?[\s._-]*(\d{1,4}(?:\.\d+)?)",
    )
    for pat in patterns:
        m = _re.search(pat, stem, _re.I)
        if m:
            raw = m.group(1)
            return raw.lstrip("0") or raw
    # Last resort: longest digit run that looks like issue (1–4 digits), not year
    cands = _re.findall(r"(?<!\d)(\d{1,4})(?!\d)", stem)
    for c in reversed(cands):
        if len(c) == 4 and c.startswith(("19", "20")):
            continue
        return c.lstrip("0") or c
    return None


def _comic_issue_lookup_keys(issue_n: str) -> list[str]:
    """Normalize issue number into several keys for matching ComicIssue rows."""
    keys: list[str] = []
    raw = str(issue_n or "").strip()
    if not raw:
        return keys
    keys.append(raw)
    stripped = raw.lstrip("0") or raw
    if stripped not in keys:
        keys.append(stripped)
    keys.append(stripped.zfill(2))
    keys.append(stripped.zfill(3))
    keys.append(stripped.zfill(4))
    # decimal issues: 12.1 → also try 12
    if "." in stripped:
        whole = stripped.split(".", 1)[0]
        if whole and whole not in keys:
            keys.append(whole)
            keys.append(whole.zfill(2))
            keys.append(whole.zfill(3))
    try:
        if stripped.replace(".", "").isdigit():
            as_int = str(int(float(stripped)))
            if as_int not in keys:
                keys.append(as_int)
    except Exception:
        pass
    # dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _comic_dest_dir(item: MediaItem) -> Path:
    """Publisher / Series (Year) folder layout for comics & manga."""
    publisher = (item.artist_name or "Unknown").split(",")[0].strip() or "Unknown"
    lib = settings.manga_library_path if item.media_type == MediaType.manga else settings.comics_library_path
    # Prefer series_name when it differs from title (volume vs series)
    series = (item.series_name or "").strip() or item.title
    # If title already embeds series, don't double-nest
    series_folder = _folder_name(series, item.year if series == item.title else None)
    # When series_name != title, put volume under series: Publisher/Series/Volume (Year)
    if item.series_name and item.series_name.strip() and item.series_name.strip() != item.title:
        volume_folder = _folder_name(item.title, item.year)
        return Path(lib) / _sanitize(publisher) / _sanitize(item.series_name.strip()) / volume_folder
    return Path(lib) / _sanitize(publisher) / series_folder


def process_completed_comic_downloads(db: Session) -> list[MediaItem]:
    """Organize comic/manga downloads into publisher/series folders.

    When filenames contain issue numbers, match against ComicIssue rows and
    mark those issues downloaded with file_path set.
    """
    placed = "move"
    from app.models import ComicIssue

    organized: list[MediaItem] = []
    downloads = db.query(Download).filter(Download.status == "grabbed", Download.episode_id.is_(None)).all()
    for download in downloads:
        item = download.media_item
        if not item or item.media_type not in (MediaType.comic, MediaType.manga):
            continue
        torrent = (
            _resolve_torrent(download, "mediaos-comics")
            or _resolve_torrent(download, "mediaos-books")
            or _resolve_torrent(download, "mediaos")
        )
        if not torrent or torrent.get("progress", 0) < 1.0:
            continue
        content_path = Path(torrent.get("content_path") or "")
        content_path = _map_path(db, content_path, "tv")
        try:
            unpack_path(content_path)
        except Exception:
            pass
        files = _files_with_ext(content_path, COMIC_EXTENSIONS)
        if not files:
            if content_path.is_file():
                files = [content_path]
            elif content_path.is_dir():
                files = sorted(
                    [
                        p
                        for p in content_path.rglob("*")
                        if p.is_file() and "sample" not in p.name.lower()
                    ],
                    key=lambda p: p.stat().st_size,
                    reverse=True,
                )[:50]
        if not files:
            log.warning("No comic files for download id=%s", download.id)
            continue

        dest_dir = _comic_dest_dir(item)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Index existing issues for this volume (multiple key forms)
        issues = (
            db.query(ComicIssue)
            .filter(ComicIssue.media_item_id == item.id)
            .all()
        )
        by_num: dict[str, ComicIssue] = {}
        for iss in issues:
            for k in _comic_issue_lookup_keys(str(iss.issue_number or "")):
                by_num[k] = iss
            raw = str(iss.issue_number or "").strip()
            if raw:
                by_num[raw] = iss

        primary = None
        matched_issues = 0
        try:
            for idx, f in enumerate(files):
                suffix = f.suffix.lower()
                stem = f.stem
                issue_n = _extract_comic_issue_number(stem)

                series_label = (item.series_name or item.title or "Unknown").strip()
                if issue_n:
                    year_bit = f" ({item.year})" if item.year else ""
                    # Jellyfin-friendly: Series #012 (Year).cbz
                    padded = issue_n
                    try:
                        if issue_n.replace(".", "").isdigit() and "." not in issue_n:
                            padded = f"{int(issue_n):03d}"
                    except Exception:
                        pass
                    safe_name = _sanitize(f"{series_label} #{padded}{year_bit}") + suffix
                else:
                    safe_name = _sanitize(stem) + suffix

                target = dest_dir / safe_name
                if target.exists() and target.resolve() != f.resolve():
                    target = dest_dir / f"{_sanitize(stem)}_{idx}{suffix}"
                if not target.exists():
                    try:
                        placed = _place_file(f, target)
                    except Exception as move_exc:
                        log.warning("Comic move failed %s → %s: %s", f, target, move_exc)
                        target = f  # keep original if move fails
                elif target.resolve() == f.resolve():
                    pass  # already in place
                else:
                    # target exists from prior run — use it
                    pass

                # Link to ComicIssue when possible
                if issue_n:
                    iss = None
                    for _k in _comic_issue_lookup_keys(issue_n):
                        if _k in by_num:
                            iss = by_num[_k]
                            break
                    if iss:
                        iss.file_path = str(target)
                        iss.status = ItemStatus.downloaded
                        db.add(iss)
                        matched_issues += 1

                if primary is None or suffix in {".cbz", ".cbr", ".pdf"}:
                    primary = target
        except Exception as exc:
            log.error("Comic organize failed for %s: %s", item.title, exc)
            continue

        item.status = ItemStatus.downloaded
        item.file_path = str(primary or dest_dir)
        download.status = "organized"
        db.add(item)
        db.add(download)
        organized.append(item)
        log_activity(
            db,
            "organized",
            f"Organized {item.media_type.value}: {item.title} → {dest_dir}"
            + (f" ({matched_issues} issues matched)" if matched_issues else ""),
            media_type=item.media_type.value,
            media_item_id=item.id,
            release_title=download.release_title,
        )
        _cleanup_torrent(download, content_path, placed=placed)
    db.commit()
    return organized

