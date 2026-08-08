"""Podcast tracking service — RSS refresh + episode download.

Zero apps in the arr ecosystem (or MediaOs) do this: subscribe to a feed,
poll for new episodes, auto-download audio as it's published.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.clients.podcast_rss import podcast_rss_client, slugify
from app.config import settings
from app.models import ItemStatus, Podcast, PodcastEpisode

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def add_podcast(db: Session, feed_url: str, *, monitored: bool = True, auto_download: bool | None = None) -> Podcast:
    existing = db.query(Podcast).filter(Podcast.feed_url == feed_url).first()
    if existing:
        return existing

    data = podcast_rss_client.fetch_feed(feed_url)
    podcast = Podcast(
        feed_url=feed_url,
        title=data["title"],
        author=data.get("author"),
        description=data.get("description"),
        image=data.get("image"),
        monitored=monitored,
        auto_download=settings.podcast_auto_download_default if auto_download is None else auto_download,
    )
    db.add(podcast)
    db.commit()
    db.refresh(podcast)

    # Backlog: ingest existing episodes as tracked, but only mark them
    # "wanted" (eligible for auto-download) if the backlog flag is on —
    # otherwise they're recorded so future refreshes don't treat them as new.
    refresh_podcast(db, podcast, mark_existing_as_downloaded=not settings.podcast_backlog_download)
    return podcast


def refresh_podcast(db: Session, podcast: Podcast, *, mark_existing_as_downloaded: bool = False) -> dict:
    data = podcast_rss_client.fetch_feed(podcast.feed_url)
    podcast.title = data["title"] or podcast.title
    podcast.description = data.get("description") or podcast.description
    podcast.image = data.get("image") or podcast.image
    podcast.last_checked_at = _utcnow()

    existing_by_guid = {e.guid: e for e in podcast.episodes}
    existing_guids = set(existing_by_guid)
    new_count = 0
    for ep in data["episodes"]:
        if ep["guid"] in existing_guids:
            # Refresh chapter metadata when feed adds/updates it
            ch = ep.get("chapters") or []
            if ch:
                row = existing_by_guid[ep["guid"]]
                row.chapters_json = json.dumps(ch)
                db.add(row)
            continue
        ch = ep.get("chapters") or []
        row = PodcastEpisode(
            podcast_id=podcast.id,
            guid=ep["guid"],
            title=ep["title"],
            audio_url=ep["audio_url"],
            pub_date=ep.get("pub_date"),
            duration_seconds=ep.get("duration_seconds"),
            episode_number=ep.get("episode_number"),
            chapters_json=json.dumps(ch) if ch else None,
            status=ItemStatus.downloaded if mark_existing_as_downloaded else ItemStatus.wanted,
        )
        db.add(row)
        new_count += 1

    podcast.episode_count = len(data["episodes"])
    db.add(podcast)
    db.commit()
    return {"new_episodes": new_count, "total_in_feed": podcast.episode_count}


def _within_download_window(podcast: Podcast, pub_date: str | None) -> bool:
    if not podcast.download_window_days or not pub_date:
        return True
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(pub_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return True
    cutoff = _utcnow() - timedelta(days=podcast.download_window_days)
    return dt >= cutoff


def download_episode(db: Session, episode: PodcastEpisode) -> PodcastEpisode:
    podcast = episode.podcast
    show_dir = os.path.join(settings.podcasts_library_path, slugify(podcast.title))
    os.makedirs(show_dir, exist_ok=True)

    ext = os.path.splitext(episode.audio_url.split("?")[0])[1] or ".mp3"
    ext = ext if len(ext) <= 5 else ".mp3"
    prefix = f"{episode.episode_number:04d}-" if episode.episode_number else ""
    filename = f"{prefix}{slugify(episode.title)}{ext}"
    dest = os.path.join(show_dir, filename)

    with httpx.stream("GET", episode.audio_url, timeout=60.0, follow_redirects=True) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1 << 16):
                f.write(chunk)

    episode.file_path = dest
    episode.status = ItemStatus.downloaded
    episode.downloaded_at = _utcnow()
    db.add(episode)
    db.commit()
    db.refresh(episode)
    log.info("Downloaded podcast episode %r -> %s", episode.title, dest)
    return episode


def check_and_download_all(db: Session, *, limit_per_show: int = 10) -> dict:
    """Scheduler entrypoint: refresh every monitored feed, auto-download
    newly-discovered episodes for shows with auto_download enabled."""
    podcasts = db.query(Podcast).filter(Podcast.monitored.is_(True)).all()
    summary = {"checked": 0, "downloaded": 0, "errors": []}
    for podcast in podcasts:
        try:
            refresh_podcast(db, podcast)
            summary["checked"] += 1
            if not podcast.auto_download:
                continue
            wanted = (
                db.query(PodcastEpisode)
                .filter(
                    PodcastEpisode.podcast_id == podcast.id,
                    PodcastEpisode.status == ItemStatus.wanted,
                )
                .order_by(PodcastEpisode.added_at.desc())
                .limit(limit_per_show)
                .all()
            )
            for ep in wanted:
                if not _within_download_window(podcast, ep.pub_date):
                    continue
                try:
                    download_episode(db, ep)
                    summary["downloaded"] += 1
                except Exception as exc:
                    log.exception("Podcast episode download failed: %s", exc)
                    summary["errors"].append(f"{podcast.title} / {ep.title}: {exc}")
        except Exception as exc:
            log.exception("Podcast refresh failed for %s: %s", podcast.title, exc)
            summary["errors"].append(f"{podcast.title}: {exc}")
    return summary
