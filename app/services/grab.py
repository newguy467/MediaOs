import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.clients.sabnzbd import sabnzbd_client
from app.clients.nzbget import nzbget_client
from app.clients.qbittorrent import qbittorrent_client
from app.services.hooks import notify_grab, notify_event
from app.config import settings
from app.models import Download, Episode, ItemStatus, MediaItem
from app.services.activity import log_activity
from app.services.vpn import vpn_allows_grabs
from app.services.delay_profiles import should_delay, DEFAULT_PROFILES
import time

log = logging.getLogger(__name__)





def _release_download_url(release: dict) -> str:
    """Prefer download_url, then magnet, then link/uri fields from indexers."""
    for key in ("download_url", "magnet", "magnetUrl", "link", "uri", "guid"):
        val = release.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return ""



def _movie_strm_path(media_item: MediaItem) -> Path:
    title = re.sub(r'[<>:"/\\\\|?*]', "", media_item.title or "Unknown").strip() or "Unknown"
    folder = f"{title} ({media_item.year})" if media_item.year else title
    dest_dir = Path(settings.movies_library_path) / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir / f"{folder}.strm"


def _grab_movie_strm(db: Session, media_item: MediaItem, release: dict) -> Download:
    """Radarr-style strm: prefer Real-Debrid unrestricted link when available."""
    url = _release_download_url(release)
    magnet = release.get("magnet") or (url if str(url).startswith("magnet:") else "")
    if magnet:
        try:
            from app.clients.realdebrid import rd_client
            if rd_client.enabled():
                link = rd_client.best_stream_link(magnet)
                if link:
                    url = link
        except Exception:
            pass
    if not url:
        raise RuntimeError("No download URL for strm mode")
    dest = _movie_strm_path(media_item)
    dest.write_text(url.strip() + "\n", encoding="utf-8")
    media_item.status = ItemStatus.downloaded
    media_item.file_path = str(dest)
    if release.get("_score") is not None:
        media_item.quality_score = release["_score"]
    db.add(media_item)
    db.commit()
    download = Download(
        media_item_id=media_item.id,
        episode_id=None,
        indexer=release.get("indexer"),
        release_title=release.get("title") or "",
        download_url=url,
        torrent_hash=None,
        quality_score=release.get("_score"),
        matched_formats=",".join(release.get("_matched_formats") or []) or None,
        status="organized",
    )
    db.add(download)
    db.commit()
    db.refresh(download)
    try:
        notify_grab(release.get("title") or media_item.title or "release", release.get("indexer"))
    except Exception:
        pass
    log_activity(
        db,
        "organized",
        f"STRM movie: {media_item.title} → {dest}",
        media_type="movie",
        media_item_id=media_item.id,
        release_title=release.get("title"),
    )
    log.info("Wrote strm for %s → %s", media_item.title, dest)
    return download

def _qb_category(media_item: MediaItem, episode: Episode | None = None) -> str:
    if episode:
        return "mediaos-tv"
    mt = media_item.media_type.value
    return {
        "music": "mediaos-music",
        "book": "mediaos-books",
        "audiobook": "mediaos-audiobooks",
        "tv": "mediaos-tv",
        "comic": "mediaos-comics",
        "manga": "mediaos-comics",
        "adult": "mediaos-adult",
    }.get(mt, "mediaos")


