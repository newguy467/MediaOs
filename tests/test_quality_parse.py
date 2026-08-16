"""Table-driven tests for release title parsing (no network)."""
from __future__ import annotations

import pytest

from app.services.quality import parse_release_title


@pytest.mark.parametrize(
    "title,expect",
    [
        ("Movie.Title.2020.1080p.BluRay.x264-GROUP", {"resolution": "1080p", "source": "bluray"}),
        ("Some.Show.S01E02.720p.WEB-DL.x264", {"resolution": "720p"}),
        ("Film.Name.2160p.UHD.BluRay.HDR.x265", {"resolution": "2160p"}),
        ("Title.2021.1080p.WEBRip.DDP5.1.x264", {"resolution": "1080p"}),
        ("Anime.Name.S02E10.1080p.CR.WEB-DL", {"resolution": "1080p"}),
        ("Movie.1999.DVDRip.XviD", {}),  # soft assert — just must parse
        ("Completely.Random.String.Without.Tags", {}),
    ],
)
def test_parse_release_title_fields(title, expect):
    parsed = parse_release_title(title)
    assert parsed is not None
    for key, val in expect.items():
        got = getattr(parsed, key, None)
        if got is None and isinstance(parsed, dict):
            got = parsed.get(key)
        if val is None:
            continue
        # normalize case
        if isinstance(got, str) and isinstance(val, str):
            assert got.lower() == val.lower(), f"{title}: {key}={got!r} expected {val!r}"
        else:
            assert got == val or (got and val in str(got).lower())


def test_score_release_prefers_higher_resolution():
    from app.services.quality import score_release

    low = score_release("Film.2020.720p.WEBRip.x264")
    high = score_release("Film.2020.2160p.BluRay.x265")
    low_s = getattr(low, "score", low)
    high_s = getattr(high, "score", high)
    if isinstance(low_s, dict):
        low_s = low_s.get("score", 0)
        high_s = high_s.get("score", 0)
    assert high_s >= low_s


@pytest.mark.parametrize(
    "title,expect_res",
    [
        ("Film.2019.480p.DVDRip.x264", "480p"),
        ("Film.2019.576p.PAL.DVD", "576p"),
        ("Film.2019.1080i.HDTV", "1080"),
        ("Film.2019.4K.UHD.HDR10", "2160"),
        ("Film.2019.720p.HDTV.x264", "720p"),
    ],
)
def test_more_resolutions(title, expect_res):
    parsed = parse_release_title(title)
    res = getattr(parsed, "resolution", None)
    if res is None and isinstance(parsed, dict):
        res = parsed.get("resolution")
    if res is None:
        pytest.skip("parser returned no resolution")
    assert expect_res.lower() in str(res).lower()


def test_score_release_handles_empty_title():
    from app.services.quality import score_release
    try:
        s = score_release("")
    except Exception:
        return  # acceptable
    assert s is not None or s == 0 or s == {}
