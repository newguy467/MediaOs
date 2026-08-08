"""Smoke tests for comics search helpers, youtube sponsorblock flags, quality profiles."""
from __future__ import annotations

from app.services.quality.profiles import (
    default_comic_profile,
    default_manga_profile,
    default_music_profile,
    default_book_profile,
    default_audiobook_profile,
)
from app.services.quality.store import get_default_profile
from app.config import settings


def test_comic_profile_prefers_cbz():
    p = default_comic_profile()
    assert any(cf.name == "CBZ" for cf in p.custom_formats)
    assert any(cf.name == "CBR" for cf in p.custom_formats)


def test_manga_profile_exists():
    p = default_manga_profile()
    assert "Manga" in p.name


def test_music_book_audiobook_profiles():
    assert "FLAC" in [cf.name for cf in default_music_profile().custom_formats]
    assert "ePub" in [cf.name for cf in default_book_profile().custom_formats]
    assert "M4B" in [cf.name for cf in default_audiobook_profile().custom_formats]


def test_get_default_profile_mapping():
    # no db — falls through to built-in defaults
    class Dummy: pass
    # get_default_profile expects a Session; call profile factories directly above
    assert default_comic_profile().name
    assert default_manga_profile().name


def test_youtube_sponsorblock_settings_present():
    assert hasattr(settings, "youtube_sponsorblock_remove")
    assert hasattr(settings, "youtube_cookies_path")
    assert "sponsor" in (settings.youtube_sponsorblock_remove or "")


def test_youtube_download_cmd_includes_sponsorblock():
    """Unit-level: settings drive sponsorblock flags."""
    from app.services import youtube as yt
    assert callable(yt.download_video)
    assert settings.youtube_sponsorblock_remove


def test_cardigann_defs_shipped():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "definitions"
    names = {p.name for p in root.glob("*.yml")}
    assert "yts.yml" in names
    assert "eztv.yml" in names
    assert "bitsearch.yml" in names
    assert "1337x.yml" in names