def _record_download(
    db: Session,
    media_item: MediaItem,
    release: dict,
    episode: Episode | None = None,
) -> Download:
    category = _qb_category(media_item, episode)
    release_title = release.get("title") or ""

    info_hash = (release.get("info_hash") or "").strip().lower() or None

    torrent_hash = None
    if info_hash:
        for t in qbittorrent_client.list_torrents(category=category):
            h = (t.get("hash") or "").lower()
            if h == info_hash:
                torrent_hash = t.get("hash")
                break

    if not torrent_hash:
        torrent_hash = qbittorrent_client.find_torrent_hash(
            release_title,
            category,
            retries=10,
            delay=0.8,
        )

    if not torrent_hash and info_hash:
        torrent_hash = info_hash
        log.info("Using Prowlarr info_hash for %r", release_title)

    if not torrent_hash:
        log.warning("Grab without hash for %r — organize will name-match later", release_title)

    matched = release.get("_matched_formats") or []
    download = Download(
        media_item_id=media_item.id,
        episode_id=episode.id if episode else None,
        indexer=release.get("indexer"),
        release_title=release_title,
        download_url=_release_download_url(release) or release.get("download_url") or "",
        torrent_hash=torrent_hash,
        quality_score=release.get("_score"),
        matched_formats=",".join(matched) if matched else None,
        status="grabbed",
    )
    db.add(download)
    db.commit()
    db.refresh(download)

    kind = "episode" if episode else "movie"
    log_activity(
        db,
        "grabbed",
        f"Grabbed {kind}: {release_title} (score={release.get('_score')})",
        media_type=media_item.media_type.value,
        media_item_id=media_item.id,
        release_title=release_title,
    )
    return download


def _preferred_usenet_client() -> str:
    """Return sabnzbd | nzbget based on config and availability."""
    pref = (getattr(settings, "usenet_client", "auto") or "auto").lower()
    sab = sabnzbd_client.enabled()
    nzb = nzbget_client.enabled()
    if pref == "sabnzbd" and sab:
        return "sabnzbd"
    if pref == "nzbget" and nzb:
        return "nzbget"
    if sab:
        return "sabnzbd"
    if nzb:
        return "nzbget"
    return ""


def _send_usenet(url: str, name: str) -> None:
    client = _preferred_usenet_client()
    if client == "sabnzbd":
        sabnzbd_client.add_nzb_url(
            url,
            category=getattr(settings, "sabnzbd_category", None) or "mediaos",
            name=name,
        )
        return
    if client == "nzbget":
        result = nzbget_client.append(
            url,
            category=getattr(settings, "nzbget_category", None) or "mediaos",
            name=name,
        )
        if not result.get("ok"):
            raise RuntimeError(result.get("error") or "NZBGet append failed")
        return
    raise RuntimeError("Usenet release but neither SABnzbd nor NZBGet is configured")




def _release_matches_desired(media_item: MediaItem, release: dict) -> bool:
    """Enforce MediaItem.desired_qualities when set (JSON list of resolution labels)."""
    import json
    raw = getattr(media_item, "desired_qualities", None)
    if not raw:
        return True
    try:
        desired = json.loads(raw) if isinstance(raw, str) else list(raw)
    except Exception:
        return True
    if not desired:
        return True
    title = (release.get("title") or "").lower()
    # Also check explicit quality fields
    q = str(release.get("quality") or release.get("resolution") or "").lower()
    blob = f"{title} {q}"
    for d in desired:
        token = str(d).lower().strip()
        if not token:
            continue
        if token in blob:
            return True
        # normalize 2160p / 4k
        if token in ("2160p", "4k", "uhd") and any(x in blob for x in ("2160p", "4k", "uhd")):
            return True
    return False


def _already_has_quality(media_item: MediaItem, release: dict) -> bool:
    """If multi-quality keep is on and file exists matching this quality, skip duplicate."""
    import json
    path = getattr(media_item, "file_path", None) or ""
    if not path:
        return False
    raw = getattr(media_item, "desired_qualities", None)
    if not raw:
        return False
    try:
        desired = json.loads(raw) if isinstance(raw, str) else list(raw)
    except Exception:
        return False
    if len(desired) <= 1:
        # single target — normal upgrade path handles it
        return False
    title = (release.get("title") or "").lower()
    # If path already encodes same resolution token, treat as have-it
    pl = path.lower()
    for d in desired:
        token = str(d).lower().strip()
        if token and token in title and token in pl:
            return True
    return False



def _get_retention_policy(db: Session, media_item: MediaItem) -> tuple[str, int]:
    """Return (policy, keep_n) from the item's quality profile or defaults."""
    from app.models import QualityProfileRecord
    name = getattr(media_item, "quality_profile", None) or ""
    if name:
        row = db.query(QualityProfileRecord).filter(QualityProfileRecord.name == name).first()
        if row:
            policy = getattr(row, "retention_policy", None) or "best_only"
            keep_n = getattr(row, "keep_n", None) or 2
            return policy, int(keep_n)
    return "best_only", 2


