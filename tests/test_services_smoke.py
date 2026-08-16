"""Service-layer smoke: imports, pure helpers, no network required."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "app" / "services"


def test_all_services_parse():
    errors = []
    for p in SERVICES.rglob("*.py"):
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as e:
            errors.append(f"{p}:{e.lineno}: {e.msg}")
    assert not errors, errors


def test_import_core_services():
    from app.services import grab, search, organize, interactive_search
    from app.services import dashboard_widgets, schema_migrate

    assert grab is not None
    assert search is not None
    assert organize is not None
    assert interactive_search is not None
    assert dashboard_widgets.widget_continue_watching is not None
    assert dashboard_widgets.widget_continue_reading is not None
    assert schema_migrate.run_schema_migrations is not None


def test_quality_score_basic():
    from app.services.quality import score_release

    result = score_release("Movie.Title.2020.1080p.BluRay.x264")
    assert result is not None
    score = getattr(result, "score", result)
    assert isinstance(score, (int, float)) or (isinstance(result, dict) and "score" in result)


def test_delay_profiles_list():
    from app.services.delay_profiles import list_profiles

    profiles = list_profiles()
    assert isinstance(profiles, list)


def test_schema_migrate_versions_include_comic_progress():
    from app.services.schema_migrate import MIGRATIONS

    versions = [v[0] for v in MIGRATIONS]
    assert "2.0.29" in versions  # is_read / last_page_read
    assert "2.0.30" in versions  # last_read_at


def test_continue_page_map_has_comic():
    from app.services.dashboard_widgets import CONTINUE_PAGE_MAP

    assert CONTINUE_PAGE_MAP.get("comic") == "comics"
    assert CONTINUE_PAGE_MAP.get("movie") == "movies"


def test_naming_helpers_importable():
    from app.services import naming

    assert naming is not None


def test_parse_release_title_basic():
    from app.services.quality import parse_release_title

    parsed = parse_release_title("Some.Show.S01E02.1080p.WEB-DL.x264")
    assert parsed is not None
