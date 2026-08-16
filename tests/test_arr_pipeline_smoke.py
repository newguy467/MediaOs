"""P0 regression smoke: *arr validation, quality, organize pure helpers, stream rank."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_arr_validation_connection_failure():
    from app.services.arr_validation import validate_connection

    with patch("httpx.Client") as Client:
        inst = MagicMock()
        inst.__enter__ = MagicMock(return_value=inst)
        inst.__exit__ = MagicMock(return_value=False)
        inst.get.side_effect = Exception("connection refused")
        Client.return_value = inst
        out = validate_connection("http://radarr:7878", "key", "radarr")
        assert out["ok"] is False
        assert out["error"]


def test_arr_validation_connection_ok():
    from app.services.arr_validation import validate_connection

    with patch("httpx.Client") as Client:
        inst = MagicMock()
        inst.__enter__ = MagicMock(return_value=inst)
        inst.__exit__ = MagicMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"version": "5.0.0", "appName": "Radarr"}
        inst.get.return_value = resp
        Client.return_value = inst
        out = validate_connection("http://radarr:7878", "key", "radarr")
        assert out["ok"] is True
        assert out["version"] == "5.0.0"


def test_arr_library_shape_radarr():
    from app.services.arr_validation import validate_library_shape

    with patch("httpx.Client") as Client:
        inst = MagicMock()
        inst.__enter__ = MagicMock(return_value=inst)
        inst.__exit__ = MagicMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = [
            {"id": 1, "title": "Test Movie", "tmdbId": 123, "year": 2020},
            {"id": 2, "title": "Other", "tmdbId": 456, "year": 2021},
        ]
        inst.get.return_value = resp
        Client.return_value = inst
        out = validate_library_shape("http://radarr:7878", "key", "radarr")
        assert out["ok"] is True
        assert out["count"] == 2
        assert out["missing_fields"] == []


def test_score_release_breakdown_present():
    from app.services.quality.profiles import score_release

    r = score_release("Some.Movie.2022.1080p.BluRay.x264-GROUP", seeders=20, size=5_000_000_000)
    assert r.breakdown
    assert "total" in r.breakdown
    assert "total" in r.breakdown


def test_stream_first_ranks_http_above_magnet():
    from app.services.release_enrichment import rank_releases_stream_first

    rows = [
        {"title": "a", "magnet": "magnet:?xt=urn:btih:1"},
        {"title": "b", "download_url": "https://cdn.example/file.mkv"},
    ]
    out = rank_releases_stream_first(rows, force=True)
    assert out[0]["title"] == "b"


def test_subtitle_profiles_kids_and_resolve():
    from app.services.subtitle_profiles import list_profiles, resolve_languages, get_profile

    profiles = list_profiles()
    assert len(profiles) >= 4
    r = resolve_languages(1)
    assert "en" in r["languages"]
    assert r["languages_csv"]
    p = get_profile(3)
    assert "es" in p.languages


def test_path_map_apply():
    from app.services.library_gaps import apply_path_map
    from unittest.mock import MagicMock

    db = MagicMock()
    # no maps
    db.query.return_value.filter.return_value.all.return_value = []
    assert apply_path_map(db, "/data/movies/x") == "/data/movies/x"


def test_backup_flags():
    from app.services.backup import create_backup
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        bad = create_backup(d, include_db=False, include_config=False)
        assert bad.get("ok") is False
        ok = create_backup(d, include_db=False, include_config=True, note="p0")
        assert ok.get("ok") is True
        assert ok.get("include_config") is True