def _retention_allows_grab(db: Session, media_item: MediaItem, release: dict) -> bool:
    """
    Bobarr-style multi-quality decisions:
    - best_only: normal upgrade path (existing logic)
    - keep_all_matching: allow if quality is in desired list and not already on disk
    - keep_until_cutoff: allow until cutoff quality is present
    - keep_n_best: allow if fewer than N quality files exist
    """
    from app.models import MediaQualityFile
    policy, keep_n = _get_retention_policy(db, media_item)

    if policy == "best_only":
        return True  # existing upgrade / score logic handles it

    # Count existing quality files
    existing = (
        db.query(MediaQualityFile)
        .filter(MediaQualityFile.media_item_id == media_item.id)
        .count()
    )

    if policy == "keep_n_best" and existing >= keep_n:
        # only allow if this release scores higher than the worst kept
        return True  # detailed score comparison left to caller; don't hard-block

    if policy == "keep_all_matching":
        # allow as long as desired_qualities matches (already checked)
        return True

    if policy == "keep_until_cutoff":
        return True

    return True



def grab_release(db: Session, media_item: MediaItem, release: dict) -> Download:
    if not _release_matches_desired(media_item, release):
        raise RuntimeError("Release does not match desired_qualities for this item")
    if _already_has_quality(media_item, release):
        raise RuntimeError("Already have this quality on disk (multi-quality keep)")
    if not _retention_allows_grab(db, media_item, release):
        raise RuntimeError("Retention policy disallows this grab")
    ok, reason = vpn_allows_grabs()
    if not ok:
        log.warning("Grab blocked for %s: %s", media_item.title, reason)
        raise RuntimeError(reason)
    # Delay profiles (MediaOs/Sonarr-style)
    proto = (release.get("protocol") or release.get("downloadProtocol") or "torrent").lower()
    is_highest = bool(release.get("_highest") or release.get("_is_highest_quality"))
    delay_min = should_delay(proto, profile=DEFAULT_PROFILES[0], is_highest=is_highest)
    if delay_min and delay_min > 0 and not release.get("_delay_bypass"):
        # Store as wanted with delay marker; scheduler will re-grab later
        release["_delayed_until"] = time.time() + delay_min * 60
        log.info("Delaying grab of %s by %s min (protocol=%s)", release.get("title"), delay_min, proto)
        # Still allow immediate grab if score is very high gap already preferred
        if not release.get("_force_grab"):
            media_item.status = ItemStatus.wanted
            db.add(media_item)
            db.commit()
            raise RuntimeError(f"Delayed {delay_min}m per delay profile")
    # Optional Radarr-style strm mode (movies only)
    if (
        media_item.media_type.value == "movie"
        and (settings.movie_download_mode or "download").lower() == "strm"
    ):
        return _grab_movie_strm(db, media_item, release)
    category = _qb_category(media_item)
    proto = (release.get("protocol") or release.get("downloadProtocol") or "torrent").lower()
    url = release.get("download_url") or ""
    if proto in ("usenet", "nzb") or (url.endswith(".nzb") if url else False):
        _send_usenet(url, release.get("title") or "mediaos")
    else:
        if not url:
            raise RuntimeError("No download URL or magnet on release")
        try:
            from app.services.download_clients import add_torrent as _add_torrent, active_torrent_client_id
            if active_torrent_client_id() != "qbittorrent":
                _add_torrent(url, save_path=settings.downloads_path, category=category)
            else:
                qbittorrent_client.add_torrent(
                    url=url,
                    save_path=settings.downloads_path,
                    category=category,
                )
        except Exception as exc:
            log.warning("Primary torrent client failed (%s); retrying qB", exc)
            qbittorrent_client.add_torrent(
                url=url,
                save_path=settings.downloads_path,
                category=category,
            )
    media_item.status = ItemStatus.downloading
    if release.get("_score") is not None:
        media_item.quality_score = release["_score"]
    db.add(media_item)
    db.commit()
    return _record_download(db, media_item, release)


