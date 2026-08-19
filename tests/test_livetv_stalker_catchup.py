"""Live TV: Stalker portal scanning + catch-up/timeshift.

Covers:
  - catchup_url_for_channel() URL building for xtream + stalker sources
  - lazy Stalker link resolution (sync doesn't call create_link; stream
    proxy + health cycle resolve on demand)
  - GET /livetv/catchup/{channel_id} validation (window bounds, future,
    unsupported channel)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


def _mk_source(db, **kw):
    from app.models import LiveTvSource

    defaults = dict(name="Test Source", kind="m3u", enabled=True)
    defaults.update(kw)
    src = LiveTvSource(**defaults)
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


def _mk_channel(db, source, **kw):
    from app.models import LiveTvChannel

    defaults = dict(
        source_id=source.id,
        name="Test Channel",
        stream_url="http://example.invalid/live.ts",
        enabled=True,
    )
    defaults.update(kw)
    ch = LiveTvChannel(**defaults)
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


# ── catchup_url_for_channel ────────────────────────────────────────────────


def test_catchup_url_xtream_builds_timeshift_path(db):
    from app.services.livetv import catchup_url_for_channel

    src = _mk_source(
        db,
        kind="xtream",
        xtream_host="http://portal.example:8080",
        xtream_username="user1",
        xtream_password="pass1",
    )
    ch = _mk_channel(db, src, catchup=True, catchup_days=7, external_id="4242")
    start = datetime(2026, 8, 10, 20, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=30)

    url = catchup_url_for_channel(src, ch, start, end)

    assert url is not None
    assert url == "http://portal.example:8080/timeshift/user1/pass1/30/2026-08-10:20-00/4242.ts"


def test_catchup_url_xtream_missing_stream_id_returns_none(db):
    from app.services.livetv import catchup_url_for_channel

    src = _mk_source(db, kind="xtream", xtream_host="http://portal.example", xtream_username="u")
    ch = _mk_channel(db, src, catchup=True, catchup_days=7, external_id=None)
    start = datetime.now(timezone.utc) - timedelta(hours=1)

    assert catchup_url_for_channel(src, ch, start, start + timedelta(minutes=10)) is None


def test_catchup_url_not_catchup_channel_returns_none(db):
    from app.services.livetv import catchup_url_for_channel

    src = _mk_source(db, kind="xtream", xtream_host="http://portal.example", xtream_username="u")
    ch = _mk_channel(db, src, catchup=False, external_id="1")
    start = datetime.now(timezone.utc) - timedelta(hours=1)

    assert catchup_url_for_channel(src, ch, start, start + timedelta(minutes=10)) is None


def test_catchup_url_stalker_calls_create_timeshift_link(db, monkeypatch):
    from app.services import livetv as livetv_mod

    src = _mk_source(db, kind="stalker", url="http://mag.example/c/", stalker_mac="00:1A:79:AA:BB:CC")
    ch = _mk_channel(db, src, catchup=True, catchup_days=3, external_id="ffmpeg http://mag.example/ch/123")

    calls = {}

    class FakeStalkerClient:
        def __init__(self, portal_url, mac):
            calls["init"] = (portal_url, mac)

        def handshake(self):
            calls["handshake"] = True
            return {"js": {"token": "tok"}}

        def create_timeshift_link(self, cmd, start, duration_min):
            calls["timeshift"] = (cmd, start, duration_min)
            return "http://mag.example/resolved-catchup.ts"

    monkeypatch.setattr("app.clients.stalker.StalkerClient", FakeStalkerClient)

    start = datetime.now(timezone.utc) - timedelta(hours=2)
    end = start + timedelta(minutes=45)
    url = livetv_mod.catchup_url_for_channel(src, ch, start, end)

    assert url == "http://mag.example/resolved-catchup.ts"
    assert calls["init"] == ("http://mag.example/c/", "00:1A:79:AA:BB:CC")
    assert calls["timeshift"][0] == ch.external_id
    assert calls["timeshift"][2] == 45


# ── lazy Stalker resolution ─────────────────────────────────────────────────


def test_sync_stalker_source_does_not_resolve_links(db, monkeypatch):
    """sync should persist a pending marker + cmd, never call create_link."""
    from app.services import livetv as livetv_mod
    from app.models import LiveTvChannel

    src = _mk_source(db, kind="stalker", url="http://mag.example/c/")

    create_link_calls = []

    class FakeStalkerClient:
        def __init__(self, portal_url, mac):
            self.mac = mac or "00:1A:79:11:22:33"

        def handshake(self):
            return {"js": {"token": "tok"}}

        def get_genres(self):
            return [{"id": "1", "title": "All"}]

        def get_ordered_list(self, genre="*", page=1):
            if page > 1:
                return []
            return [
                {"cmd": "ffmpeg http://mag.example/ch/1", "name": "Channel One", "tv_archive": 1, "tv_archive_duration": 5},
                {"cmd": "ffmpeg http://mag.example/ch/2", "name": "Channel Two"},
            ]

        def create_link(self, cmd):
            create_link_calls.append(cmd)
            return "http://mag.example/resolved.ts"

    monkeypatch.setattr("app.clients.stalker.StalkerClient", FakeStalkerClient)

    count = livetv_mod.sync_stalker_source(db, src)

    assert count == 2
    assert create_link_calls == []  # lazy: sync never resolves links

    channels = db.query(LiveTvChannel).filter(LiveTvChannel.source_id == src.id).order_by(LiveTvChannel.id).all()
    assert len(channels) == 2
    assert all(c.stream_url.startswith(livetv_mod.STALKER_PENDING_PREFIX) for c in channels)
    assert channels[0].external_id == "ffmpeg http://mag.example/ch/1"
    assert channels[0].catchup is True
    assert channels[0].catchup_days == 5
    assert channels[1].catchup is False


def test_resolve_stalker_stream_url_calls_create_link(db, monkeypatch):
    from app.services import livetv as livetv_mod

    src = _mk_source(db, kind="stalker", url="http://mag.example/c/", stalker_mac="AA:BB:CC:DD:EE:FF")
    ch = _mk_channel(
        db, src,
        stream_url=livetv_mod.STALKER_PENDING_PREFIX + "ffmpeg http://mag.example/ch/9",
        external_id="ffmpeg http://mag.example/ch/9",
    )

    class FakeStalkerClient:
        def __init__(self, portal_url, mac):
            assert mac == "AA:BB:CC:DD:EE:FF"

        def handshake(self):
            return {}

        def create_link(self, cmd):
            assert cmd == ch.external_id
            return "http://mag.example/live-token-xyz.ts"

    monkeypatch.setattr("app.clients.stalker.StalkerClient", FakeStalkerClient)

    url = livetv_mod.resolve_stalker_stream_url(src, ch)
    assert url == "http://mag.example/live-token-xyz.ts"


def test_health_cycle_resolves_pending_stalker_channel_instead_of_probing_marker(db, monkeypatch):
    """Regression: the health monitor must not probe the raw stalker-pending://
    marker as an HTTP URL (it would always fail and eventually delete/disable
    otherwise-healthy lazily-synced Stalker channels)."""
    from app.models import LiveTvChannel
    from app.services import livetv as livetv_mod

    # run_channel_health_cycle() queries LiveTvChannel with no per-test
    # filter (by design — it's a real background job, not test-scoped), and
    # the `db` fixture's rollback() at teardown can't undo rows _mk_channel()
    # already committed in earlier tests within this session-scoped sqlite
    # file. Clearing the table here only protects against rows committed
    # *before* this point — it can't protect against the zero-touch
    # iptv-org auto-seed's background daemon thread (app/main.py, started
    # on FastAPI startup by any test using the `client` fixture) writing
    # real rows *during* this test's run. conftest.py sets
    # LIVETV_SEED_IPTV_ORG=false to stop that thread from starting at all,
    # but as a second line of defense this test scopes its own assertions
    # to only the channel(s) it creates, so it can't be broken by
    # concurrently-inserted rows regardless of their source.
    db.query(LiveTvChannel).delete()
    db.commit()

    src = _mk_source(db, kind="stalker", url="http://mag.example/c/")
    ch = _mk_channel(
        db, src,
        stream_url=livetv_mod.STALKER_PENDING_PREFIX + "ffmpeg http://mag.example/ch/5",
        external_id="ffmpeg http://mag.example/ch/5",
    )

    probed = {}  # channel_id -> probed url, so we can isolate this test's channel

    def fake_resolve(source, channel):
        return "http://mag.example/resolved-for-health.ts"

    def fake_check(url, timeout=8.0):
        probed[url] = url
        return True, None

    monkeypatch.setattr(livetv_mod, "resolve_stalker_stream_url", fake_resolve)
    monkeypatch.setattr(livetv_mod, "check_channel_stream", fake_check)

    result = livetv_mod.run_channel_health_cycle(db)

    # Assert our channel's resolved URL was probed, without asserting
    # anything about the full set of URLs probed — any other rows present
    # (leaked from elsewhere) are out of scope for this test.
    assert "http://mag.example/resolved-for-health.ts" in probed
    assert result["ok"] >= 1
    db.refresh(ch)
    assert ch.fail_count in (0, None)


# ── router: GET /livetv/catchup/{channel_id} ────────────────────────────────


def test_catchup_endpoint_404_missing_channel(client):
    r = client.get("/api/livetv/catchup/999999", params={
        "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:30:00Z",
    })
    assert r.status_code == 404


def test_catchup_endpoint_400_not_catchup_capable(client, db):
    src = _mk_source(db, kind="xtream", xtream_host="http://p.example", xtream_username="u")
    ch = _mk_channel(db, src, catchup=False)
    r = client.get(f"/api/livetv/catchup/{ch.id}", params={
        "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:30:00Z",
    })
    assert r.status_code == 400


def test_catchup_endpoint_400_future_start(client, db):
    src = _mk_source(db, kind="xtream", xtream_host="http://p.example", xtream_username="u")
    ch = _mk_channel(db, src, catchup=True, catchup_days=7, external_id="1")
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    r = client.get(f"/api/livetv/catchup/{ch.id}", params={
        "start": future, "end": future,
    })
    assert r.status_code == 400


def test_catchup_endpoint_400_outside_window(client, db):
    src = _mk_source(db, kind="xtream", xtream_host="http://p.example", xtream_username="u")
    ch = _mk_channel(db, src, catchup=True, catchup_days=2, external_id="1")
    too_old = datetime.now(timezone.utc) - timedelta(days=10)
    r = client.get(f"/api/livetv/catchup/{ch.id}", params={
        "start": too_old.isoformat(), "end": (too_old + timedelta(minutes=30)).isoformat(),
    })
    assert r.status_code == 400


def test_catchup_endpoint_success(client, db):
    src = _mk_source(db, kind="xtream", xtream_host="http://p.example:80", xtream_username="u", xtream_password="p")
    ch = _mk_channel(db, src, catchup=True, catchup_days=7, external_id="777")
    start = datetime.now(timezone.utc) - timedelta(hours=1)
    end = start + timedelta(minutes=20)
    r = client.get(f"/api/livetv/catchup/{ch.id}", params={
        "start": start.isoformat(), "end": end.isoformat(),
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["url"].startswith("http://p.example:80/timeshift/u/p/")
    assert "/777.ts" in body["url"]


# ── stream proxy resolves pending Stalker links ─────────────────────────────


def test_stream_proxy_resolves_pending_stalker_channel(client, db, monkeypatch):
    from app.services import livetv as livetv_mod

    src = _mk_source(db, kind="stalker", url="http://mag.example/c/")
    ch = _mk_channel(
        db, src,
        stream_url=livetv_mod.STALKER_PENDING_PREFIX + "ffmpeg http://mag.example/ch/3",
        external_id="ffmpeg http://mag.example/ch/3",
    )

    def fake_resolve(source, channel):
        assert channel.id == ch.id
        return "http://mag.example/final.m3u8"

    monkeypatch.setattr(livetv_mod, "resolve_stalker_stream_url", fake_resolve)
    # router imports resolve_stalker_stream_url by name at call time from app.services.livetv
    r = client.get(f"/api/livetv/stream/{ch.id}", follow_redirects=False)
    # .m3u8 URLs are redirected upstream once resolved
    assert r.status_code in (302, 307)
    assert r.headers.get("location") == "http://mag.example/final.m3u8"


def test_stream_proxy_502_when_stalker_resolution_fails(client, db, monkeypatch):
    from app.services import livetv as livetv_mod

    src = _mk_source(db, kind="stalker", url="http://mag.example/c/")
    ch = _mk_channel(
        db, src,
        stream_url=livetv_mod.STALKER_PENDING_PREFIX + "ffmpeg http://mag.example/ch/dead",
        external_id="ffmpeg http://mag.example/ch/dead",
    )

    monkeypatch.setattr(livetv_mod, "resolve_stalker_stream_url", lambda source, channel: None)
    r = client.get(f"/api/livetv/stream/{ch.id}")
    assert r.status_code == 502


# ── source creation / kind validation ───────────────────────────────────────


def test_add_stalker_source_requires_portal_url(client):
    r = client.post("/api/livetv/sources", json={"name": "My Portal", "kind": "stalker"})
    assert r.status_code == 400


def test_add_stalker_source_ok(client):
    r = client.post("/api/livetv/sources", json={
        "name": "My Portal", "kind": "stalker", "url": "http://mag.example/c/", "stalker_mac": "00:1A:79:00:00:01",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "stalker"
    assert body["stalker_mac"] == "00:1A:79:00:00:01"


def test_schema_migrate_includes_stalker_catchup_version():
    from app.services.schema_migrate import MIGRATIONS

    versions = [v[0] for v in MIGRATIONS]
    assert "2.0.31" in versions
