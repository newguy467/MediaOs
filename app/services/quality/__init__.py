from app.services.quality.parser import ParsedRelease, parse_release_title
from app.services.quality.profiles import (
    QualityProfile,
    ScoreResult,
    default_movie_profile,
    default_tv_profile,
    rank_releases,
    score_release,
)

__all__ = [
    "ParsedRelease",
    "parse_release_title",
    "QualityProfile",
    "ScoreResult",
    "default_movie_profile",
    "default_tv_profile",
    "rank_releases",
    "score_release",
]

try:
    from app.services.quality.matrix import apply_overrides as _apply_quality_matrix
    _apply_quality_matrix()
except Exception:
    pass