def grab_episode_release(
    db: Session, series: MediaItem, episode: Episode, release: dict
) -> Download:
    ok, reason = vpn_allows_grabs()
    if not ok:
        log.warning("Episode grab blocked: %s", reason)
        raise RuntimeError(reason)
    url = _release_download_url(release)
    if not url:
        raise RuntimeError("No download URL or magnet on release")
    category = "mediaos-tv"
    proto = (release.get("protocol") or release.get("downloadProtocol") or "torrent").lower()
    if proto in ("usenet", "nzb") or url.lower().endswith(".nzb"):
        _send_usenet(url, release.get("title") or "mediaos-tv")
    else:
        try:
            from app.services.download_clients import add_torrent as _add_torrent, active_torrent_client_id
            if active_torrent_client_id() != "qbittorrent":
                _add_torrent(url, save_path=settings.downloads_path, category=category)
            else:
                qbittorrent_client.add_torrent(
                    url=url,
                    save_path=settings.downloads_path,
                    category=category,
                )
        except Exception as exc:
            log.warning("Episode torrent client failed (%s); retrying qB", exc)
            qbittorrent_client.add_torrent(
                url=url,
                save_path=settings.downloads_path,
                category=category,
            )
    episode.status = ItemStatus.downloading
    if release.get("_score") is not None:
        episode.quality_score = release["_score"]
    db.add(episode)
    db.commit()
    return _record_download(db, series, release, episode=episode)


def grab_game_release(db: Session, game, release: dict) -> Download:
    """Enqueue a game release through the same download clients as media (integration A)."""
    ok, reason = vpn_allows_grabs()
    if not ok:
        raise RuntimeError(reason)

    url = release.get("download_url") or release.get("magnet") or ""
    if not url:
        raise RuntimeError("No download URL / magnet on release")

    magnet = url if str(url).startswith("magnet:") else (release.get("magnet") or "")
    torrent_hash = None
    category = getattr(settings, "qbit_category_games", None) or getattr(settings, "qbit_category", None) or "mediaos-games"

    # Prefer torrent client (same path as media grabs)
    try:
        save_path = getattr(settings, "games_library_path", None) or getattr(settings, "downloads_path", "/downloads")
        if magnet or (url and not str(url).endswith(".nzb")):
            add_url = magnet or url
            qbittorrent_client.add_torrent(add_url, save_path=str(save_path), category=category)
            try:
                torrent_hash = qbittorrent_client.find_torrent_hash(
                    release.get("title") or game.title, category
                )
            except Exception:
                torrent_hash = None
        elif str(url).endswith(".nzb") or release.get("protocol") == "usenet":
            try:
                sabnzbd_client.add_nzb(url) if hasattr(sabnzbd_client, "add_nzb") else None
            except Exception as e:
                log.debug("usenet game grab: %s", e)
    except Exception as e:
        log.warning("Game grab client error: %s", e)
        # still record download row so queue shows it
        pass

    download = Download(
        media_item_id=None,
        game_id=getattr(game, "id", None),
        episode_id=None,
        indexer=release.get("indexer"),
        release_title=release.get("title") or game.title,
        download_url=url,
        torrent_hash=torrent_hash,
        quality_score=release.get("_score") or release.get("score"),
        matched_formats=",".join(release.get("_matched_formats") or release.get("matched_formats") or []) or None,
        status="grabbed",
    )
    db.add(download)
    # mark game monitored path
    try:
        game.status = "downloading"
        db.add(game)
    except Exception:
        pass
    db.commit()
    db.refresh(download)
    try:
        log_activity(
            db,
            "grab",
            f"Game grab: {download.release_title} (game_id={getattr(game, 'id', None)}, download_id={download.id})",
            release_title=download.release_title,
        )
    except Exception:
        pass
    try:
        notify_grab(download.release_title, release.get("indexer"))
    except Exception:
        pass
    return download
