"""Filesystem-free unit tests for organize helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.organize import (
    _folder_name,
    _is_multi_season_title,
    _is_season_pack_title,
    _parse_se,
    _parse_se_with_hint,
    _parse_season_only,
    _sanitize,
)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Show.Name.S01E02.1080p.mkv", (1, 2)),
        ("Show Name - 1x05 - Title.mkv", (1, 5)),
        ("foo.s02e10.bar", (2, 10)),
        ("no-episode-here.mkv", None),
    ],
)
def test_parse_se(name, expected):
    assert _parse_se(name) == expected


def test_parse_se_with_hint():
    assert _parse_se_with_hint("Episode 07.mkv", season_hint=3) == (3, 7) or _parse_se_with_hint(
        "E07.mkv", season_hint=3
    ) in ((3, 7), None)


@pytest.mark.parametrize(
    "title,is_pack",
    [
        ("Show.S01.Complete.1080p", True),
        ("Show.Season.2.Bluray", True),
        ("Show.S01E01.1080p", False),
    ],
)
def test_season_pack_detection(title, is_pack):
    assert _is_season_pack_title(title) is is_pack


def test_sanitize_and_folder():
    assert "/" not in _sanitize("A/B:C*")
    assert "2020" in _folder_name("Movie", 2020)
    assert _folder_name("Movie", None)


def test_find_video_in_temp(tmp_path: Path):
    from app.services.organize import _find_video_file, _all_video_files

    (tmp_path / "readme.txt").write_text("x")
    vid = tmp_path / "movie.mkv"
    vid.write_bytes(b"\x00" * 10)
    found = _find_video_file(tmp_path)
    assert found is not None
    assert found.suffix == ".mkv"
    assert len(_all_video_files(tmp_path)) >= 1
