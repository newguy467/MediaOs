"""Post-organize hooks: subtitles, Apprise, Discord, Telegram, Jellyfin/Emby refresh."""
from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Episode, MediaItem
from app.services.subtitles import fetch_subtitles

log = logging.getLogger(__name__)


def _discord_notify(message: str, *, title: str = "mediaos") -> None:
    url = (settings.discord_webhook_url or "").strip()
    if not url:
        return
    content = f"**{title}**\n{message}"[:1900]
    payload = {"content": content}
    last = None
    for _ in range(2):
        try:
            r = httpx.post(url, json=payload, timeout=10.0)
            if r.status_code < 400:
                return
            last = f"HTTP {r.status_code}"
        except Exception as exc:
            last = str(exc)
        time.sleep(0.8)
    log.warning("Discord notify failed: %s", last)


def _telegram_notify(message: str) -> None:
    token = (settings.telegram_bot_token or "").strip()
    chat = (settings.telegram_chat_id or "").strip()
    if not token or not chat:
        return
    last = None
    for _ in range(2):
        try:
            r = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": message[:4000]},
                timeout=10.0,
            )
            if r.status_code < 400:
                return
            last = f"HTTP {r.status_code}"
        except Exception as exc:
            last = str(exc)
        time.sleep(0.8)
    log.warning("Telegram notify failed: %s", last)


def _apprise_notify(message: str) -> None:
    url = (settings.apprise_url or "").strip()
    if not url:
        return
    try:
        r = httpx.post(url, json={"body": message, "title": "mediaos"}, timeout=10.0)
        if r.status_code >= 400:
            log.warning("Apprise notify HTTP %s", r.status_code)
    except Exception as exc:
        log.warning("Apprise notify failed: %s", exc)


def notify(message: str, *, title: str = "mediaos") -> None:
    """Fan-out to all configured notification channels."""
    _apprise_notify(message)
    _discord_notify(message, title=title)
    _telegram_notify(f"{title}: {message}" if title else message)


def jellyfin_refresh() -> None:
    base = (settings.jellyfin_url or "").rstrip("/")
    key = settings.jellyfin_api_key
    if not base or not key:
        return
    try:
        httpx.post(
            f"{base}/Library/Refresh",
            headers={"X-Emby-Token": key},
            timeout=15.0,
        )
    except Exception as exc:
        log.debug("Jellyfin refresh failed: %s", exc)


def emby_refresh() -> None:
    base = (getattr(settings, "emby_url", "") or "").rstrip("/")
    key = getattr(settings, "emby_api_key", "") or ""
    if not base or not key:
        return
    try:
        httpx.post(
            f"{base}/Library/Refresh",
            headers={"X-Emby-Token": key},
            timeout=15.0,
        )
    except Exception as exc:
        log.debug("Emby refresh failed: %s", exc)


def media_server_refresh() -> None:
    jellyfin_refresh()
    emby_refresh()


def fetch_subtitles_for_video(
    video_path: Path,
    *,
    item: MediaItem | None = None,
    episode: Episode | None = None,
) -> None:
    result = fetch_subtitles(video_path, item=item, episode=episode)
    if result.get("ok"):
        log.info("Subtitles via %s → %s", result.get("provider"), result.get("path"))
    else:
        log.debug("No subtitles for %s: %s", video_path, result.get("error"))


def after_organize(db: Session, item: MediaItem, dest_path: Path) -> None:
    try:
        from app.services.plugins import run_hook
        run_hook("organize", item, dest_path)
    except Exception:
        pass

    if not str(dest_path).endswith(".strm"):
        fetch_subtitles_for_video(dest_path, item=item)
    notify(f"Downloaded: {item.title}", title="Download complete")
    media_server_refresh()


def after_organize_episode(
    db: Session, series: MediaItem, episode: Episode, dest_path: Path
) -> None:
    try:
        from app.services.plugins import run_hook
        run_hook("organize_episode", series, episode, dest_path)
    except Exception:
        pass
    fetch_subtitles_for_video(dest_path, item=series, episode=episode)
    notify(
        f"Downloaded: {series.title} S{episode.season_number:02d}E{episode.episode_number:02d}",
        title="Episode complete",
    )
    media_server_refresh()


# ── Event-typed notifications (grab, failure, request, etc.) ─────────────────

def notify_event(event: str, message: str, *, title: str | None = None) -> None:
    try:
        from app.services.plugins import run_hook
        run_hook("event", event, message, title=title)
        run_hook(f"event.{event}", message, title=title)
    except Exception:
        pass
    # Notify all channels with an event label (grab, download, failure, request, …)
    label = title or {
        "grab": "Grabbed",
        "download": "Download complete",
        "organize": "Organized",
        "failure": "Failure",
        "request": "Request",
        "upgrade": "Upgrade",
        "import": "Import",
        "migrate": "Migration",
        "blocklist": "Blocklist",
        "cleanup": "Cleanup",
        "subtitle": "Subtitles",
        "convert": "Converter",
    }.get(event, event.replace("_", " ").title())
    notify(message, title=label)


def notify_grab(title: str, indexer: str | None = None) -> None:
    """Notify that a release was sent to the download client."""
    try:
        from app.services.plugins import run_hook
        run_hook("grab", title, indexer=indexer)
    except Exception:
        pass
    idx = f" via {indexer}" if indexer else ""
    notify_event("grab", f"{title}{idx}", title="Grabbed")


def notify_failure(message: str) -> None:
    notify_event("failure", message, title="Failure")


def notify_request(message: str) -> None:
    notify_event("request", message, title="Request")


def notify_upgrade(message: str) -> None:
    notify_event("upgrade", message, title="Upgrade")


def after_organize_series(db: Session, series: MediaItem) -> None:
    """Called when a whole series pack finishes organizing."""
    notify(f"Series organized: {series.title}", title="Series complete")
    media_server_refresh()
