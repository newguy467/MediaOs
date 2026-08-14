"""Per-indexer / per-host delay, rate limiting, and temporary backoff registry.

Closer to *arr / Cinephage-style indexer health: respect delay, remember failures,
expose a snapshot the interactive UI / system status can show.

When REDIS_URL is set and reachable, backoff / fail counts / last-request timestamps
are shared across workers. Without Redis, process-local RLock state is used.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any


_lock = threading.RLock()  # reentrant: snapshot() calls host_snapshot() while already holding this
_last_request: dict[str, float] = defaultdict(float)
_default_delay = 1.0

# key -> unix monotonic deadline until which the key is in backoff (local mode)
_backoff_until: dict[str, float] = {}
_fail_counts: dict[str, int] = defaultdict(int)
_last_error: dict[str, str] = {}

_PREFIX = "mediaos:rl:"


def _redis():
    try:
        from app.services.redis_client import get_redis
        return get_redis()
    except Exception:
        return None


def wait(key: str, delay_seconds: float | None = None) -> None:
    """Block until `delay_seconds` have passed since last call for `key`."""
    delay = _default_delay if delay_seconds is None else max(0.0, float(delay_seconds))
    r = _redis()
    if r is not None:
        rk = f"{_PREFIX}last:{key}"
        try:
            last_s = r.get(rk)
            last = float(last_s) if last_s else 0.0
            now = time.time()
            wait_for = (last + delay) - now
            if wait_for > 0:
                time.sleep(wait_for)
                now = time.time()
            r.set(rk, str(now), ex=86400)
            return
        except Exception:
            pass
    with _lock:
        last = _last_request.get(key, 0.0)
        now = time.monotonic()
        wait_for = (last + delay) - now
        if wait_for > 0:
            time.sleep(wait_for)
            now = time.monotonic()
        _last_request[key] = now


def set_default_delay(seconds: float) -> None:
    global _default_delay
    _default_delay = max(0.0, float(seconds))


def is_in_backoff(key: str) -> bool:
    r = _redis()
    if r is not None:
        try:
            until_s = r.get(f"{_PREFIX}backoff:{key}")
            if not until_s:
                return False
            until = float(until_s)
            if time.time() >= until:
                r.delete(f"{_PREFIX}backoff:{key}")
                return False
            return True
        except Exception:
            pass
    with _lock:
        until = _backoff_until.get(key)
        if until is None:
            return False
        if time.monotonic() >= until:
            _backoff_until.pop(key, None)
            return False
        return True


def remaining_backoff(key: str) -> float:
    r = _redis()
    if r is not None:
        try:
            until_s = r.get(f"{_PREFIX}backoff:{key}")
            if not until_s:
                return 0.0
            return max(0.0, float(until_s) - time.time())
        except Exception:
            pass
    with _lock:
        until = _backoff_until.get(key)
        if not until:
            return 0.0
        return max(0.0, until - time.monotonic())


def record_success(key: str) -> None:
    r = _redis()
    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.delete(f"{_PREFIX}fail:{key}")
            pipe.delete(f"{_PREFIX}err:{key}")
            pipe.delete(f"{_PREFIX}backoff:{key}")
            pipe.execute()
        except Exception:
            pass
    with _lock:
        _fail_counts[key] = 0
        _last_error.pop(key, None)
        _backoff_until.pop(key, None)


def record_failure(key: str, error: str | None = None, *, base_seconds: float = 30.0) -> float:
    """Register a failure; exponential backoff capped at 15 minutes. Returns backoff seconds."""
    r = _redis()
    if r is not None:
        try:
            fk = f"{_PREFIX}fail:{key}"
            n = int(r.incr(fk))
            r.expire(fk, 86400)
            if error:
                r.set(f"{_PREFIX}err:{key}", str(error)[:200], ex=86400)
            seconds = min(900.0, float(base_seconds) * (2 ** min(n - 1, 5)))
            r.set(f"{_PREFIX}backoff:{key}", str(time.time() + seconds), ex=int(seconds) + 60)
            return seconds
        except Exception:
            pass
    with _lock:
        n = _fail_counts[key] + 1
        _fail_counts[key] = n
        if error:
            _last_error[key] = str(error)[:200]
        seconds = min(900.0, float(base_seconds) * (2 ** min(n - 1, 5)))
        _backoff_until[key] = time.monotonic() + seconds
        return seconds


def clear_backoff(key: str | None = None) -> None:
    r = _redis()
    if r is not None:
        try:
            if key is None:
                for pattern in (f"{_PREFIX}backoff:*", f"{_PREFIX}fail:*", f"{_PREFIX}err:*"):
                    for k in r.scan_iter(pattern, count=100):
                        r.delete(k)
            else:
                r.delete(f"{_PREFIX}backoff:{key}", f"{_PREFIX}fail:{key}", f"{_PREFIX}err:{key}")
        except Exception:
            pass
    with _lock:
        if key is None:
            _backoff_until.clear()
            _fail_counts.clear()
            _last_error.clear()
        else:
            _backoff_until.pop(key, None)
            _fail_counts.pop(key, None)
            _last_error.pop(key, None)


def snapshot() -> dict[str, Any]:
    r = _redis()
    if r is not None:
        try:
            now = time.time()
            indexers = []
            keys: set[str] = set()
            for pattern in (f"{_PREFIX}last:*", f"{_PREFIX}backoff:*", f"{_PREFIX}fail:*"):
                for full in r.scan_iter(pattern, count=200):
                    keys.add(full.split(":", 3)[-1] if full.count(":") >= 3 else full.rsplit(":", 1)[-1])
            for k in sorted(keys):
                until_s = r.get(f"{_PREFIX}backoff:{k}")
                until = float(until_s) if until_s else None
                last_s = r.get(f"{_PREFIX}last:{k}")
                fail_s = r.get(f"{_PREFIX}fail:{k}")
                err = r.get(f"{_PREFIX}err:{k}")
                indexers.append({
                    "key": k,
                    "last_request_age_s": round(now - float(last_s), 1) if last_s else None,
                    "fail_count": int(fail_s or 0),
                    "in_backoff": bool(until and until > now),
                    "backoff_remaining_s": round(max(0.0, (until or 0) - now), 1) if until else 0,
                    "last_error": err,
                    "backend": "redis",
                })
            return {
                "default_delay_s": _default_delay,
                "indexers": indexers,
                "hosts": host_snapshot(),
                "backend": "redis",
            }
        except Exception:
            pass
    with _lock:
        now = time.monotonic()
        indexers = []
        keys = set(_last_request) | set(_backoff_until) | set(_fail_counts)
        for k in sorted(keys):
            until = _backoff_until.get(k)
            indexers.append({
                "key": k,
                "last_request_age_s": round(now - _last_request[k], 1) if k in _last_request else None,
                "fail_count": int(_fail_counts.get(k, 0)),
                "in_backoff": bool(until and until > now),
                "backoff_remaining_s": round(max(0.0, (until or 0) - now), 1) if until else 0,
                "last_error": _last_error.get(k),
                "backend": "local",
            })
        return {
            "default_delay_s": _default_delay,
            "indexers": indexers,
            "hosts": host_snapshot(),
            "backend": "local",
        }


# ── Host concurrency map (process-local; Redis optional shared counters) ─────
_host_inflight: dict[str, int] = defaultdict(int)
_host_max: dict[str, int] = defaultdict(lambda: 2)
_host_total_done: dict[str, int] = defaultdict(int)


def set_host_max(host: str, max_parallel: int) -> None:
    with _lock:
        _host_max[host] = max(1, int(max_parallel))
    r = _redis()
    if r is not None:
        try:
            r.set(f"{_PREFIX}hostmax:{host}", str(max(1, int(max_parallel))), ex=86400)
        except Exception:
            pass


def acquire_host(host: str, *, timeout: float = 15.0) -> bool:
    """Block until a concurrency slot is free for host. Returns False on timeout."""
    r = _redis()
    if r is not None:
        rk = f"{_PREFIX}hostinflight:{host}"
        deadline = time.time() + timeout
        try:
            mx_s = r.get(f"{_PREFIX}hostmax:{host}")
            mx = int(mx_s) if mx_s else 2
            while time.time() < deadline:
                cur = int(r.get(rk) or 0)
                if cur < mx:
                    # optimistic incr; may slightly overshoot under extreme races
                    n = r.incr(rk)
                    r.expire(rk, 3600)
                    if n <= mx:
                        return True
                    r.decr(rk)
                time.sleep(0.05)
            return False
        except Exception:
            pass
    deadline = time.monotonic() + timeout
    while True:
        with _lock:
            cur = _host_inflight[host]
            mx = _host_max[host]
            if cur < mx:
                _host_inflight[host] = cur + 1
                return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def release_host(host: str) -> None:
    r = _redis()
    if r is not None:
        try:
            rk = f"{_PREFIX}hostinflight:{host}"
            n = r.decr(rk)
            if n < 0:
                r.set(rk, "0", ex=3600)
            r.incr(f"{_PREFIX}hostdone:{host}")
            r.expire(f"{_PREFIX}hostdone:{host}", 86400)
            return
        except Exception:
            pass
    with _lock:
        _host_inflight[host] = max(0, _host_inflight[host] - 1)
        _host_total_done[host] += 1


def host_snapshot() -> list[dict[str, Any]]:
    r = _redis()
    if r is not None:
        try:
            hosts: set[str] = set()
            for pattern in (f"{_PREFIX}hostinflight:*", f"{_PREFIX}hostmax:*", f"{_PREFIX}hostdone:*"):
                for full in r.scan_iter(pattern, count=100):
                    hosts.add(full.rsplit(":", 1)[-1])
            out = []
            for h in sorted(hosts):
                out.append({
                    "host": h,
                    "inflight": int(r.get(f"{_PREFIX}hostinflight:{h}") or 0),
                    "max_parallel": int(r.get(f"{_PREFIX}hostmax:{h}") or 2),
                    "completed": int(r.get(f"{_PREFIX}hostdone:{h}") or 0),
                    "backend": "redis",
                })
            if out:
                return out
        except Exception:
            pass
    with _lock:
        keys = set(_host_inflight) | set(_host_max) | set(_host_total_done)
        out = []
        for h in sorted(keys):
            out.append({
                "host": h,
                "inflight": int(_host_inflight.get(h, 0)),
                "max_parallel": int(_host_max[h]),
                "completed": int(_host_total_done.get(h, 0)),
                "backend": "local",
            })
        return out
