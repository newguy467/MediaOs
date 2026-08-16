"""Notification center — Discord, Telegram, Apprise, ntfy, Gotify + history."""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("mediaos.notifications")

_lock = threading.Lock()
_history: deque[dict[str, Any]] = deque(maxlen=200)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record(channel: str, title: str, message: str, ok: bool, error: str | None = None) -> None:
    with _lock:
        _history.appendleft({
            "ts": _utcnow(),
            "channel": channel,
            "title": title,
            "message": message[:500],
            "ok": ok,
            "error": error,
        })


def channels_status() -> list[dict[str, Any]]:
    return [
        {"id": "discord", "enabled": bool(getattr(settings, "discord_webhook_url", "")), "label": "Discord webhook"},
        {"id": "telegram", "enabled": bool(getattr(settings, "telegram_bot_token", "") and getattr(settings, "telegram_chat_id", "")), "label": "Telegram"},
        {"id": "apprise", "enabled": bool(getattr(settings, "apprise_url", "")), "label": "Apprise"},
        {"id": "ntfy", "enabled": bool(getattr(settings, "ntfy_url", "") or getattr(settings, "ntfy_topic", "")), "label": "ntfy"},
        {"id": "gotify", "enabled": bool(getattr(settings, "gotify_url", "") and getattr(settings, "gotify_token", "")), "label": "Gotify"},
    ]


def history(limit: int = 50) -> list[dict]:
    with _lock:
        return list(_history)[:limit]


def _discord(message: str, title: str) -> None:
    url = (getattr(settings, "discord_webhook_url", "") or "").strip()
    if not url:
        return
    try:
        r = httpx.post(url, json={"content": f"**{title}**\n{message}"[:1900]}, timeout=10.0)
        _record("discord", title, message, r.status_code < 400, None if r.status_code < 400 else f"HTTP {r.status_code}")
    except Exception as e:
        _record("discord", title, message, False, str(e))


def _telegram(message: str, title: str) -> None:
    token = (getattr(settings, "telegram_bot_token", "") or "").strip()
    chat = (getattr(settings, "telegram_chat_id", "") or "").strip()
    if not token or not chat:
        return
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": f"{title}\n{message}"[:4000]},
            timeout=10.0,
        )
        _record("telegram", title, message, r.status_code < 400, None if r.status_code < 400 else f"HTTP {r.status_code}")
    except Exception as e:
        _record("telegram", title, message, False, str(e))


def _apprise(message: str, title: str) -> None:
    url = (getattr(settings, "apprise_url", "") or "").strip()
    if not url:
        return
    try:
        r = httpx.post(url, json={"body": message, "title": title}, timeout=10.0)
        _record("apprise", title, message, r.status_code < 400, None if r.status_code < 400 else f"HTTP {r.status_code}")
    except Exception as e:
        _record("apprise", title, message, False, str(e))


def _ntfy(message: str, title: str) -> None:
    base = (getattr(settings, "ntfy_url", "") or "").strip().rstrip("/")
    topic = (getattr(settings, "ntfy_topic", "") or "").strip()
    if not base and topic:
        base = f"https://ntfy.sh/{topic}"
    elif base and topic and not base.endswith(topic):
        base = f"{base}/{topic}"
    if not base:
        return
    headers = {"Title": title}
    token = (getattr(settings, "ntfy_token", "") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = httpx.post(base, content=message.encode("utf-8"), headers=headers, timeout=10.0)
        _record("ntfy", title, message, r.status_code < 400, None if r.status_code < 400 else f"HTTP {r.status_code}")
    except Exception as e:
        _record("ntfy", title, message, False, str(e))


def _gotify(message: str, title: str) -> None:
    base = (getattr(settings, "gotify_url", "") or "").strip().rstrip("/")
    token = (getattr(settings, "gotify_token", "") or "").strip()
    if not base or not token:
        return
    try:
        r = httpx.post(
            f"{base}/message",
            params={"token": token},
            json={"title": title, "message": message, "priority": 5},
            timeout=10.0,
        )
        _record("gotify", title, message, r.status_code < 400, None if r.status_code < 400 else f"HTTP {r.status_code}")
    except Exception as e:
        _record("gotify", title, message, False, str(e))


def send(message: str, *, title: str = "MediaOS", channels: list[str] | None = None) -> dict[str, Any]:
    """Fan-out notification. channels=None → all configured."""
    want = set(channels) if channels else None
    if want is None or "discord" in want:
        _discord(message, title)
    if want is None or "telegram" in want:
        _telegram(message, title)
    if want is None or "apprise" in want:
        _apprise(message, title)
    if want is None or "ntfy" in want:
        _ntfy(message, title)
    if want is None or "gotify" in want:
        _gotify(message, title)
    return {"ok": True, "title": title, "channels": channels_status(), "history_head": history(5)}


def test_all() -> dict[str, Any]:
    return send("MediaOS notification test — if you see this, channels are wired.", title="MediaOS test")
