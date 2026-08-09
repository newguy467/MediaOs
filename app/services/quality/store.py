"""Load / save quality profiles from the database."""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.models import QualityProfileRecord
from app.services.quality.profiles import (
    CustomFormat,
    QualityProfile,
    default_movie_profile,
    default_tv_profile,
    default_music_profile,
    default_book_profile,
    default_audiobook_profile,
    default_comic_profile,
    default_manga_profile,
    default_comic_digital_profile,
    default_comic_any_profile,
    default_adult_profile,
)

log = logging.getLogger(__name__)


def _cf_to_dict(cf: CustomFormat) -> dict:
    return {
        "name": cf.name,
        "score": cf.score,
        "resolutions": cf.resolutions,
        "sources": cf.sources,
        "codecs": cf.codecs,
        "hdr": cf.hdr,
        "audio": cf.audio,
        "groups": cf.groups,
        "languages": getattr(cf, "languages", []) or [],
        "editions": getattr(cf, "editions", []) or [],
        "title_regex": cf.title_regex,
        "exclude_regex": getattr(cf, "exclude_regex", None),
        "required": cf.required,
        "reject": cf.reject,
        "season_pack": getattr(cf, "season_pack", None),
    }


def _cf_from_dict(d: dict) -> CustomFormat:
    sp = d.get("season_pack", None)
    if sp is not None:
        sp = bool(sp)
    return CustomFormat(
        name=d.get("name") or "unnamed",
        score=int(d.get("score") or 0),
        resolutions=list(d.get("resolutions") or []),
        sources=list(d.get("sources") or []),
        codecs=list(d.get("codecs") or []),
        hdr=list(d.get("hdr") or []),
        audio=list(d.get("audio") or []),
        groups=list(d.get("groups") or []),
        languages=list(d.get("languages") or []),
        editions=list(d.get("editions") or []),
        title_regex=d.get("title_regex"),
        exclude_regex=d.get("exclude_regex"),
        required=bool(d.get("required")),
        reject=bool(d.get("reject")),
        season_pack=sp,
    )


def profile_to_record_fields(profile: QualityProfile, media_type: str) -> dict:
    return {
        "name": profile.name,
        "media_type": media_type,
        "cutoff": profile.cutoff,
        "min_seeders": profile.min_seeders,
        "resolutions_json": json.dumps(profile.resolutions),
        "preferred_sources_json": json.dumps(profile.preferred_sources),
        "custom_formats_json": json.dumps(
            [_cf_to_dict(cf) for cf in profile.custom_formats]
        ),
    }


def record_to_profile(row: QualityProfileRecord) -> QualityProfile:
    try:
        resolutions = json.loads(row.resolutions_json or "[]")
    except json.JSONDecodeError:
        resolutions = ["2160p", "1080p", "720p", "480p"]
    try:
        sources = json.loads(row.preferred_sources_json or "[]")
    except json.JSONDecodeError:
        sources = ["bluray", "webdl", "webrip", "hdtv"]
    try:
        cfs = json.loads(row.custom_formats_json or "[]")
    except json.JSONDecodeError:
        cfs = []
    return QualityProfile(
        name=row.name,
        resolutions=resolutions or ["2160p", "1080p", "720p", "480p"],
        cutoff=row.cutoff or "1080p",
        min_seeders=row.min_seeders or 3,
        preferred_sources=sources or ["bluray", "webdl", "webrip", "hdtv"],
        custom_formats=[_cf_from_dict(c) for c in cfs],
    )


def seed_default_profiles(db: Session) -> None:
    """Insert built-in profiles if the table is empty."""
    if db.query(QualityProfileRecord).count() > 0:
        return
    music = default_movie_profile()
    music.name = "Music - Prefer lossless / higher bitrate"
    music.cutoff = "480p"  # unused for audio; kept for schema
    music.min_seeders = 2
    music.custom_formats = [
        cf for cf in music.custom_formats
        if not cf.reject or cf.name in ("CAM", "TeleSync")
    ]
    for media_type, profile, is_default in [
        ("movie", default_movie_profile(), True),
        ("tv", default_tv_profile(), True),
        ("music", default_music_profile(), True),
        ("book", default_book_profile(), True),
        ("audiobook", default_audiobook_profile(), True),
        ("comic", default_comic_profile(), True),
        ("manga", default_manga_profile(), True),
        ("adult", default_adult_profile(), True),
        ("comic", default_comic_digital_profile(), False),
        ("comic", default_comic_any_profile(), False),
        ("music", music, True),
    ]:
        fields = profile_to_record_fields(profile, media_type)
        row = QualityProfileRecord(**fields, is_default=is_default)
        db.add(row)
    db.commit()
    log.info("Seeded default quality profiles")


def get_default_profile(db: Session, media_type: str) -> QualityProfile:
    row = (
        db.query(QualityProfileRecord)
        .filter(
            QualityProfileRecord.media_type == media_type,
            QualityProfileRecord.is_default.is_(True),
        )
        .first()
    )
    if not row:
        row = (
            db.query(QualityProfileRecord)
            .filter(QualityProfileRecord.media_type == media_type)
            .first()
        )
    if row:
        return record_to_profile(row)
    mapping = {
        "tv": default_tv_profile,
        "music": default_music_profile,
        "book": default_book_profile,
        "books": default_book_profile,
        "audiobook": default_audiobook_profile,
        "audiobooks": default_audiobook_profile,
        "comic": default_comic_profile,
        "comics": default_comic_profile,
        "manga": default_manga_profile,
    }
    fn = mapping.get((media_type or "").lower(), default_movie_profile)
    return fn()


def get_profile_by_name(db: Session, name: str) -> QualityProfile | None:
    row = db.query(QualityProfileRecord).filter(QualityProfileRecord.name == name).first()
    return record_to_profile(row) if row else None


def list_profile_rows(db: Session) -> list[QualityProfileRecord]:
    return db.query(QualityProfileRecord).order_by(QualityProfileRecord.media_type, QualityProfileRecord.name).all()
