"""Settings + quality profile CRUD."""
from __future__ import annotations

from app.auth import require_admin, require_permission

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import QualityProfileRecord
from app.services import app_settings as app_settings_service
from app.services.quality.profiles import CustomFormat, QualityProfile
from app.services.quality.store import (
    list_profile_rows,
    profile_to_record_fields,
    record_to_profile,
    seed_default_profiles,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class CustomFormatIn(BaseModel):
    name: str
    score: int = 0
    resolutions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    codecs: list[str] = Field(default_factory=list)
    hdr: list[str] = Field(default_factory=list)
    audio: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    title_regex: str | None = None
    required: bool = False
    reject: bool = False


class ProfileIn(BaseModel):
    name: str
    media_type: str = "movie"  # movie | tv
    is_default: bool = False
    cutoff: str = "1080p"
    min_seeders: int = 3
    resolutions: list[str] = Field(
        default_factory=lambda: ["2160p", "1080p", "720p", "480p"]
    )
    preferred_sources: list[str] = Field(
        default_factory=lambda: ["bluray", "webdl", "webrip", "hdtv"]
    )
    custom_formats: list[CustomFormatIn] = Field(default_factory=list)


class ProfileOut(BaseModel):
    id: int
    name: str
    media_type: str
    is_default: bool
    cutoff: str
    min_seeders: int
    resolutions: list[str]
    preferred_sources: list[str]
    custom_formats: list[CustomFormatIn]


def _row_out(row: QualityProfileRecord) -> ProfileOut:
    p = record_to_profile(row)
    return ProfileOut(
        id=row.id,
        name=row.name,
        media_type=row.media_type,
        is_default=row.is_default,
        cutoff=p.cutoff,
        min_seeders=p.min_seeders,
        resolutions=p.resolutions,
        preferred_sources=p.preferred_sources,
        custom_formats=[
            CustomFormatIn(
                name=cf.name,
                score=cf.score,
                resolutions=cf.resolutions,
                sources=cf.sources,
                codecs=cf.codecs,
                hdr=cf.hdr,
                audio=cf.audio,
                groups=cf.groups,
                title_regex=cf.title_regex,
                required=cf.required,
                reject=cf.reject,
            )
            for cf in p.custom_formats
        ],
    )


@router.get("/profiles", response_model=list[ProfileOut])
def get_profiles(db: Session = Depends(get_db)):
    seed_default_profiles(db)
    return [_row_out(r) for r in list_profile_rows(db)]


@router.get("/profiles/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    row = db.get(QualityProfileRecord, profile_id)
    if not row:
        raise HTTPException(404, "Profile not found")
    return _row_out(row)


@router.post("/profiles", response_model=ProfileOut)
def create_profile(payload: ProfileIn, db: Session = Depends(get_db), _: str = Depends(require_permission("settings"))):
    existing = (
        db.query(QualityProfileRecord)
        .filter(QualityProfileRecord.name == payload.name)
        .first()
    )
    if existing:
        raise HTTPException(409, "Profile name already exists")

    profile = QualityProfile(
        name=payload.name,
        resolutions=payload.resolutions,
        cutoff=payload.cutoff,
        min_seeders=payload.min_seeders,
        preferred_sources=payload.preferred_sources,
        custom_formats=[
            CustomFormat(
                name=cf.name,
                score=cf.score,
                resolutions=cf.resolutions,
                sources=cf.sources,
                codecs=cf.codecs,
                hdr=cf.hdr,
                audio=cf.audio,
                groups=cf.groups,
                title_regex=cf.title_regex,
                required=cf.required,
                reject=cf.reject,
            )
            for cf in payload.custom_formats
        ],
    )
    fields = profile_to_record_fields(profile, payload.media_type)
    if payload.is_default:
        # clear other defaults for this media type
        for r in (
            db.query(QualityProfileRecord)
            .filter(QualityProfileRecord.media_type == payload.media_type)
            .all()
        ):
            r.is_default = False
            db.add(r)

    row = QualityProfileRecord(**fields, is_default=payload.is_default)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_out(row)


@router.put("/profiles/{profile_id}", response_model=ProfileOut)
def update_profile(profile_id: int, payload: ProfileIn, db: Session = Depends(get_db), _: str = Depends(require_permission("settings"))):
    row = db.get(QualityProfileRecord, profile_id)
    if not row:
        raise HTTPException(404, "Profile not found")

    # name uniqueness if changed
    if payload.name != row.name:
        clash = (
            db.query(QualityProfileRecord)
            .filter(QualityProfileRecord.name == payload.name)
            .first()
        )
        if clash:
            raise HTTPException(409, "Profile name already exists")

    profile = QualityProfile(
        name=payload.name,
        resolutions=payload.resolutions,
        cutoff=payload.cutoff,
        min_seeders=payload.min_seeders,
        preferred_sources=payload.preferred_sources,
        custom_formats=[
            CustomFormat(
                name=cf.name,
                score=cf.score,
                resolutions=cf.resolutions,
                sources=cf.sources,
                codecs=cf.codecs,
                hdr=cf.hdr,
                audio=cf.audio,
                groups=cf.groups,
                title_regex=cf.title_regex,
                required=cf.required,
                reject=cf.reject,
            )
            for cf in payload.custom_formats
        ],
    )
    fields = profile_to_record_fields(profile, payload.media_type)
    if payload.is_default:
        for r in (
            db.query(QualityProfileRecord)
            .filter(
                QualityProfileRecord.media_type == payload.media_type,
                QualityProfileRecord.id != profile_id,
            )
            .all()
        ):
            r.is_default = False
            db.add(r)

    for k, v in fields.items():
        setattr(row, k, v)
    row.is_default = payload.is_default
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_out(row)


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: int, db: Session = Depends(get_db), _: str = Depends(require_permission("settings"))):
    row = db.get(QualityProfileRecord, profile_id)
    if not row:
        raise HTTPException(404, "Profile not found")
    if row.is_default:
        raise HTTPException(400, "Cannot delete the default profile — set another default first")
    db.delete(row)
    db.commit()


@router.post("/profiles/{profile_id}/set-default", response_model=ProfileOut)
def set_default(profile_id: int, db: Session = Depends(get_db), _: str = Depends(require_permission("settings"))):
    row = db.get(QualityProfileRecord, profile_id)
    if not row:
        raise HTTPException(404, "Profile not found")
    for r in (
        db.query(QualityProfileRecord)
        .filter(QualityProfileRecord.media_type == row.media_type)
        .all()
    ):
        r.is_default = r.id == profile_id
        db.add(r)
    db.commit()
    db.refresh(row)
    return _row_out(row)



# ── VPN ────────────────────────────────────────────────────────────────────

@router.get("/vpn")
def get_vpn_settings():
    """Current VPN config + live status (safe for non-admin read)."""
    from app.config import settings as cfg
    from app.services.vpn import get_vpn_status

    return {
        "enabled": cfg.vpn_enabled,
        "provider": cfg.vpn_provider,
        "gluetun_url": cfg.vpn_gluetun_url,
        "expected_country": cfg.vpn_expected_country or None,
        "kill_switch": cfg.vpn_kill_switch,
        "public_ip_url": cfg.vpn_public_ip_url,
        "status": get_vpn_status(),
    }


@router.get("/vpn/status")
def vpn_status():
    from app.services.vpn import get_vpn_status

    return get_vpn_status()




@router.get("/vpn/providers")
def vpn_providers():
    from app.services.vpn import list_providers, credentials_summary
    return credentials_summary()


@router.get("/vpn/compose-snippet")
def vpn_compose_snippet():
    from app.services.vpn import gluetun_compose_snippet
    return {"snippet": gluetun_compose_snippet()}

@router.get("/movies")
def get_movie_settings():
    """Radarr-facing movie pipeline settings (read-only from env)."""
    from app.config import settings as cfg

    return {
        "download_mode": cfg.movie_download_mode,
        "prefer_stream_on_search": bool(getattr(cfg, "prefer_stream_on_search", False)),
        "write_strm_sidecar": cfg.movie_write_strm_sidecar,
        "upgrade_enabled": cfg.upgrade_enabled,
        "upgrade_min_score_gap": cfg.upgrade_min_score_gap,
        "upgrade_search_interval_hours": cfg.upgrade_search_interval_hours,
        "library_path": cfg.movies_library_path,
        "min_seeders": cfg.min_seeders,
    }


# ── Editable config groups (Download Clients / Library Storage / System) ────
# Persisted overrides in app_settings; these are the only truly runtime-
# editable settings groups (everything else — quality profiles, indexers —
# already has its own DB table + CRUD above / in routers/indexers.py).

@router.get("/config/{group}")
def get_config_group(group: str, db: Session = Depends(get_db)):
    try:
        return app_settings_service.get_group(db, group)
    except KeyError:
        raise HTTPException(404, f"Unknown settings group: {group}")


@router.put("/config/{group}")
def put_config_group(
    group: str,
    payload: dict,
    db: Session = Depends(get_db),
    admin: str = Depends(require_permission("settings")),
):
    try:
        return app_settings_service.update_group(db, group, payload)
    except KeyError:
        raise HTTPException(404, f"Unknown settings group: {group}")
