"""Delay profiles — wait before grabbing (prefer better releases).

Sonarr/Radarr-style: prefer usenet vs torrent, optional delay so a better
release can appear, bypass delay when the candidate is already the highest
quality allowed by the profile.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DelayProfile:
    id: int
    name: str
    preferred_protocol: str = "usenet"  # usenet | torrent | any
    usenet_delay_minutes: int = 0
    torrent_delay_minutes: int = 15
    bypass_if_highest: bool = True
    order: int = 1


DEFAULT_PROFILES = [
    DelayProfile(1, "Default", preferred_protocol="any", usenet_delay_minutes=0, torrent_delay_minutes=15),
    DelayProfile(2, "Usenet prefer", preferred_protocol="usenet", usenet_delay_minutes=0, torrent_delay_minutes=60),
    DelayProfile(3, "Torrent prefer", preferred_protocol="torrent", usenet_delay_minutes=30, torrent_delay_minutes=0),
    DelayProfile(4, "No delay", preferred_protocol="any", usenet_delay_minutes=0, torrent_delay_minutes=0, bypass_if_highest=True),
]


def list_profiles() -> list[dict]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "preferredProtocol": p.preferred_protocol,
            "usenetDelay": p.usenet_delay_minutes,
            "torrentDelay": p.torrent_delay_minutes,
            "bypassIfHighestQuality": p.bypass_if_highest,
            "order": p.order,
        }
        for p in DEFAULT_PROFILES
    ]


def get_profile(profile_id: int | None = None) -> DelayProfile:
    if profile_id is None:
        return DEFAULT_PROFILES[0]
    for p in DEFAULT_PROFILES:
        if p.id == profile_id:
            return p
    return DEFAULT_PROFILES[0]


def protocol_preference_bonus(protocol: str, profile: DelayProfile | None = None) -> int:
    """Small score boost when release protocol matches preferred_protocol."""
    p = profile or DEFAULT_PROFILES[0]
    if p.preferred_protocol in ("", "any", None):
        return 0
    proto = (protocol or "torrent").lower()
    if proto in ("nzb",):
        proto = "usenet"
    if proto == p.preferred_protocol:
        return 15
    return 0


def should_delay(
    protocol: str,
    *,
    profile: DelayProfile | None = None,
    is_highest: bool = False,
    profile_id: int | None = None,
) -> int:
    """Return minutes to wait before grab; 0 = grab now."""
    p = profile or get_profile(profile_id)
    if p.bypass_if_highest and is_highest:
        return 0
    proto = (protocol or "torrent").lower()
    if proto in ("usenet", "nzb"):
        return int(p.usenet_delay_minutes or 0)
    return int(p.torrent_delay_minutes or 0)
