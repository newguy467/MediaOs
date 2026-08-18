"""Optional Redis connection for multi-worker rate limits, session cache, leader election.

When REDIS_URL is empty or redis-py is not installed, all helpers return None / no-op
and callers fall back to process-local behavior.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

log = logging.getLogger(__name__)

_client: Any = None
_lock = threading.Lock()
_failed = False


def get_redis():
    """Return a redis.Redis client or None."""
    global _client, _failed
    if _failed:
        return None
    if _client is not None:
        return _client
    with _lock:
        if _client is not None:
            return _client
        if _failed:
            return None
        try:
            from app.config import settings
            url = (getattr(settings, "redis_url", None) or "").strip()
            if not url:
                _failed = True
                return None
            import redis  # type: ignore

            c = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=1.5, socket_timeout=2.0)
            c.ping()
            _client = c
            log.info("Redis connected (%s)", url.split("@")[-1] if "@" in url else url)
            return _client
        except Exception as e:
            log.info("Redis unavailable (%s) — using process-local fallbacks", e)
            _failed = True
            return None


def reset_for_tests() -> None:
    """Clear cached client (unit tests)."""
    global _client, _failed
    _client = None
    _failed = False
