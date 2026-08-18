"""
Quality profiles + custom formats (TRaSH-Guides-inspired, simplified).

A CustomFormat is a named rule that matches parsed release attributes (and/or
regex on the raw title) and applies a score delta.

A QualityProfile orders preferred resolutions/sources and sets a cutoff.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.quality.parser import ParsedRelease, parse_release_title


# Dictionarry / TRaSH-inspired base attribute scores
RESOLUTION_SCORE = {
    "2160p": 20000, "4k": 20000, "uhd": 20000,
    "1080p": 10000, "720p": 5000, "576p": 2000, "480p": 1000, "360p": 200,
}
SOURCE_SCORE = {
    "remux": 8000, "bluray": 6000, "blu-ray": 6000, "webdl": 4500, "web-dl": 4500,
    "webrip": 3500, "web-rip": 3500, "hdtv": 2000, "sdtv": 500, "cam": -5000, "ts": -3000,
}
CODEC_SCORE = {
    "av1": 1200, "x265": 800, "hevc": 800, "h265": 800,
    "x264": 400, "h264": 400, "avc": 400, "xvid": -200,
}
HDR_SCORE = {"dv": 1500, "dolby vision": 1500, "hdr10+": 900, "hdr10": 700, "hdr": 500, "hlg": 300}
AUDIO_SCORE = {
    "atmos": 800, "truehd": 700, "dts-hd": 650, "dts-x": 650, "dts": 300,
    "eac3": 200, "ac3": 100, "flac": 400, "aac": 50, "opus": 80,
}
GROUP_BOOST = {
    "framestor": 500, "criterion": 400, "sparrow": 350, "btb": 350,
    "ctrlhd": 300, "monolith": 300, "flux": 250, "ntb": 200, "rarbg": 50,
}



# Expanded release group reputation (Dictionarry-inspired sample)
GROUP_BOOST.update({
    # High-end encode / remux scene & P2P
    "spaaze": 400, "kings": 350, "don": 300, "chd": 280, "hds": 260,
    "eptv": 200, "joy": 180, "megusta": 170, "tigole": 300, "d-zon3": 250,
    "blindspot": 220, "playhd": 150, "ntg": 140, "sparkle": 90, "amy": 120,
    "drizzle": 200, "publichd": 80, "geckos": 210, "sparks": 180, "flux": 250,
    "ntb": 220, "ctrlhd": 300, "monolith": 300, "framestor": 500, "criterion": 450,
    "sparrow": 350, "btb": 350, "koyana": 280, "liber": 260, "bmf": 240,
    "hmax": 200, "wine": 190, "cmrg": 210, "tepes": 200, "successfulcrab": 180,
    "donthes": 170, "egxp": 160, "cielos": 200, "byro": 150, "qman": 140,
    "hone": 220, "kitsune": 180, "samfd": 160, "oft": 150, "raiden": 170,
    "srtb": 140, "d3g": 200, "dopamine": 280, "decibel": 250, "blonde": 160,
    "hype": 130, "rovers": 120, "shortbreard": 150, "edge2020": 140,
    # WEB-oriented
    "ntb": 220, "flux": 250, "successfulcrab": 180, "cmrg": 210, "3c": 100,
    "drones": 90, "joy": 180, "trollhd": 200, "kings": 350,
    # Anime-leaning
    "subsplease": 80, "erai-raws": 70, "horriblesubs": -30, "judas": 100,
    "ember": 90, "asenshi": 85, "goland": 75, "commie": 60,
    # Public / low-rep (penalties)
    "yify": -80, "yts": -60, "rarbg": 40, "ettv": -30, "eztv": -20,
    "1337x": -10, "torrentgalaxy": -15, "tgx": -15, "limetorrents": -25,
    "ion10": -40, "rartv": 20, "vxt": -20, "fgt": 30,
    # Neutral tooling tags
    "radarr": 0, "sonarr": 0, "mediaos": 0, "remux": 50,
})

EDITION_SCORE = {
    "criterion": 800, "directors cut": 400, "director's cut": 400,
    "extended": 250, "theatrical": 50, "unrated": 100, "imax": 350,
    "remaster": 150, "anniversary": 100,
}
HYBRID_SCORE = {"hybrid": 200, "remux": 0}
THREE_D = {"3d": -800, "hsbs": -800, "hou": -800}
FREELEECH_BOOST = 50

FACTOR_COUNT = 50  # documented factor families

def attr_base_score(parsed) -> int:
    s = 0
    res = (getattr(parsed, "resolution", None) or "").lower()
    s += RESOLUTION_SCORE.get(res, 0)
    src = (getattr(parsed, "source", None) or "").lower()
    s += SOURCE_SCORE.get(src, 0)
    codec = (getattr(parsed, "codec", None) or "").lower()
    s += CODEC_SCORE.get(codec, 0)
    for h in getattr(parsed, "hdr", None) or []:
        s += HDR_SCORE.get(str(h).lower(), 0)
    for a in getattr(parsed, "audio", None) or []:
        s += AUDIO_SCORE.get(str(a).lower(), 0)
    group = (getattr(parsed, "release_group", None) or getattr(parsed, "group", None) or "")
    s += GROUP_BOOST.get(str(group).lower(), 0)
    if getattr(parsed, "proper", False):
        s += 100
    if getattr(parsed, "repack", False):
        s += 80
    if getattr(parsed, "freeleech", False):
        s += FREELEECH_BOOST
    if getattr(parsed, "bit_depth", None) == 10:
        s += 40
    if getattr(parsed, "season_pack", False):
        s += 120  # prefer full season packs for TV
    # edition from structured list + raw fallback
    for ed in getattr(parsed, "edition", None) or []:
        key = str(ed).lower().replace("-", " ")
        s += EDITION_SCORE.get(key, 0) or EDITION_SCORE.get(ed, 0)
    raw = (getattr(parsed, "raw", None) or "").lower()
    for k, v in EDITION_SCORE.items():
        if k in raw and not (getattr(parsed, "edition", None) or []):
            s += v
    for k, v in THREE_D.items():
        if k in raw:
            s += v
    if "hybrid" in raw or "hybrid" in (getattr(parsed, "edition", None) or []):
        s += HYBRID_SCORE.get("hybrid", 200)
    # language soft preference: multi/dual slightly preferred for international
    langs = [str(x).lower() for x in (getattr(parsed, "languages", None) or [])]
    if "multi" in langs:
        s += 30
    elif "dual" in langs:
        s += 20
    return s



@dataclass
class CustomFormat:
    name: str
    score: int
    # Non-empty lists are ANDed together; within a list, any match counts.
    resolutions: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    codecs: list[str] = field(default_factory=list)
    hdr: list[str] = field(default_factory=list)
    audio: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)  # release groups
    languages: list[str] = field(default_factory=list)
    editions: list[str] = field(default_factory=list)
    title_regex: str | None = None
    exclude_regex: str | None = None  # if matches → format does not apply
    required: bool = False  # if True and no match → reject release
    reject: bool = False  # if match → reject entirely
    season_pack: bool | None = None  # True = only packs, False = only singles, None = either


@dataclass
class QualityProfile:
    name: str
    # Preferred resolution order (best first)
    resolutions: list[str] = field(
        default_factory=lambda: ["2160p", "1080p", "720p", "480p"]
    )
    # Minimum acceptable resolution (cutoff). Releases below are rejected
    # once we already have cutoff or better on disk (upgrade logic later).
    cutoff: str = "1080p"
    min_seeders: int = 3
    custom_formats: list[CustomFormat] = field(default_factory=list)
    # Prefer these sources when resolution ties
    preferred_sources: list[str] = field(
        default_factory=lambda: ["bluray", "webdl", "webrip", "hdtv"]
    )


# --- Built-in custom formats (starter set) ---

_CF_UPGRADE_HINTS = [
    CustomFormat("x265 / HEVC", 5, codecs=["x265"]),
    CustomFormat("AV1", 8, codecs=["av1"]),
    CustomFormat("10-bit", 3, title_regex=r"\b10[\s.\-]?bit\b|\bhi10p?\b"),
    CustomFormat("Dolby Vision", 15, hdr=["dv"]),
    CustomFormat("HDR10+", 10, hdr=["hdr10+"]),
    CustomFormat("HDR10", 8, hdr=["hdr10", "hdr"]),
    CustomFormat("Atmos", 10, audio=["atmos"]),
    CustomFormat("TrueHD", 6, audio=["truehd"]),
    CustomFormat("DTS-HD", 5, audio=["dts-hd"]),
    CustomFormat("Remux", 25, sources=["remux"]),
    CustomFormat("BluRay", 8, sources=["bluray"]),
    CustomFormat("WEB-DL", 6, sources=["webdl"]),
    CustomFormat("Proper", 3, title_regex=r"\bproper\b"),
    CustomFormat("Repack", 2, title_regex=r"\brepack\b|\brerip\b"),
    CustomFormat("Season Pack", 15, season_pack=True),
    CustomFormat("Multi Audio", 5, languages=["multi"]),
    CustomFormat("Dual Audio", 4, languages=["dual"]),
    CustomFormat("IMAX", 12, editions=["imax"]),
    CustomFormat("Director's Cut", 8, editions=["directors-cut"]),
    CustomFormat("Criterion", 15, editions=["criterion"]),
    CustomFormat("Hybrid", 6, editions=["hybrid"]),
    CustomFormat("Freeleech", 5, title_regex=r"\bfreeleech\b|\b[\/\[]fl[\]\/]?\b"),
]

_CF_REJECTS = [
    CustomFormat("CAM", 0, sources=["cam"], reject=True),
    CustomFormat("TeleSync", 0, sources=["ts"], reject=True),
    CustomFormat("XviD", -50, codecs=["xvid"]),
    CustomFormat("Screen / Watermark", 0, title_regex=r"\b(hc|korsub|watermarked)\b", reject=True),
    CustomFormat("3D", 0, title_regex=r"\b(3d|hsbs|hou)\b", reject=True),
    CustomFormat("LQ / Screener", 0, title_regex=r"\b(screener|r5|tc|workprint)\b", reject=True),
]

_CF_GROUPS_BONUS = [
    # A few well-known groups — expand later via settings UI
    CustomFormat("Group: SPARKS", 5, groups=["SPARKS"]),
    CustomFormat("Group: RARBG", 3, groups=["RARBG"]),
    CustomFormat("Group: FLUX", 5, groups=["FLUX"]),
    CustomFormat("Group: NTb", 5, groups=["NTb"]),
    CustomFormat("Group: CtrlHD", 8, groups=["CtrlHD"]),
]


def default_movie_profile() -> QualityProfile:
    return QualityProfile(
        name="Movies - HD-1080p / prefer WEB+BluRay",
        resolutions=["2160p", "1080p", "720p", "480p"],
        cutoff="1080p",
        min_seeders=3,
        preferred_sources=["bluray", "webdl", "webrip", "hdtv"],
        custom_formats=_CF_UPGRADE_HINTS + _CF_REJECTS + _CF_GROUPS_BONUS,
    )


def default_tv_profile() -> QualityProfile:
    return QualityProfile(
        name="TV - HD-1080p WEB",
        resolutions=["1080p", "720p", "2160p", "480p"],
        cutoff="720p",
        min_seeders=3,
        preferred_sources=["webdl", "webrip", "hdtv", "bluray"],
        custom_formats=_CF_UPGRADE_HINTS + _CF_REJECTS + _CF_GROUPS_BONUS,
    )


@dataclass
class ScoreResult:
    accepted: bool
    score: int
    rejection_reason: str | None = None
    matched_formats: list[str] = field(default_factory=list)
    parsed: ParsedRelease | None = None
    breakdown: dict = field(default_factory=dict)


def _cf_matches(cf: CustomFormat, parsed: ParsedRelease, title: str) -> bool:
    """Match when every non-empty condition group is satisfied.

    Within a list (resolutions, sources, ...), any single hit counts.
    exclude_regex short-circuits to False. season_pack flag is exact.
    """
    if cf.exclude_regex and re.search(cf.exclude_regex, title, re.I):
        return False
    if cf.season_pack is True and not getattr(parsed, "season_pack", False):
        return False
    if cf.season_pack is False and getattr(parsed, "season_pack", False):
        return False

    checks = []
    if cf.resolutions:
        checks.append(parsed.resolution in cf.resolutions)
    if cf.sources:
        checks.append(parsed.source in cf.sources)
    if cf.codecs:
        checks.append(parsed.codec in cf.codecs)
    if cf.hdr:
        checks.append(any(h in (parsed.hdr or []) for h in cf.hdr))
    if cf.audio:
        checks.append(any(a in (parsed.audio or []) for a in cf.audio))
    if cf.groups:
        checks.append(
            (parsed.release_group or "").lower()
            in {g.lower() for g in cf.groups}
        )
    if getattr(cf, "languages", None):
        langs = {x.lower() for x in (parsed.languages or [])}
        checks.append(any(l.lower() in langs for l in cf.languages))
    if getattr(cf, "editions", None):
        eds = {x.lower() for x in (parsed.edition or [])}
        checks.append(any(e.lower() in eds for e in cf.editions))
    if cf.title_regex:
        checks.append(bool(re.search(cf.title_regex, title, re.I)))
    if not checks:
        # season_pack-only or exclude-only formats still count as a match
        return cf.season_pack is not None or bool(cf.exclude_regex)
    return all(checks)


def score_release(
    title: str,
    *,
    seeders: int | None = 0,
    size: int | None = 0,
    protocol: str = "torrent",
    profile: QualityProfile | None = None,
) -> ScoreResult:
    profile = profile or default_movie_profile()
    parsed = parse_release_title(title)
    matched: list[str] = []
    score = attr_base_score(parsed)

    # Base: resolution rank * 100
    res_rank = _RES_RANK.get(parsed.resolution or "", 0)
    score += res_rank * 100

    # Source preference
    if parsed.source and parsed.source in profile.preferred_sources:
        score += (len(profile.preferred_sources) - profile.preferred_sources.index(parsed.source)) * 5

    # Seeders (torrent only)
    if protocol != "usenet":
        score += min(seeders or 0, 100)  # cap seeder influence
        if (seeders or 0) < profile.min_seeders:
            return ScoreResult(
                accepted=False,
                score=score,
                rejection_reason=f"seeders {seeders or 0} < min {profile.min_seeders}",
                parsed=parsed,
                breakdown={"total": score, "rejected": "seeders"},
            )

    # Size soft bonus (avoid tiny fakes / huge trash without quality tags)
    if size:
        score += min(size // (400 * 1024 * 1024), 15)

    # Custom formats
    for cf in profile.custom_formats:
        if _cf_matches(cf, parsed, title):
            if cf.reject:
                return ScoreResult(
                    accepted=False,
                    score=score,
                    rejection_reason=f"rejected by format: {cf.name}",
                    matched_formats=[cf.name],
                    parsed=parsed,
                    breakdown={"total": score, "rejected": "custom_format", "format": cf.name},
                )
            score += cf.score
            matched.append(cf.name)

    for cf in profile.custom_formats:
        if cf.required and cf.name not in matched:
            return ScoreResult(
                accepted=False,
                score=score,
                rejection_reason=f"missing required format: {cf.name}",
                matched_formats=matched,
                parsed=parsed,
                breakdown={"total": score, "rejected": "missing_required_format", "format": cf.name, "matched_formats": matched},
            )

    return ScoreResult(
        accepted=True,
        score=score,
        matched_formats=matched,
        parsed=parsed,
        breakdown={"total": score, "matched_formats": matched},
    )


def rank_releases(
    releases: list[dict],
    profile: QualityProfile | None = None,
) -> list[tuple[dict, ScoreResult]]:
    """Score and sort releases best-first; drop rejected."""
    profile = profile or default_movie_profile()
    ranked: list[tuple[dict, ScoreResult]] = []
    for r in releases:
        result = score_release(
            r.get("title") or "",
            seeders=r.get("seeders"),
            size=r.get("size"),
            protocol=(r.get("protocol") or "torrent").lower(),
            profile=profile,
        )
        if result.accepted and r.get("download_url"):
            ranked.append((r, result))
    ranked.sort(key=lambda x: x[1].score, reverse=True)
    return ranked


def is_resolution_downgrade(current_res: str | None, new_res: str | None) -> bool:
    """True if new resolution is strictly lower than current."""
    cr = resolution_rank(current_res)
    nr = resolution_rank(new_res)
    if cr <= 0 or nr <= 0:
        return False  # unknown — do not treat as downgrade
    return nr < cr


def default_music_profile() -> QualityProfile:
    return QualityProfile(
        name="Music - FLAC / lossless prefer",
        resolutions=[],
        cutoff="",
        min_seeders=2,
        preferred_sources=["web", "cd", "vinyl"],
        custom_formats=[
            CustomFormat("FLAC", 25, title_regex=r"\bflac\b"),
            CustomFormat("Lossless", 20, title_regex=r"\blossless\b"),
            CustomFormat("24bit", 15, title_regex=r"\b24[- ]?bit\b"),
            CustomFormat("Vinyl", 10, title_regex=r"\bvinyl\b|\bvinyl.?rip\b"),
            CustomFormat("MP3 320", 5, title_regex=r"\b320\b"),
            CustomFormat("MP3 V0", 4, title_regex=r"\bv0\b"),
            CustomFormat("Low bitrate", -30, title_regex=r"\b(128|96|64)\s?kbps\b"),
        ],
    )


def default_book_profile() -> QualityProfile:
    return QualityProfile(
        name="Books - ePub preferred",
        resolutions=[],
        cutoff="",
        min_seeders=1,
        preferred_sources=[],
        custom_formats=[
            CustomFormat("ePub", 20, title_regex=r"\bepub\b"),
            CustomFormat("MOBI / AZW", 10, title_regex=r"\b(mobi|azw3?|kindle)\b"),
            CustomFormat("PDF", 5, title_regex=r"\bpdf\b"),
            CustomFormat("Retail", 8, title_regex=r"\bretail\b"),
            CustomFormat("Converted", -5, title_regex=r"\bconverted\b"),
        ],
    )


def default_audiobook_profile() -> QualityProfile:
    return QualityProfile(
        name="Audiobooks - M4B / chaptered",
        resolutions=[],
        cutoff="",
        min_seeders=1,
        preferred_sources=[],
        custom_formats=[
            CustomFormat("M4B", 25, title_regex=r"\bm4b\b"),
            CustomFormat("Chapterized", 15, title_regex=r"\b(chapteri[sz]ed|chapters)\b"),
            CustomFormat("Unabridged", 12, title_regex=r"\bunabridged\b"),
            CustomFormat("Abridged", -20, title_regex=r"\babridged\b"),
            CustomFormat("MP3", 5, title_regex=r"\bmp3\b"),
            CustomFormat("M4A / AAC", 8, title_regex=r"\b(m4a|aac)\b"),
            CustomFormat("128kbps+", 6, title_regex=r"\b(128|160|192|256|320)\s?kbps\b"),
            CustomFormat("64kbps or lower", -25, title_regex=r"\b(32|48|64)\s?kbps\b"),
            CustomFormat("Podcast feed", -10, title_regex=r"\bpodcast\b"),
        ],
    )


def default_comic_profile() -> QualityProfile:
    return QualityProfile(
        name="Comics - CBZ preferred",
        resolutions=[],
        cutoff="",
        min_seeders=1,
        preferred_sources=[],
        custom_formats=[
            CustomFormat("CBZ", 20, title_regex=r"\bcbz\b"),
            CustomFormat("CBR", 12, title_regex=r"\bcbr\b"),
            CustomFormat("Digital", 10, title_regex=r"\bdigital\b"),
            CustomFormat("Scanlation", 5, title_regex=r"\bscanlation\b|\bscan\b"),
            CustomFormat("c2c", 3, title_regex=r"\bc2c\b"),
            CustomFormat("Fixed / repack", 4, title_regex=r"\b(fixed|repack|re.?edit)\b"),
            CustomFormat("HD / 3000px", 8, title_regex=r"\b(hd-|\d{3,4}x\d{3,4}|3000px|4k-scan)\b"),
            CustomFormat("PDF", -8, title_regex=r"\bpdf\b"),
            CustomFormat("Raw", -5, title_regex=r"\braw\b"),
        ],
    )


def default_manga_profile() -> QualityProfile:
    return QualityProfile(
        name="Manga - CBZ / digital",
        resolutions=[],
        cutoff="",
        min_seeders=1,
        preferred_sources=[],
        custom_formats=[
            CustomFormat("CBZ", 20, title_regex=r"\bcbz\b"),
            CustomFormat("CBR", 12, title_regex=r"\bcbr\b"),
            CustomFormat("Digital", 10, title_regex=r"\bdigital\b"),
            CustomFormat("Official", 15, title_regex=r"\b(official|viz|shonen|kodansha)\b"),
            CustomFormat("Scanlation", 5, title_regex=r"\bscanlation\b|\bscan\b"),
            CustomFormat("Webtoon", 8, title_regex=r"\bwebtoon\b"),
            CustomFormat("Raw", -5, title_regex=r"\braw\b"),
        ],
    )


def default_comic_digital_profile() -> QualityProfile:
    return QualityProfile(
        name="Comics - Digital only",
        resolutions=[],
        cutoff="",
        min_seeders=1,
        preferred_sources=[],
        custom_formats=[
            CustomFormat("Digital", 25, title_regex=r"\bdigital\b"),
            CustomFormat("CBZ", 20, title_regex=r"\bcbz\b"),
            CustomFormat("Webrip / web", 10, title_regex=r"\bweb[- ]?(rip|dl)?\b"),
            CustomFormat("HD / 3000px", 12, title_regex=r"\b(hd-|3000px|4k-scan|\d{3,4}x\d{3,4})\b"),
            CustomFormat("c2c scan", -15, title_regex=r"\bc2c\b"),
            CustomFormat("PDF", -25, title_regex=r"\bpdf\b", reject=True),
            CustomFormat("CBR", 5, title_regex=r"\bcbr\b"),
        ],
    )


def default_comic_any_profile() -> QualityProfile:
    return QualityProfile(
        name="Comics - Any format",
        resolutions=[],
        cutoff="",
        min_seeders=0,
        preferred_sources=[],
        custom_formats=[
            CustomFormat("CBZ", 10, title_regex=r"\bcbz\b"),
            CustomFormat("CBR", 8, title_regex=r"\bcbr\b"),
            CustomFormat("PDF", 2, title_regex=r"\bpdf\b"),
        ],
    )



# Resolution rank for cutoff / upgrade decisions
_RES_RANK = {
    "2160p": 4, "4k": 4, "uhd": 4,
    "1080p": 3, "fhd": 3,
    "720p": 2, "hd": 2,
    "480p": 1, "sd": 1, "576p": 1,
}


def resolution_rank(label: str | None) -> int:
    if not label:
        return 0
    s = str(label).lower()
    for k, v in _RES_RANK.items():
        if k in s:
            return v
    return 0


def default_adult_profile() -> QualityProfile:
    """Dedicated Adult / XXX quality profile (not the movie profile)."""
    return QualityProfile(
        name="Adult",
        custom_formats=[
            CustomFormat("2160p / 4K", 20, title_regex=r"\b(2160p|4k|uhd)\b"),
            CustomFormat("1080p", 15, title_regex=r"\b1080p\b"),
            CustomFormat("720p", 8, title_regex=r"\b720p\b"),
            CustomFormat("WEB-DL / WEBRip", 10, title_regex=r"\b(web-?dl|webrip)\b"),
            CustomFormat("BluRay", 12, title_regex=r"\b(bluray|bdrip|bd\s?remux)\b"),
            CustomFormat("HEVC / x265", 6, title_regex=r"\b(hevc|x265|h\.?265)\b"),
            CustomFormat("x264", 3, title_regex=r"\b(x264|h\.?264|avc)\b"),
            CustomFormat("HDR", 5, title_regex=r"\b(hdr10?|dv|dolby\s?vision)\b"),
            CustomFormat("VR", 8, title_regex=r"\b(vr|oculus|quest)\b"),
            CustomFormat("Cam / TS / TC", -100, title_regex=r"\b(cam|telesync|telecine|hdts|hdtc)\b"),
            CustomFormat("XXX / Adult tag", 2, title_regex=r"\b(xxx|adult)\b"),
        ],
    )



# Named packs — pick one and go (TRaSH-inspired, single app)
PRESET_PACKS = {
    "hd": {
        "id": "hd",
        "label": "HD (1080p)",
        "description": "Prefer 1080p WEB/BluRay; solid default for most libraries",
        "preferred_resolutions": ["1080p", "720p"],
        "cutoff_resolution": "1080p",
        "min_score": 0,
    },
    "uhd": {
        "id": "uhd",
        "label": "4K / UHD",
        "description": "Prefer 2160p with HDR/DV scoring boosts",
        "preferred_resolutions": ["2160p", "1080p"],
        "cutoff_resolution": "2160p",
        "min_score": 0,
    },
    "anime": {
        "id": "anime",
        "label": "Anime",
        "description": "Anime-friendly ranking (1080p WEB preferred)",
        "preferred_resolutions": ["1080p", "720p", "2160p"],
        "cutoff_resolution": "1080p",
        "min_score": 0,
    },
    "any": {
        "id": "any",
        "label": "Any quality",
        "description": "No resolution cutoff — grab the best score available",
        "preferred_resolutions": ["2160p", "1080p", "720p", "480p"],
        "cutoff_resolution": None,
        "min_score": -5000,
    },
}


def list_preset_packs() -> list[dict]:
    return list(PRESET_PACKS.values())


def apply_preset_pack(pack_id: str) -> dict:
    """Return a QualityProfile-like dict for the pack (caller persists if needed)."""
    pack = PRESET_PACKS.get(pack_id) or PRESET_PACKS.get(str(pack_id).lower())
    if not pack:
        raise ValueError(f"Unknown preset pack: {pack_id}")
    return {
        "ok": True,
        "pack": pack,
        "profile": {
            "name": pack["label"],
            "preferred_resolutions": list(pack.get("preferred_resolutions") or []),
            "cutoff_resolution": pack.get("cutoff_resolution"),
            "min_score": pack.get("min_score", 0),
            "source": f"preset:{pack['id']}",
        },
    }
