"""Scheduler leader election for multi-replica deployments.

Uses Redis SET NX + EX when REDIS_URL is set. Without Redis, every process
considers itself leader (single-node / dev default).

Renewal: call refresh_leader() periodically from the scheduler process so the
TTL does not expire while this instance is healthy.
"""
from __future__ import annotations

import logging
import os
import socket
import threading
import time
import uuid
from typing import Optional

log = logging.getLogger(__name__)

_KEY = "mediaos:scheduler:leader"
_instance_id: Optional[str] = None
_lock = threading.Lock()
_is_leader_cache = True  # default: single-node leader
_last_check = 0.0

# Atomic compare-and-{expire,delete} so renewal/release can't act on a key
# that a different replica acquired in the gap between GET and the
# follow-up EXPIRE/DEL. A plain "GET then EXPIRE/DEL" is two round-trips:
# if this instance's key expires and another replica wins acquisition in
# between them, the EXPIRE would silently extend the *other* replica's
# lease (a false "I'm still leader" reading here), and the DEL in
# release_leader() would drop the *other* replica's lease out from under
# it (both replicas could then believe they're leader). Lua scripts run
# atomically on the Redis server, closing that window.
_RENEW_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("EXPIRE", KEYS[1], ARGV[2])
else
    return 0
end
"""
_RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


def _id() -> str:
    global _instance_id
    if _instance_id:
        return _instance_id
    host = socket.gethostname()
    _instance_id = f"{host}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    return _instance_id


def instance_id() -> str:
    return _id()


def try_become_leader(*, ttl_seconds: int | None = None) -> bool:
    """Attempt to acquire or renew leadership. Returns True if this process is leader."""
    global _is_leader_cache, _last_check
    from app.services.redis_client import get_redis

    r = get_redis()
    if r is None:
        _is_leader_cache = True
        return True

    if ttl_seconds is None:
        try:
            from app.config import settings
            ttl_seconds = int(getattr(settings, "scheduler_leader_ttl_seconds", 45) or 45)
        except Exception:
            ttl_seconds = 45
    iid = _id()
    ttl = max(15, int(ttl_seconds))
    try:
        # Renew if we already own it (atomic compare-and-expire — see
        # _RENEW_SCRIPT comment above)
        renewed = r.eval(_RENEW_SCRIPT, 1, _KEY, iid, ttl)
        if renewed:
            _is_leader_cache = True
            _last_check = time.time()
            return True
        # Try acquire
        ok = r.set(_KEY, iid, nx=True, ex=ttl)
        if ok:
            log.info("Scheduler leader acquired (%s)", iid)
            _is_leader_cache = True
            _last_check = time.time()
            return True
        _is_leader_cache = False
        _last_check = time.time()
        return False
    except Exception as e:
        log.warning("Leader election error (%s) — assuming leader for safety of single-node", e)
        _is_leader_cache = True
        return True


def refresh_leader(*, ttl_seconds: int = 45) -> bool:
    return try_become_leader(ttl_seconds=ttl_seconds)


def is_leader(*, max_stale_s: float = 20.0) -> bool:
    """Fast check; re-probes Redis if cache is stale."""
    if time.time() - _last_check > max_stale_s:
        return try_become_leader()
    return _is_leader_cache


def release_leader() -> None:
    from app.services.redis_client import get_redis

    r = get_redis()
    if r is None:
        return
    try:
        # Atomic compare-and-delete — see _RELEASE_SCRIPT comment above.
        deleted = r.eval(_RELEASE_SCRIPT, 1, _KEY, _id())
        if deleted:
            log.info("Scheduler leader released")
    except Exception as e:
        log.debug("release_leader: %s", e)
