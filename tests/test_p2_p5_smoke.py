"""P2–P5 smoke tests."""
from __future__ import annotations

def test_notification_channels_shape():
    from app.services.notifications import channels_status, history, send
    ch = channels_status()
    assert isinstance(ch, list)
    ids = {c["id"] for c in ch}
    assert "discord" in ids and "ntfy" in ids and "gotify" in ids
    out = send("test msg", title="t", channels=["ntfy"])
    assert out["ok"] is True
    assert isinstance(history(5), list)

def test_tracking_statuses_catalog():
    from app.routers.tracking import TRACKING_STATUSES
    ids = {s["id"] for s in TRACKING_STATUSES}
    assert {"planned", "in_progress", "completed", "on_hold", "dropped"} <= ids

def test_subtitle_profiles_list():
    from app.services.subtitle_profiles import list_profiles, resolve_languages
    assert len(list_profiles()) >= 3
    r = resolve_languages(1)
    assert "languages_csv" in r

def test_music_completeness_functions_importable():
    from app.services.music_completeness import album_completeness, hunt_priority_incomplete, missing_track_targets
    assert callable(album_completeness)
    assert callable(hunt_priority_incomplete)
    assert callable(missing_track_targets)
