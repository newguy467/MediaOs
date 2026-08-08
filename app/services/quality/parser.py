"""
Parse release titles into structured attributes for scoring.

Handles common scene / P2P / anime / private-tracker naming for movies and TV.
Expanded in 2.11 for fidelity closer to Sonarr/Radarr + TRaSH Guides.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedRelease:
    raw: str
    resolution: str | None = None  # 2160p, 1080p, 720p, 480p
    source: str | None = None  # remux, bluray, webdl, webrip, hdtv, dvd, cam, ts
    codec: str | None = None  # av1, x265, x264, xvid
    bit_depth: int | None = None  # 8 / 10
    hdr: list[str] = field(default_factory=list)  # dv, hdr10+, hdr10, hdr, hlg
    audio: list[str] = field(default_factory=list)  # atmos, truehd, dts-hd, ...
    channels: str | None = None  # 7.1, 5.1, 2.0
    languages: list[str] = field(default_factory=list)  # multi, dual, eng, fre, ...
    release_group: str | None = None
    edition: list[str] = field(default_factory=list)  # directors-cut, imax, criterion...
    proper: bool = False
    repack: bool = False
    season: int | None = None
    episode: int | None = None
    season_pack: bool = False
    year: int | None = None
    freeleech: bool = False


# Order matters: more specific patterns first
_RES = [
    (r"\b2160p\b|\b4k\b|\buhd\b", "2160p"),
    (r"\b1080p\b", "1080p"),
    (r"\b720p\b", "720p"),
    (r"\b576p\b", "576p"),
    (r"\b480p\b|\bsd\b", "480p"),
    (r"\b360p\b", "360p"),
]

# remux before plain bluray
_SOURCE = [
    (r"\b(?:bd|uhd)?[\s.\-]?remux\b|\bremux\b", "remux"),
    (r"\bblu-?ray\b|\bbluray\b|\bbdrip\b|\bbd[\s.\-]?r(?:ip)?\b", "bluray"),
    (r"\bweb-?dl\b|\bwebdl\b", "webdl"),
    (r"\bweb-?rip\b|\bwebrip\b", "webrip"),
    (r"\bweb\b", "webrip"),  # plain WEB often means WEBRip-style
    (r"\bhdtv\b|\bpdtv\b|\bdsr\b", "hdtv"),
    (r"\bdvdrip\b|\bdvd\b", "dvd"),
    (r"\bcam\b|\bhdcam\b", "cam"),
    (r"\btelesync\b|\bts\b|\btc\b", "ts"),
]

_CODEC = [
    (r"\bav1\b", "av1"),
    (r"\bx265\b|\bhevc\b|\bh\.?265\b", "x265"),
    (r"\bx264\b|\bh\.?264\b|\bavc\b", "x264"),
    (r"\bxvid\b", "xvid"),
]

_HDR = [
    (r"\bdolby[\s.\-]?vision\b|\bdv\b", "dv"),
    (r"\bhdr10\+\b|\bhdr10plus\b", "hdr10+"),
    (r"\bhdr10\b", "hdr10"),
    (r"\bhdr\b", "hdr"),
    (r"\bhlg\b", "hlg"),
]

_AUDIO = [
    (r"\batmos\b", "atmos"),
    (r"\btruehd\b", "truehd"),
    (r"\bdts-?hd[\s.\-]?ma\b|\bdts-?x\b", "dts-hd"),
    (r"\bdts\b", "dts"),
    (r"\be-?ac-?3\b|\bdd\+\b|\bddplus\b", "eac3"),
    (r"\bac-?3\b|\bdd\b", "ac3"),
    (r"\baac\b", "aac"),
    (r"\bflac\b", "flac"),
    (r"\bopus\b", "opus"),
    (r"\bmp3\b", "mp3"),
]

_EDITION = [
    (r"\bcriterion\b", "criterion"),
    (r"\bdirector'?s?[\s.\-]?cut\b|\bdc\b", "directors-cut"),
    (r"\bextended(?:[\s.\-]?cut)?\b", "extended"),
    (r"\btheatrical\b", "theatrical"),
    (r"\bunrated\b", "unrated"),
    (r"\bimax(?:[\s.\-]?enhanced)?\b", "imax"),
    (r"\bremaster(?:ed)?\b", "remaster"),
    (r"\banniversary\b", "anniversary"),
    (r"\bhybrid\b", "hybrid"),
    (r"\bopen[\s.\-]?matte\b", "open-matte"),
]

_LANG = [
    (r"\bmulti(?:lang|audio|plex)?\b|\bml\b", "multi"),
    (r"\bdual(?:[\s.\-]?audio)?\b", "dual"),
    (r"\beng(?:lish)?\b|\ben\b", "eng"),
    (r"\bfre(?:nch)?\b|\bfr\b|\bvff\b|\bvfq\b", "fre"),
    (r"\bger(?:man)?\b|\bde\b|\bdeu\b", "ger"),
    (r"\bita(?:lian)?\b|\bit\b", "ita"),
    (r"\bspa(?:nish)?\b|\bes\b|\blatino\b", "spa"),
    (r"\bjpn?\b|\bjapanese\b", "jpn"),
    (r"\bkor(?:ean)?\b|\bko\b", "kor"),
    (r"\bchi(?:nese)?\b|\bzh\b|\bcn\b", "chi"),
    (r"\brus(?:sian)?\b|\bru\b", "rus"),
    (r"\bnordic\b|\bsubs?\b", "subs"),
]

_CHANNELS = re.compile(r"\b([765]\.1(?:\.4)?|2\.0)\b", re.I)
_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
_SE = re.compile(r"\b[Ss](\d{1,2})[Ee](\d{1,3})\b")
# Season pack patterns
_SEASON_PACK = [
    re.compile(r"\b[Ss](\d{1,2})\b(?![Ee]\d)", re.I),  # S01 without Exx
    re.compile(r"\bseason[\s.\-_]?(\d{1,2})\b", re.I),
    re.compile(r"\b[Ss](\d{1,2})[\s.\-_]?complete\b", re.I),
    re.compile(r"\bcomplete[\s.\-_]?(?:series|season)?\b", re.I),
    re.compile(r"\b[Ss](\d{1,2})[\s.\-_][Ss](\d{1,2})\b", re.I),  # S01-S03
    re.compile(r"\b[Ss](\d{1,2})[Ee]\d{1,3}[\s.\-_][Ee]\d{1,3}\b", re.I),  # range still single season
]
_PROPER = re.compile(r"\bproper\b", re.I)
_REPACK = re.compile(r"\brepack\b|\brerip\b", re.I)
_BIT10 = re.compile(r"\b10[\s.\-]?bit\b|\bhi10p?\b", re.I)
_BIT8 = re.compile(r"\b8[\s.\-]?bit\b", re.I)
_FREELEECH = re.compile(r"\bfreeleech\b|\bfl\b|\b\/fl\b", re.I)
_GROUP = re.compile(r"[-]([A-Za-z0-9\[\]]{2,})$")


def _first(title: str, patterns: list[tuple[str, str]]) -> str | None:
    for pat, label in patterns:
        if re.search(pat, title, re.I):
            return label
    return None


def _all(title: str, patterns: list[tuple[str, str]]) -> list[str]:
    found: list[str] = []
    for pat, label in patterns:
        if re.search(pat, title, re.I) and label not in found:
            found.append(label)
    return found


def parse_release_title(title: str) -> ParsedRelease:
    raw = title or ""
    t = raw.replace(".", " ").replace("_", " ")

    parsed = ParsedRelease(raw=raw)
    parsed.resolution = _first(t, _RES)
    parsed.source = _first(t, _SOURCE)
    parsed.codec = _first(t, _CODEC)
    parsed.hdr = _all(t, _HDR)
    parsed.audio = _all(t, _AUDIO)
    parsed.edition = _all(t, _EDITION)
    parsed.languages = _all(t, _LANG)

    if _BIT10.search(t):
        parsed.bit_depth = 10
    elif _BIT8.search(t):
        parsed.bit_depth = 8

    ch = _CHANNELS.search(t)
    if ch:
        parsed.channels = ch.group(1)

    se = _SE.search(t)
    if se:
        parsed.season = int(se.group(1))
        parsed.episode = int(se.group(2))
    else:
        # Season pack detection (no single episode)
        for rx in _SEASON_PACK:
            m = rx.search(t)
            if m:
                parsed.season_pack = True
                if m.lastindex and m.group(1) and m.group(1).isdigit():
                    try:
                        parsed.season = int(m.group(1))
                    except (TypeError, ValueError):
                        pass
                break
        # "Complete" alone often means season/series pack
        if re.search(r"\bcomplete\b", t, re.I) and not parsed.episode:
            parsed.season_pack = True

    full_years = _YEAR.findall(t)
    if full_years:
        try:
            # Prefer the last year token (title year usually near quality tags)
            parsed.year = int(full_years[-1])
        except ValueError:
            pass

    parsed.proper = bool(_PROPER.search(t))
    parsed.repack = bool(_REPACK.search(t))
    parsed.freeleech = bool(_FREELEECH.search(t))

    g = _GROUP.search(raw.strip())
    if g:
        parsed.release_group = g.group(1).strip("[]")

    return parsed


def parse_anime_absolute(title: str) -> int | None:
    """Extract absolute episode number common in anime releases (e.g. Show.123.1080p)."""
    # Prefer SxxExx when present
    if re.search(r"[Ss]\d{1,2}[Ee]\d{1,3}", title):
        return None
    # Title - 12 [group]
    m = re.search(r"\s-\s(\d{1,4})\s*[\[\(]", title)
    if m:
        return int(m.group(1))
    m = re.search(r"\[(\d{1,4})\]", title)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 9999:
            return n
    # .123. before quality
    m = re.search(r"(?:^|[\s.\-_])(\d{2,4})(?:[\s.\-_](?:1080|720|2160|480|BD|WEB|HDTV))", title, re.I)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 9999:
            return n
    return None
