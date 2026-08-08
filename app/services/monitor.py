"""Sonarr-style episode monitor rules."""
from __future__ import annotations

from datetime import date, datetime

from app.models import Episode, ItemStatus


def _aired(ep: Episode, today: date | None = None) -> bool:
    today = today or date.today()
    if not ep.air_date:
        return True  # unknown → treat as aired
    try:
        # TVDb often YYYY-MM-DD
        d = datetime.strptime(ep.air_date[:10], "%Y-%m-%d").date()
        return d <= today
    except ValueError:
        return True


def apply_monitor_mode(episodes: list[Episode], mode: str) -> None:
    """
    Mutates episode.monitored (and leaves status alone).
    Modes:
      all     — every episode
      future  — only unaired (not yet aired)
      missing — aired + not downloaded
      first   — season 1 only (all eps in S01)
      none    — nothing monitored
    """
    mode = (mode or "all").lower()
    today = date.today()

    for ep in episodes:
        if mode == "none":
            ep.monitored = False
        elif mode == "all":
            ep.monitored = True
        elif mode == "first":
            ep.monitored = ep.season_number == 1
        elif mode == "future":
            ep.monitored = not _aired(ep, today)
        elif mode == "missing":
            ep.monitored = _aired(ep, today) and ep.status != ItemStatus.downloaded
        else:
            ep.monitored = True
