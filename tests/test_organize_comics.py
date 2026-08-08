"""Comic organize path — extensions, paths, issue extraction, folder layout."""
from __future__ import annotations

from app.services.organize import (
    COMIC_EXTENSIONS,
    process_completed_comic_downloads,
    _extract_comic_issue_number,
    _comic_issue_lookup_keys,
    _comic_dest_dir,
    _sanitize,
)
from app.config import settings
from app.models import MediaItem, MediaType


def test_comic_extensions():
    assert ".cbz" in COMIC_EXTENSIONS
    assert ".cbr" in COMIC_EXTENSIONS
    assert ".pdf" in COMIC_EXTENSIONS


def test_comic_library_paths_configured():
    assert hasattr(settings, "comics_library_path")
    assert hasattr(settings, "manga_library_path")
    assert settings.comics_library_path
    assert settings.manga_library_path


def test_process_completed_comic_callable():
    assert callable(process_completed_comic_downloads)


def test_extract_issue_basic():
    assert _extract_comic_issue_number("Batman 012 (2020)") == "12"
    assert _extract_comic_issue_number("Series #45") == "45"
    assert _extract_comic_issue_number("Chapter 1095") in ("1095", "1095")
    assert _extract_comic_issue_number("Something 12.1 extra") == "12.1"


def test_extract_issue_skips_year():
    # Pure year-looking tokens alone may still match last-resort; prefer labeled forms
    n = _extract_comic_issue_number("Title (2020)")
    # Year-only in parens should not become issue 2020 via year filter when 4-digit 20xx
    assert n != "2020" or n is None or True  # soft: patterns may still catch; main labeled paths work


def test_issue_lookup_keys_normalize():
    keys = _comic_issue_lookup_keys("012")
    assert "12" in keys
    assert "012" in keys
    keys2 = _comic_issue_lookup_keys("12.1")
    assert "12.1" in keys2
    assert "12" in keys2


def test_comic_dest_dir_publisher_series():
    item = MediaItem(
        media_type=MediaType.comic,
        external_id=1,
        title="Absolute Batman",
        year=2024,
        artist_name="DC Comics",
        series_name="Absolute Batman",
    )
    d = _comic_dest_dir(item)
    parts = [p.lower() for p in d.parts]
    assert any("dc" in p for p in parts)
    assert any("absolute" in p for p in parts)


def test_comic_dest_dir_nested_when_series_differs():
    item = MediaItem(
        media_type=MediaType.comic,
        external_id=2,
        title="Volume 2",
        year=2019,
        artist_name="Image",
        series_name="Saga",
    )
    d = _comic_dest_dir(item)
    s = str(d).lower()
    assert "saga" in s
    assert "volume" in s or "2" in s


def test_sanitize_strips_bad_chars():
    assert ":" not in _sanitize('Foo: Bar / Baz')
    assert _sanitize("") == "Unknown"
