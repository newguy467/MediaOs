"""Golden-title tests for quality parser + scoring (2.11 fidelity)."""
from __future__ import annotations

from app.services.quality.parser import parse_release_title, parse_anime_absolute
from app.services.quality.profiles import score_release, default_movie_profile, default_tv_profile


def test_remux_is_first_class_source():
    p = parse_release_title("Movie.2020.2160p.UHD.BluRay.REMUX.HDR.HEVC.Atmos-GROUP")
    assert p.resolution == "2160p"
    assert p.source == "remux"
    assert p.codec == "x265"
    assert "dv" in p.hdr or "hdr" in p.hdr or "hdr10" in p.hdr
    assert "atmos" in p.audio
    assert p.release_group == "GROUP"


def test_webdl_vs_webrip():
    assert parse_release_title("Show.S01E01.1080p.WEB-DL.x264-GROUP").source == "webdl"
    assert parse_release_title("Show.S01E01.1080p.WEBRip.x264-GROUP").source == "webrip"


def test_season_pack_detection():
    p = parse_release_title("Show.Name.S01.1080p.BluRay.x265-GROUP")
    assert p.season_pack is True
    assert p.season == 1
    assert p.episode is None

    p2 = parse_release_title("Show.Name.Season.2.Complete.720p.WEB-GROUP")
    assert p2.season_pack is True


def test_single_episode_not_pack():
    p = parse_release_title("Show.S02E05.1080p.WEB-DL.x264-GROUP")
    assert p.season == 2
    assert p.episode == 5
    assert p.season_pack is False


def test_languages_and_edition():
    p = parse_release_title("Film.2019.Directors.Cut.1080p.BluRay.MULTI.Atmos-GROUP")
    assert "directors-cut" in p.edition
    assert "multi" in p.languages
    assert "atmos" in p.audio


def test_imax_and_10bit():
    p = parse_release_title("Movie.2021.IMAX.1080p.10bit.WEB-DL.x265-GROUP")
    assert "imax" in p.edition
    assert p.bit_depth == 10
    assert p.codec == "x265"


def test_cam_rejected_by_profile():
    r = score_release("Movie.2020.CAM.x264-EVIL", seeders=50, profile=default_movie_profile())
    assert r.accepted is False


def test_remux_scores_higher_than_webdl():
    remux = score_release(
        "Movie.2020.1080p.BluRay.REMUX.AVC.Atmos-GROUP",
        seeders=20,
        size=40 * 1024 ** 3,
        profile=default_movie_profile(),
    )
    web = score_release(
        "Movie.2020.1080p.WEB-DL.x264-GROUP",
        seeders=20,
        size=8 * 1024 ** 3,
        profile=default_movie_profile(),
    )
    assert remux.accepted and web.accepted
    assert remux.score > web.score


def test_season_pack_bonus_on_tv_profile():
    pack = score_release(
        "Show.S01.1080p.WEB-DL.x264-GROUP",
        seeders=10,
        profile=default_tv_profile(),
    )
    single = score_release(
        "Show.S01E01.1080p.WEB-DL.x264-GROUP",
        seeders=10,
        profile=default_tv_profile(),
    )
    assert pack.accepted and single.accepted
    assert pack.score >= single.score


def test_anime_absolute():
    assert parse_anime_absolute("My Show - 12 [Group]") == 12
    assert parse_anime_absolute("Show.S01E05.1080p") is None


def test_freeleech_flag():
    p = parse_release_title("Movie.2020.1080p.WEB-DL.x264-GROUP /FL")
    assert p.freeleech is True
