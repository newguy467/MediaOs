from datetime import datetime

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    external_id: int
    title: str
    year: int | None
    overview: str | None
    poster_path: str | None


class MovieCreate(BaseModel):
    external_id: int
    monitored: bool = True
    quality_profile: str | None = None
    search_missing: bool = True


class MovieUpdate(BaseModel):
    monitored: bool | None = None
    quality_profile: str | None = None


class MovieOut(BaseModel):
    id: int
    external_id: int
    title: str
    year: int | None
    overview: str | None = None
    status: str
    monitored: bool
    quality_profile: str | None = None
    quality_score: int | None = None
    file_path: str | None
    poster_path: str | None
    added_at: datetime
    last_searched_at: datetime | None = None

    class Config:
        from_attributes = True


class ReleaseOut(BaseModel):
    title: str
    indexer: str | None
    size: int | None
    seeders: int | None
    download_url: str
    score: int | None = None


# monitor modes (Sonarr-inspired)
# all | future | missing | first | none
class SeriesCreate(BaseModel):
    external_id: int
    monitored: bool = True
    monitor: str = Field(
        default="all",
        description="all | future | missing | first | none",
    )
    quality_profile: str | None = None
    search_missing: bool = True  # kick search after add


class SeriesUpdate(BaseModel):
    monitored: bool | None = None
    quality_profile: str | None = None
    monitor: str | None = None  # re-apply episode monitoring


class EpisodeOut(BaseModel):
    id: int
    season_number: int
    episode_number: int
    title: str | None
    air_date: str | None
    status: str
    monitored: bool
    file_path: str | None
    quality_score: int | None = None

    class Config:
        from_attributes = True


class EpisodeUpdate(BaseModel):
    monitored: bool | None = None


class SeriesOut(BaseModel):
    id: int
    external_id: int
    title: str
    year: int | None
    poster_path: str | None
    monitored: bool
    quality_profile: str | None = None
    series_status: str | None = None  # continuing | ended | upcoming | canceled
    series_name: str | None = None
    status: str | None = None
    file_path: str | None = None
    added_at: datetime
    episode_count: int
    downloaded_count: int
    missing_count: int = 0
    monitor: str | None = None
