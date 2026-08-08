"""Per-indexer / per-host delay, rate limiting, and temporary backoff registry.

Closer to *arr / Cinephage-style indexer health: respect delay, remember failures,
expose a snapshot the interactive UI / system status can show.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any


_lock = threading.Lock()
_last_request: dict[str, float] = defaultdict(float)
_default_delay = 1.0

# key -> unix monotonic deadline until which the key is in backoff
_backoff_until: dict[str, float] = {}
# key -> consecutive failure count
_fail_counts: dict[str, int] = defaultdict(int)
# key -> last error message
_last_error: dict[str, str] = {}


def wait(key: str, delay_seconds: float | None = None) -> None:
    """Block until `delay_seconds` have passed since last call for `key`."""
    delay = _default_delay if delay_seconds is None else max(0.0, float(delay_seconds))
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
    with _lock:
        until = _backoff_until.get(key)
        if until is None:
            return False
        if time.monotonic() >= until:
            _backoff_until.pop(key, None)
            return False
        return True


def remaining_backoff(key: str) -> float:
    with _lock:
        until = _backoff_until.get(key)
        if not until:
            return 0.0
        return max(0.0, until - time.monotonic())


def record_success(key: str) -> None:
    with _lock:
        _fail_counts[key] = 0
        _last_error.pop(key, None)
        _backoff_until.pop(key, None)


def record_failure(key: str, error: str | None = None, *, base_seconds: float = 30.0) -> float:
    """Register a failure; exponential backoff capped at 15 minutes. Returns backoff seconds."""
    with _lock:
        n = _fail_counts[key] + 1
        _fail_counts[key] = n
        if error:
            _last_error[key] = str(error)[:200]
        # 30s, 60s, 120s, ... cap 900s
        seconds = min(900.0, float(base_seconds) * (2 ** min(n - 1, 5)))
        _backoff_until[key] = time.monotonic() + seconds
        return seconds


def clear_backoff(key: str | None = None) -> None:
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
            })
        return {
            "default_delay_s": _default_delay,
            "indexers": indexers,
            "hosts": host_snapshot(),
        }


# ── Host concurrency map ─────────────────────────────────────────────────────
_host_inflight: dict[str, int] = defaultdict(int)
_host_max: dict[str, int] = defaultdict(lambda: 2)  # default max parallel per host
_host_total_done: dict[str, int] = defaultdict(int)


def set_host_max(host: str, max_parallel: int) -> None:
    with _lock:
        _host_max[host] = max(1, int(max_parallel))


def acquire_host(host: str, *, timeout: float = 15.0) -> bool:
    """Block until a concurrency slot is free for host. Returns False on timeout."""
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
    with _lock:
        _host_inflight[host] = max(0, _host_inflight[host] - 1)
        _host_total_done[host] += 1


def host_snapshot() -> list[dict[str, Any]]:
    with _lock:
        keys = set(_host_inflight) | set(_host_max) | set(_host_total_done)
        out = []
        for h in sorted(keys):
            out.append({
                "host": h,
                "inflight": int(_host_inflight.get(h, 0)),
                "max_parallel": int(_host_max[h]),
                "completed": int(_host_total_done.get(h, 0)),
            })
        return out
