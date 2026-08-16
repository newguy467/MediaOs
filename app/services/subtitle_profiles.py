"""Subtitle language profiles (Bazarr-style)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LanguageProfile:
    id: int
    name: str
    languages: list[str]  # priority order ISO 639-1
    hearing_impaired: str = "include"  # prefer | include | exclude
    forced: str = "include"


PROFILES = [
    LanguageProfile(1, "English", ["en"], "include", "include"),
    LanguageProfile(2, "English + HI prefer", ["en"], "prefer", "include"),
    LanguageProfile(3, "English + Spanish", ["en", "es"], "include", "include"),
    LanguageProfile(4, "Multi European", ["en", "fr", "de", "es", "it"], "include", "include"),
    LanguageProfile(5, "Nordic", ["en", "sv", "no", "da", "fi"], "include", "include"),
    LanguageProfile(6, "Asian", ["en", "ja", "ko", "zh"], "include", "include"),
    LanguageProfile(7, "Portuguese + Spanish", ["pt", "es", "en"], "include", "include"),
    LanguageProfile(8, "Any", ["en", "es", "fr", "de", "pt", "it", "ja", "ko", "zh", "ru", "pl"], "include", "include"),
]


def list_profiles() -> list[dict]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "languages": p.languages,
            "hearing_impaired": p.hearing_impaired,
            "forced": p.forced,
        }
        for p in PROFILES
    ]


def get_profile(profile_id: int | None) -> LanguageProfile:
    for p in PROFILES:
        if p.id == profile_id:
            return p
    return PROFILES[0]


_default_profile_id: int = 1

def get_default_profile_id() -> int:
    try:
        from app.config import settings
        raw = getattr(settings, "subtitle_default_profile_id", None)
        if raw is not None:
            return int(raw)
    except Exception:
        pass
    return _default_profile_id

def set_default_profile_id(profile_id: int) -> int:
    global _default_profile_id
    _default_profile_id = int(profile_id)
    return _default_profile_id

def resolve_languages(profile_id: int | None = None) -> dict:
    pid = profile_id if profile_id is not None else get_default_profile_id()
    p = get_profile(pid)
    return {
        "profile_id": p.id,
        "name": p.name,
        "languages": list(p.languages),
        "hearing_impaired": p.hearing_impaired,
        "forced": p.forced,
        "languages_csv": ",".join(p.languages),
    }
