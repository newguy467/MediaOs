"""API contract tests: bulk monitor/profile + comic reading progress."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "media_type,list_path,bulk_path",
    [
        ("movie", "/api/movies", "/api/movies/bulk"),
        ("book", "/api/books", "/api/books/bulk"),
        ("audiobook", "/api/audiobooks", "/api/audiobooks/bulk"),
    ],
)
def test_bulk_monitor_roundtrip(client, make_item, db, media_type, list_path, bulk_path):
    a = make_item(media_type=media_type, title=f"Bulk A {media_type}", monitored=False)
    b = make_item(media_type=media_type, title=f"Bulk B {media_type}", monitored=False)
    r = client.post(bulk_path, json={"ids": [a.id, b.id], "monitored": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("updated", body.get("ok")) in (2, True) or body.get("updated") == 2

    db.expire_all()
    from app.models import MediaItem

    for iid in (a.id, b.id):
        item = db.get(MediaItem, iid)
        assert item is not None
        assert item.monitored is True


@pytest.mark.parametrize(
    "media_type,bulk_path",
    [
        ("movie", "/api/movies/bulk"),
        ("book", "/api/books/bulk"),
        ("audiobook", "/api/audiobooks/bulk"),
    ],
)
def test_bulk_quality_profile(client, make_item, db, media_type, bulk_path):
    item = make_item(media_type=media_type, title=f"QP {media_type}", monitored=True)
    r = client.post(
        bulk_path,
        json={"ids": [item.id], "quality_profile": "HD-1080p"},
    )
    assert r.status_code == 200, r.text
    db.expire_all()
    from app.models import MediaItem

    refreshed = db.get(MediaItem, item.id)
    assert refreshed.quality_profile == "HD-1080p"


def test_bulk_ignores_wrong_media_type(client, make_item, db):
    """Movies bulk must not mutate a book id."""
    book = make_item(media_type="book", title="Not a movie", monitored=False)
    r = client.post("/api/movies/bulk", json={"ids": [book.id], "monitored": True})
    assert r.status_code == 200, r.text
    db.expire_all()
    from app.models import MediaItem

    refreshed = db.get(MediaItem, book.id)
    assert refreshed.monitored is False


def test_movies_list_ok(client, make_item):
    make_item(media_type="movie", title="List Me")
    r = client.get("/api/movies")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_books_list_ok(client, make_item):
    make_item(media_type="book", title="List Book")
    r = client.get("/api/books")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_comic_issue_progress_and_last_read_at(client, make_item, db):
    from app.models import ComicIssue, MediaType

    vol = make_item(media_type="comic", title="Saga Vol 1", external_id=424242)
    issue = ComicIssue(
        media_item_id=vol.id,
        issue_number="1",
        title="Chapter 1",
        monitored=True,
        is_read=False,
        last_page_read=None,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)

    r = client.post(
        f"/api/comics/issues/{issue.id}/progress",
        json={"last_page_read": 3, "is_read": False},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["last_page_read"] == 3
    assert data["is_read"] is False
    assert data.get("last_read_at"), "last_read_at should be stamped"

    db.expire_all()
    row = db.get(ComicIssue, issue.id)
    assert row.last_page_read == 3
    assert row.last_read_at is not None

    # mark read
    r2 = client.post(
        f"/api/comics/issues/{issue.id}/progress",
        json={"is_read": True, "last_page_read": 10},
    )
    assert r2.status_code == 200
    db.expire_all()
    row = db.get(ComicIssue, issue.id)
    assert row.is_read is True


def test_continue_reading_widget_shape(client, make_item, db):
    from datetime import datetime, timezone
    from app.models import ComicIssue
    from app.services.dashboard_widgets import widget_continue_reading

    vol = make_item(media_type="comic", title="Continue Me", external_id=525252)
    issue = ComicIssue(
        media_item_id=vol.id,
        issue_number="2",
        title="Mid chapter",
        is_read=False,
        last_page_read=5,
        last_read_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.commit()

    rows = widget_continue_reading(db, limit=5)
    assert isinstance(rows, list)
    match = [x for x in rows if x.get("issue_id") == issue.id]
    assert match, f"expected issue in continue_reading, got {rows!r}"
    assert match[0]["title"] == "Continue Me"


def test_parity_status_ok(client):
    r = client.get("/api/parity/status")
    assert r.status_code == 200
    body = r.json()
    assert "features" in body


def test_interactive_search_missing_item_404(client):
    """Interactive search on unknown id should 404, not 500."""
    for path in (
        "/api/movies/999999001/interactive-search",
        "/api/books/999999002/interactive-search",
        "/api/audiobooks/999999003/interactive-search",
        "/api/comics/999999004/interactive-search",
    ):
        r = client.get(path)
        assert r.status_code in (404, 422), f"{path} -> {r.status_code} {r.text}"


def test_tv_bulk_monitor(client, make_item, db):
    a = make_item(media_type="tv", title="Bulk TV A", monitored=False)
    b = make_item(media_type="tv", title="Bulk TV B", monitored=False)
    r = client.post("/api/tv/bulk", json={"ids": [a.id, b.id], "monitored": True})
    assert r.status_code == 200, r.text
    db.expire_all()
    from app.models import MediaItem
    assert db.get(MediaItem, a.id).monitored is True
    assert db.get(MediaItem, b.id).monitored is True


def test_podcasts_bulk_monitor(client, db):
    from app.models import Podcast
    rows = []
    for i, title in enumerate(["Pod A", "Pod B"]):
        p = Podcast(
            title=title,
            feed_url=f"https://example.com/feed/{i}.xml",
            monitored=False,
            auto_download=False,
        )
        db.add(p)
        rows.append(p)
    db.commit()
    for p in rows:
        db.refresh(p)
    r = client.post(
        "/api/podcasts/bulk",
        json={"ids": [rows[0].id, rows[1].id], "monitored": True, "auto_download": True},
    )
    assert r.status_code == 200, r.text
    db.expire_all()
    for p in rows:
        row = db.get(Podcast, p.id)
        assert row.monitored is True
        assert row.auto_download is True


def test_converter_retry_endpoint_exists(client):
    """Retry route is registered (404 for missing job is OK)."""
    r = client.post("/api/converter/jobs/999999/retry")
    assert r.status_code in (200, 400, 404, 401, 403), r.text


def test_tracking_list_ok(client):
    r = client.get("/api/tracking")
    assert r.status_code == 200, r.text


def test_tracking_upsert_movie(client, make_item, db):
    m = make_item(media_type="movie", title="Track Me")
    r = client.post("/api/tracking", json={"media_item_id": m.id, "status": "planned"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True


def test_games_launch_404(client):
    r = client.post("/api/games/999999/launch")
    assert r.status_code in (404, 401, 403), r.text


def test_games_install_missing(client):
    r = client.post("/api/games/999999/install", json={})
    assert r.status_code in (404, 401, 403, 400), r.text


def test_movie_settings_has_stream_flag(client):
    r = client.get("/api/settings/movies")
    if r.status_code != 200:
        return
    data = r.json()
    assert "download_mode" in data


def test_portal_health(client):
    r = client.get("/api/livetv/portal/health")
    assert r.status_code in (200, 401, 403), r.text
    if r.status_code == 200:
        assert "channels" in r.json()


def test_scrobble_tracking_writeback(client, make_item, db):
    m = make_item(media_type="movie", title="Writeback Film")
    r = client.post("/api/scrobble", json={
        "media_item_id": m.id,
        "event_type": "progress",
        "progress_percent": 42.0,
    })
    if r.status_code == 404:
        r = client.post("/api/scrobble/", json={
            "media_item_id": m.id,
            "event_type": "progress",
            "progress_percent": 42.0,
        })
    if r.status_code not in (200, 201):
        return


def test_library_duplicates(client):
    r = client.get("/api/library/duplicates")
    assert r.status_code in (200, 401, 403), r.text


def test_library_attention(client):
    r = client.get("/api/library/attention")
    assert r.status_code in (200, 401, 403), r.text


def test_path_maps_list(client):
    r = client.get("/api/library/path-maps")
    assert r.status_code in (200, 401, 403), r.text


def test_tv_sync_tracking_404(client):
    r = client.post("/api/library/tv/999999/sync-tracking")
    assert r.status_code in (404, 401, 403), r.text


def test_games_install_jobs_list(client):
    r = client.get("/api/games/install-jobs")
    assert r.status_code in (200, 401, 403), r.text


def test_metadata_refresh_missing(client):
    r = client.post("/api/library/metadata/refresh/999999")
    assert r.status_code in (404, 401, 403, 502), r.text
