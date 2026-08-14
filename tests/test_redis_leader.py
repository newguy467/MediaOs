"""Redis optional path + leader election fallbacks (no Redis required)."""
from __future__ import annotations

import time

from app.services import rate_limit
from app.services import leader
from app.services.redis_client import reset_for_tests


def test_rate_limit_local_backend():
    reset_for_tests()
    rate_limit.clear_backoff()
    key = "test:idx:" + str(time.time())
    assert rate_limit.is_in_backoff(key) is False
    secs = rate_limit.record_failure(key, "boom", base_seconds=1.0)
    assert secs >= 1.0
    assert rate_limit.is_in_backoff(key) is True
    rate_limit.record_success(key)
    assert rate_limit.is_in_backoff(key) is False
    snap = rate_limit.snapshot()
    assert snap.get("backend") in ("local", "redis")


def test_leader_without_redis_is_leader():
    reset_for_tests()
    assert leader.try_become_leader() is True
    assert leader.is_leader() is True
    assert leader.instance_id()


def test_leader_job_wrapper_runs():
    from app.scheduler import _leader_job
    called = []

    def job():
        called.append(1)
        return "ok"

    wrapped = _leader_job(job)
    assert wrapped() == "ok"
    assert called == [1]
