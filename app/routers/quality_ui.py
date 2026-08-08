"""Rich quality / custom format UI API."""
from __future__ import annotations

from app.auth import require_permission
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.quality.parser import parse_release_title
from app.services.quality.profiles import attr_base_score, score_release
from app.services.subtitle_profiles import list_profiles as lang_profiles

router = APIRouter(prefix="/quality-ui", tags=["quality-ui"])


@router.get("/factors")
def factors():
    from app.services.quality import profiles as qp

    return {
        "resolution": getattr(qp, "RESOLUTION_SCORE", {}),
        "source": getattr(qp, "SOURCE_SCORE", {}),
        "codec": getattr(qp, "CODEC_SCORE", {}),
        "hdr": getattr(qp, "HDR_SCORE", {}),
        "audio": getattr(qp, "AUDIO_SCORE", {}),
        "groups": dict(getattr(qp, "GROUP_BOOST", {})),
        "edition": getattr(qp, "EDITION_SCORE", {}),
        "factor_families": 50,
        "language_profiles": lang_profiles(),
    }


class ScoreIn(BaseModel):
    title: str
    seeders: int = 0
    size: int = 0
    protocol: str = "torrent"


@router.post("/score")
def score(body: ScoreIn, _perm: list = Depends(require_permission("settings"))):
    parsed = parse_release_title(body.title)
    base = attr_base_score(parsed)
    result = score_release(body.title, seeders=body.seeders, size=body.size, protocol=body.protocol)
    return {
        "base_score": base,
        "total": result.score if hasattr(result, "score") else result.get("score"),
        "accepted": getattr(result, "accepted", True),
        "matched": getattr(result, "matched_formats", None) or getattr(result, "matched", []),
        "parsed": {
            "resolution": getattr(parsed, "resolution", None),
            "source": getattr(parsed, "source", None),
            "codec": getattr(parsed, "codec", None),
            "hdr": getattr(parsed, "hdr", None),
            "audio": getattr(parsed, "audio", None),
            "group": getattr(parsed, "release_group", None) or getattr(parsed, "group", None),
        },
    }


@router.get("/profiles")
def profiles(db: Session = Depends(get_db)):
    try:
        from app.services.quality.store import list_profile_rows, seed_default_profiles

        seed_default_profiles(db)
        rows = list_profile_rows(db)
        return [
            {"id": r.id, "name": r.name, "media_type": r.media_type, "cutoff": r.cutoff}
            for r in rows
        ]
    except Exception:
        try:
            from app.services.quality.profiles import default_movie_profile
            p = default_movie_profile()
            return [{"id": 1, "name": getattr(p, "name", "Default")}]
        except Exception:
            return [{"id": 1, "name": "Default"}]


@router.get("/language-profiles")
def language_profiles():
    return lang_profiles()


class MatrixCellIn(BaseModel):
    name: str
    score: int


class MatrixFamilyIn(BaseModel):
    cells: dict[str, int]
    replace: bool = False


@router.get("/matrix")
def matrix_all(_perm: list = Depends(require_permission("settings"))):
    from app.services.quality.matrix import get_matrix
    return get_matrix()


@router.get("/matrix/{family}")
def matrix_family(family: str, _perm: list = Depends(require_permission("settings"))):
    from app.services.quality.matrix import get_matrix
    from fastapi import HTTPException
    try:
        return get_matrix(family)
    except KeyError:
        raise HTTPException(404, f"Unknown matrix family: {family}")


@router.put("/matrix/{family}/{name}")
def matrix_set_cell(family: str, name: str, body: MatrixCellIn, _perm: list = Depends(require_permission("settings"))):
    from app.services.quality.matrix import set_cell
    from fastapi import HTTPException
    try:
        return set_cell(family, body.name or name, body.score)
    except KeyError:
        raise HTTPException(404, f"Unknown family: {family}")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/matrix/{family}")
def matrix_set_family(family: str, body: MatrixFamilyIn, _perm: list = Depends(require_permission("settings"))):
    from app.services.quality.matrix import set_family
    from fastapi import HTTPException
    try:
        return set_family(family, body.cells, replace=body.replace)
    except KeyError:
        raise HTTPException(404, f"Unknown family: {family}")


@router.delete("/matrix/{family}/{name}")
def matrix_delete_cell(family: str, name: str, _perm: list = Depends(require_permission("settings"))):
    from app.services.quality.matrix import delete_cell
    from fastapi import HTTPException
    try:
        return delete_cell(family, name)
    except KeyError:
        raise HTTPException(404, f"Unknown family: {family}")


@router.post("/matrix/reset")
def matrix_reset(family: str | None = None, _perm: list = Depends(require_permission("settings"))):
    from app.services.quality.matrix import reset_family
    from fastapi import HTTPException
    try:
        return reset_family(family)
    except KeyError:
        raise HTTPException(404, f"Unknown family: {family}")


# ── Live TRaSH Guides sync (v4) ───────────────────────────────────────────
@router.get("/trash/status")
def trash_status(_perm: list = Depends(require_permission("settings"))):
    from app.services.trash_guide_fetch import get_sync_status
    return get_sync_status()


@router.post("/trash/sync")
def trash_sync(url: str | None = None, _perm: list = Depends(require_permission("settings"))):
    from app.services.trash_guide_fetch import fetch_and_apply
    return fetch_and_apply(url=url, use_builtin_fallback=True)
