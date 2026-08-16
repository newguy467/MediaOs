import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MediaType(str, enum.Enum):
    movie = "movie"
    tv = "tv"
    music = "music"  # artist / album (album-level rows; tracks later)
    book = "book"
    audiobook = "audiobook"
    comic = "comic"
    manga = "manga"
    adult = "adult"  # Whisparr-style adult movies (passcode gated)
    game = "game"    # Questarr-inspired video games module (MediaOS v2)
    board_game = "board_game"  # Yamtrack-style board games
    podcast = "podcast"


class ItemStatus(str, enum.Enum):
    wanted = "wanted"
    downloading = "downloading"
    downloaded = "downloaded"
    missing = "missing"
    failed = "failed"


class MediaItem(Base):
    """
    One row per tracked library entity.
    - movie / book / audiobook: the whole work
    - tv: the series (episodes in Episode)
    - music: typically an album (artist in title or metadata JSON later)
    """

    __tablename__ = "media_items"
    __table_args__ = (UniqueConstraint("media_type", "external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType), default=MediaType.movie, nullable=False
    )

    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    external_source: Mapped[str | None] = mapped_column(
        String, nullable=True, default="tmdb"
    )  # tmdb | tvdb | musicbrainz | openlibrary | audnexus
    # Provider IDs for strong webhook / library matching (v2.0.4+)
    imdb_id: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. tt1234567
    tvdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON blob of extra IDs
    title: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overview: Mapped[str | None] = mapped_column(String, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String, nullable=True)

    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus), default=ItemStatus.wanted
    )
    quality_profile: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # profile name key
    # JSON list e.g. ["1080p","2160p"] — interactive search preference
    desired_qualities: Mapped[str | None] = mapped_column(String, nullable=True)
    # Sonarr-style: all | future | missing | first | none
    monitor_mode: Mapped[str | None] = mapped_column(String, nullable=True, default="all")
    # Lidarr: artist name for music albums
    artist_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # TV show airing status from TMDb/TVDb: continuing | ended | upcoming | canceled
    series_status: Mapped[str | None] = mapped_column(String, nullable=True)
    # Series/saga name for books, audiobooks, comic volumes
    series_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Comma-separated tags, substring/OR-matched (same convention as
    # LiveTvVirtualChannel.genre_filter). Used today by music smart playlists
    # (source=library_genre / library_mood); generic enough for other media
    # types to adopt later without a schema change.
    genre: Mapped[str | None] = mapped_column(String, nullable=True)
    mood: Mapped[str | None] = mapped_column(String, nullable=True)

    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_searched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Optional link into a tracked movie collection/saga (movies only)
    collection_id: Mapped[int | None] = mapped_column(
        ForeignKey("collections.id"), nullable=True
    )

    downloads: Mapped[list["Download"]] = relationship(
        back_populates="media_item", cascade="all, delete-orphan"
    )
    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )
    collection: Mapped["Collection | None"] = relationship(back_populates="movies")


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (
        UniqueConstraint("media_item_id", "season_number", "episode_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"))

    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    absolute_episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    air_date: Mapped[str | None] = mapped_column(String, nullable=True)

    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus), default=ItemStatus.wanted
    )
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_searched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    series: Mapped["MediaItem"] = relationship(back_populates="episodes")
    downloads: Mapped[list["Download"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan"
    )


class Download(Base):
    __tablename__ = "downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_item_id: Mapped[int | None] = mapped_column(ForeignKey("media_items.id"), nullable=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), nullable=True)
    episode_id: Mapped[int | None] = mapped_column(
        ForeignKey("episodes.id"), nullable=True
    )

    indexer: Mapped[str | None] = mapped_column(String, nullable=True)
    release_title: Mapped[str] = mapped_column(String, nullable=False)
    download_url: Mapped[str] = mapped_column(String, nullable=False)
    torrent_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matched_formats: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, default="grabbed")
    strikes: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    media_item: Mapped["MediaItem"] = relationship(back_populates="downloads")
    episode: Mapped["Episode | None"] = relationship(back_populates="downloads")


class Blocklist(Base):
    """Permanently skip a release title (or hash) after failure / user reject."""

    __tablename__ = "blocklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    release_title: Mapped[str] = mapped_column(String, nullable=False, index=True)
    torrent_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    media_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_items.id"), nullable=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class Activity(Base):
    """Append-only event log for the Activity page."""

    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event: Mapped[str] = mapped_column(String, nullable=False)  # grabbed|organized|failed|blocked|searched
    message: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String, nullable=True)
    media_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    release_title: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class QualityProfileRecord(Base):
    """Persisted quality profile (editable via API / settings UI)."""

    __tablename__ = "quality_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    media_type: Mapped[str] = mapped_column(String, nullable=False, default="movie")  # movie|tv|music|...
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    cutoff: Mapped[str] = mapped_column(String, default="1080p")
    min_seeders: Mapped[int] = mapped_column(Integer, default=3)
    # JSON-encoded lists
    resolutions_json: Mapped[str] = mapped_column(Text, default='["2160p","1080p","720p","480p"]')
    preferred_sources_json: Mapped[str] = mapped_column(
        Text, default='["bluray","webdl","webrip","hdtv"]'
    )
    custom_formats_json: Mapped[str] = mapped_column(Text, default="[]")
    # bobarr-inspired: best_only | keep_all_matching | keep_until_cutoff | keep_n_best
    retention_policy: Mapped[str] = mapped_column(String, default="best_only")
    keep_n: Mapped[int] = mapped_column(Integer, default=2)  # used when retention_policy == keep_n_best
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class User(Base):
    """Multi-user accounts stored in DB (optional; env admin still works)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default=UserRole.user.value)
    # JSON list of permission keys. Null = role defaults (admin=all, user=view+request).
    permissions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthSession(Base):
    """DB-backed auth sessions (survive restarts / multi-worker)."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_token: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    refresh_token: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, default="user")
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    ip: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class LiveTvSource(Base):
    """IPTV source: M3U URL or Xtream Codes credentials."""

    __tablename__ = "livetv_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, default="m3u")  # m3u | xtream
    url: Mapped[str | None] = mapped_column(String, nullable=True)  # m3u url
    xtream_host: Mapped[str | None] = mapped_column(String, nullable=True)
    xtream_username: Mapped[str | None] = mapped_column(String, nullable=True)
    xtream_password: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel_count: Mapped[int] = mapped_column(Integer, default=0)
    epg_url: Mapped[str | None] = mapped_column(String, nullable=True)  # XMLTV EPG URL
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class LiveTvChannel(Base):
    __tablename__ = "livetv_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("livetv_sources.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    group_title: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    logo: Mapped[str | None] = mapped_column(String, nullable=True)
    stream_url: Mapped[str] = mapped_column(Text, nullable=False)
    tvg_id: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    epg_tvg_id: Mapped[str | None] = mapped_column(String, nullable=True)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Health-cycle bookkeeping (used by run_channel_health_cycle to auto-delete/disable
    # channels whose stream has been dead for longer than `livetv_offline_hours`).
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class LiveTvVirtualChannel(Base):
    """A 24/7 'channel' auto-scheduled from the user's own media_items/episodes
    library (the "your library becomes TV channels" feature) rather than a
    real IPTV stream. Rendered into the same unified M3U/XMLTV export as
    LiveTvChannel so Jellyfin sees one lineup.
    """

    __tablename__ = "livetv_virtual_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    group_title: Mapped[str | None] = mapped_column(String, nullable=True, default="Personal Media")
    logo: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Content source. media_types: JSON list subset of ["movie","tv"].
    # media_item_ids: JSON list of explicit MediaItem ids to restrict to (empty = whole
    # library matching media_types/genre/title filters below).
    media_types: Mapped[str] = mapped_column(String, default='["movie"]')
    media_item_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list[int] or null
    genre_filter: Mapped[str | None] = mapped_column(String, nullable=True)  # substring match, comma list = OR
    title_filter: Mapped[str | None] = mapped_column(String, nullable=True)  # substring match on title
    year_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Scheduling rules
    randomize: Mapped[bool] = mapped_column(Boolean, default=True)
    repeat_protection_days: Mapped[int] = mapped_column(Integer, default=7)
    prime_time_movies: Mapped[bool] = mapped_column(Boolean, default=False)

    # Stream engine bookkeeping
    schedule_filled_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stream_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stream_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stream_status: Mapped[str] = mapped_column(String, default="stopped")  # stopped | starting | running | error
    stream_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class LiveTvVirtualScheduleItem(Base):
    """One entry in a virtual channel's generated continuous schedule."""

    __tablename__ = "livetv_virtual_schedule_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    virtual_channel_id: Mapped[int] = mapped_column(
        ForeignKey("livetv_virtual_channels.id"), nullable=False, index=True
    )
    media_item_id: Mapped[int | None] = mapped_column(ForeignKey("media_items.id"), nullable=True)
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episodes.id"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SmartList(Base):
    """Rule-based auto-add from TMDb lists / discover queries."""

    __tablename__ = "smart_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    media_type: Mapped[str] = mapped_column(String, default="movie")  # movie | tv
    # tmdb_list | tmdb_discover
    source: Mapped[str] = mapped_column(String, default="tmdb_list")
    # For tmdb_list: numeric list id as string. For discover: JSON query params.
    source_ref: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    min_vote_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_profile: Mapped[str | None] = mapped_column(String, nullable=True)
    series_type: Mapped[str | None] = mapped_column(String, nullable=True)  # standard | anime | daily
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_added_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MusicSmartlist(Base):
    """A saved, live-updating *filter over the existing local music library*.

    Deliberately a separate model from SmartList: SmartList's whole shape
    (source_ref against an external API, min_year/max_year/min_vote_average,
    last_added_count) is built around discovering and adding *new* items from
    TMDb/Trakt/IMDb. A music smart playlist does the opposite — it queries
    MediaItem/MusicTrack rows already in the library and re-evaluates on
    every read, so there's nothing to "run" or "add"; see
    app/services/music_smartlists.py `resolve_smartlist()`.
    """

    __tablename__ = "music_smartlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # library_genre | library_mood | library_recent | library_most_played
    source: Mapped[str] = mapped_column(String, default="library_genre")
    # Substring match against MediaItem.genre / .mood, comma list = OR
    # (same convention as LiveTvVirtualChannel.genre_filter).
    genre_filter: Mapped[str | None] = mapped_column(String, nullable=True)
    mood_filter: Mapped[str | None] = mapped_column(String, nullable=True)
    # library_recent: only include albums added in the last N days
    added_within_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # library_most_played: only include tracks with at least this many plays
    min_play_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_limit: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Indexer(Base):
    """Built-in Torznab/Newznab indexer (Prowlarr replacement path)."""

    __tablename__ = "indexers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)  # base, e.g. https://indexer/api
    api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    credentials_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # private tracker login/cookies
    kind: Mapped[str] = mapped_column(String, default="torznab")  # torznab | newznab | cardigann
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    categories: Mapped[str | None] = mapped_column(String, nullable=True)  # comma ids
    use_flaresolverr: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=25)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Collection(Base):
    """TMDb movie collection / saga (e.g. MCU, Bond). Beyond MediaOs scope."""

    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    overview: Mapped[str | None] = mapped_column(String, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String, nullable=True)
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    # Total parts known from TMDb at last refresh (owned = len(movies) in library)
    total_parts: Mapped[int] = mapped_column(Integer, default=0)
    quality_profile: Mapped[str | None] = mapped_column(String, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    movies: Mapped[list["MediaItem"]] = relationship(back_populates="collection")


class Podcast(Base):
    """Tracked RSS podcast feed. Zero arr-ecosystem apps cover this."""

    __tablename__ = "podcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image: Mapped[str | None] = mapped_column(String, nullable=True)

    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    # Auto-download new episodes as they appear in the feed
    auto_download: Mapped[bool] = mapped_column(Boolean, default=True)
    # Only auto-download episodes published after this many days ago (0 = all)
    download_window_days: Mapped[int] = mapped_column(Integer, default=0)

    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    episode_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    episodes: Mapped[list["PodcastEpisode"]] = relationship(
        back_populates="podcast", cascade="all, delete-orphan"
    )


class PodcastEpisode(Base):
    __tablename__ = "podcast_episodes"
    __table_args__ = (UniqueConstraint("podcast_id", "guid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    podcast_id: Mapped[int] = mapped_column(ForeignKey("podcasts.id"), nullable=False)

    guid: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    audio_url: Mapped[str] = mapped_column(Text, nullable=False)
    pub_date: Mapped[str | None] = mapped_column(String, nullable=True)  # ISO string, best-effort
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.wanted)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chapters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    podcast: Mapped["Podcast"] = relationship(back_populates="episodes")


class RequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    denied = "denied"
    fulfilled = "fulfilled"


class MediaRequest(Base):
    """Native request queue — user requests, admin approves.
    Replaces Overseerr/Jellyseerr; no separate app needed."""

    __tablename__ = "media_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_type: Mapped[str] = mapped_column(String, nullable=False)  # movie|tv|music|book|audiobook
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    external_source: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overview: Mapped[str | None] = mapped_column(String, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String, nullable=True)
    artist_name: Mapped[str | None] = mapped_column(String, nullable=True)  # music only

    requested_by: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default=RequestStatus.pending.value)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_item_id: Mapped[int | None] = mapped_column(ForeignKey("media_items.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppSetting(Base):
    """Runtime-editable override for a Settings field (app/config.py).
    Absence of a row means "use the .env / default value". A row here
    always wins over the environment. Lets Settings pages persist changes
    without a container restart or editing .env by hand."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)  # matches a Settings field name
    value: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class YouTubeChannel(Base):
    __tablename__ = "youtube_channels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    playlist_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    feed_url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(String, nullable=True)
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_download: Mapped[bool] = mapped_column(Boolean, default=True)
    quality: Mapped[str | None] = mapped_column(String, nullable=True, default="best[height<=1080]")
    download_window_days: Mapped[int] = mapped_column(Integer, default=0)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    video_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    videos: Mapped[list["YouTubeVideo"]] = relationship(back_populates="channel", cascade="all, delete-orphan")

class YouTubeVideo(Base):
    __tablename__ = "youtube_videos"
    __table_args__ = (UniqueConstraint("channel_id_fk", "video_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id_fk: Mapped[int] = mapped_column(ForeignKey("youtube_channels.id"), nullable=False)
    video_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    published_at: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.wanted)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    channel: Mapped["YouTubeChannel"] = relationship(back_populates="videos")


class ComicIssue(Base):
    """Individual issue/chapter under a comic or manga volume (MediaItem)."""

    __tablename__ = "comic_issues"
    __table_args__ = (
        UniqueConstraint("media_item_id", "issue_number", "external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"), nullable=False, index=True)
    external_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_source: Mapped[str | None] = mapped_column(String, nullable=True)
    issue_number: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_date: Mapped[str | None] = mapped_column(String, nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String, nullable=True)
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.wanted)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    last_page_read: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    volume: Mapped["MediaItem"] = relationship()


class ConvertPreset(Base):
    """Tdarr-style conversion preset (codec/container/quality)."""

    __tablename__ = "convert_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    # video
    video_codec: Mapped[str] = mapped_column(String, default="libx264")  # libx264|libx265|libsvtav1|copy
    video_crf: Mapped[int] = mapped_column(Integer, default=23)
    video_preset: Mapped[str] = mapped_column(String, default="medium")  # ultrafast…veryslow / av1 presets
    audio_codec: Mapped[str] = mapped_column(String, default="aac")  # aac|libopus|copy|ac3
    audio_bitrate: Mapped[str] = mapped_column(String, default="160k")
    container: Mapped[str] = mapped_column(String, default="mp4")  # mp4|mkv|webm
    # filters
    only_codecs: Mapped[str | None] = mapped_column(String, nullable=True)  # comma list: hevc,vc1 — convert only if match
    skip_codecs: Mapped[str | None] = mapped_column(String, nullable=True)  # skip if already these
    max_height: Mapped[int | None] = mapped_column(Integer, nullable=True)  # e.g. 1080
    # output
    output_mode: Mapped[str] = mapped_column(String, default="new_file")  # new_file | replace | rename_old
    output_suffix: Mapped[str] = mapped_column(String, default=".converted")
    backup_suffix: Mapped[str] = mapped_column(String, default=".original")  # used by rename_old
    # Hardware encode: none | cuda | qsv | vaapi | d3d11va
    hwaccel: Mapped[str | None] = mapped_column(String, nullable=True, default="none")
    # Extra ffmpeg args (advanced), e.g. -rc constqp
    extra_args: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ConvertJob(Base):
    """Single file conversion job in the queue."""

    __tablename__ = "convert_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    preset_id: Mapped[int | None] = mapped_column(ForeignKey("convert_presets.id"), nullable=True)
    preset_name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)  # queued|running|done|failed|cancelled
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_codec: Mapped[str | None] = mapped_column(String, nullable=True)
    source_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    health_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    health_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    preset: Mapped["ConvertPreset | None"] = relationship()



class ConvertWatchFolder(Base):
    """Per-folder converter mapping: path → preset (Tdarr-style libraries)."""

    __tablename__ = "convert_watch_folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    preset_id: Mapped[int | None] = mapped_column(ForeignKey("convert_presets.id"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    recursive: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_queued: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    preset: Mapped["ConvertPreset | None"] = relationship()


class MusicTrack(Base):
    """Track-level music row (Lidarr-style) under an album MediaItem."""

    __tablename__ = "music_tracks"
    __table_args__ = (UniqueConstraint("media_item_id", "track_number", "disc_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"), nullable=False, index=True)
    recording_mbid: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    track_number: Mapped[int] = mapped_column(Integer, default=1)
    disc_number: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.wanted)
    # Local play counter, incremented via POST /api/music/track/{id}/played —
    # the frontend calls this from the same ~50%-played threshold that
    # already drives scrobble-out (store.js `_scrobbleOut`). Powers the
    # library_most_played smart playlist source; independent of Last.fm/
    # ListenBrainz, which only track plays remotely and only when enabled.
    play_count: Mapped[int] = mapped_column(Integer, default=0)

    album: Mapped["MediaItem"] = relationship()


# ── Overhaul 3.7: comics pull-list / story arcs / stream files / multi-quality ─

class ComicPullList(Base):
    """Weekly comic pull-list entry (Mylar-inspired)."""
    __tablename__ = "comic_pull_list"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    series_name: Mapped[str] = mapped_column(String, nullable=False)
    issue_number: Mapped[str | None] = mapped_column(String, nullable=True)
    publisher: Mapped[str | None] = mapped_column(String, nullable=True)
    release_date: Mapped[str | None] = mapped_column(String, nullable=True)  # YYYY-MM-DD
    comicvine_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_item_id: Mapped[int | None] = mapped_column(ForeignKey("media_items.id"), nullable=True)
    watched: Mapped[bool] = mapped_column(Boolean, default=True)
    grabbed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ComicStoryArc(Base):
    """Story arc spanning multiple issues (Mylar-inspired)."""
    __tablename__ = "comic_story_arcs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    comicvine_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    issue_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ComicStoryArcIssue(Base):
    __tablename__ = "comic_story_arc_issues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    arc_id: Mapped[int] = mapped_column(ForeignKey("comic_story_arcs.id"), nullable=False)
    series_name: Mapped[str] = mapped_column(String, nullable=False)
    issue_number: Mapped[str | None] = mapped_column(String, nullable=True)
    reading_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_item_id: Mapped[int | None] = mapped_column(ForeignKey("media_items.id"), nullable=True)
    comic_issue_id: Mapped[int | None] = mapped_column(ForeignKey("comic_issues.id"), nullable=True)


class StreamLink(Base):
    """Cinephage-style .strm / stream-without-download pointer."""
    __tablename__ = "stream_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_item_id: Mapped[int | None] = mapped_column(ForeignKey("media_items.id"), nullable=True)
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episodes.id"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    stream_url: Mapped[str] = mapped_column(Text, nullable=False)
    strm_path: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ExternalArrInstance(Base):
    """Prismarr-style external Sonarr/Radarr instance for dashboard aggregation."""
    __tablename__ = "external_arr_instances"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # sonarr|radarr|lidarr
    base_url: Mapped[str] = mapped_column(String, nullable=False)
    api_key: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class MediaQualityFile(Base):
    """Bobarr-style multi-quality retention: multiple files per item."""
    __tablename__ = "media_quality_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"), nullable=False)
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episodes.id"), nullable=True)
    quality_label: Mapped[str] = mapped_column(String, nullable=False)  # 1080p, 2160p
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))



# ---------------------------------------------------------------------------
# MediaOS v2 — Scrobbling, Tracking, Games, Homelab (absorbed concepts)
# ---------------------------------------------------------------------------

class TrackingStatus(str, enum.Enum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    dropped = "dropped"
    on_hold = "on_hold"
    repeating = "repeating"


class ScrobbleEventType(str, enum.Enum):
    start = "start"
    pause = "pause"
    resume = "resume"
    stop = "stop"
    scrobble = "scrobble"
    progress = "progress"


class Platform(Base):
    """Gaming platform / store (PC, PS5, Switch, Steam, GOG, etc.)."""
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    icon_url: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Game(Base):
    """
    Video game entity (Questarr-inspired).
    Reuses shared pipeline: search → grab → organize → track.
    """
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    sort_title: Mapped[str | None] = mapped_column(String, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String, nullable=True)
    fanart_path: Mapped[str | None] = mapped_column(String, nullable=True)
    external_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: igdb, steam, ...
    genres: Mapped[str | None] = mapped_column(String, nullable=True)
    platform_id: Mapped[int | None] = mapped_column(ForeignKey("platforms.id"), nullable=True)
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String, default="wanted")  # wanted|downloaded|installed|completed
    path: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    playtime_minutes: Mapped[int] = mapped_column(Integer, default=0)
    completion_percent: Mapped[float] = mapped_column(Float, default=0.0)
    last_played_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    quality_profile: Mapped[str | None] = mapped_column(String, nullable=True)
    install_path: Mapped[str | None] = mapped_column(String, nullable=True)
    launcher: Mapped[str | None] = mapped_column(String, nullable=True)  # steam://, shell path, etc.
    added_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class GameRelease(Base):
    """Specific release / edition / installer / ROM for a game."""
    __tablename__ = "game_releases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    edition: Mapped[str | None] = mapped_column(String, nullable=True)
    platform_id: Mapped[int | None] = mapped_column(ForeignKey("platforms.id"), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    grabbed: Mapped[bool] = mapped_column(Boolean, default=False)
    installed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class WatchProgress(Base):
    """Aggregated watch/play progress (scrob + Yamtrack inspired)."""
    __tablename__ = "watch_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_item_id: Mapped[int | None] = mapped_column(ForeignKey("media_items.id"), nullable=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), nullable=True)
    episode_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    season_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    position_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    play_count: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_watched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)  # jellyfin|plex|emby|manual|scrob
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class ScrobbleEvent(Base):
    """Individual scrobble / play event."""
    __tablename__ = "scrobble_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_item_id: Mapped[int | None] = mapped_column(ForeignKey("media_items.id"), nullable=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), nullable=True)
    episode_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    season_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)  # start|pause|scrobble|...
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    position_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class TrackedItem(Base):
    """
    Unified tracking record (Yamtrack-inspired).
    Status + rating + notes across any media type or game.
    """
    __tablename__ = "tracked_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_item_id: Mapped[int | None] = mapped_column(ForeignKey("media_items.id"), nullable=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), nullable=True)
    season_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="planned")  # TrackingStatus values
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rewatch_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class TrackingHistory(Base):
    """Action timeline for tracked items (Yamtrack-style history)."""
    __tablename__ = "tracking_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracked_item_id: Mapped[int | None] = mapped_column(ForeignKey("tracked_items.id"), nullable=True)
    media_item_id: Mapped[int | None] = mapped_column(ForeignKey("media_items.id"), nullable=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)  # added|started|completed|rewatch|status_change|rated
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)




class LiveTvSeriesRule(Base):
    """Series-record rule: auto-schedule matching EPG titles (Cinephage / DVR depth)."""
    __tablename__ = "livetv_series_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title_match: Mapped[str] = mapped_column(String, nullable=False)  # substring or exact
    match_mode: Mapped[str] = mapped_column(String, default="contains")  # contains|exact|startswith
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("livetv_channels.id"), nullable=True)  # None = any
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    keep_episodes: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited
    priority: Mapped[int] = mapped_column(Integer, default=50)
    only_new: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class LiveTvRecording(Base):
    """EPG click-to-record / DVR job (Cinephage-style)."""
    __tablename__ = "livetv_recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("livetv_channels.id"), nullable=True)
    channel_name: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String, nullable=True)
    tvg_id: Mapped[str | None] = mapped_column(String, nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="scheduled")  # scheduled|recording|completed|failed|cancelled
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    stream_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    series_rule_id: Mapped[int | None] = mapped_column(ForeignKey("livetv_series_rules.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class HomelabLink(Base):
    """Organizr-inspired service / bookmark links for the Homelab page."""
    __tablename__ = "homelab_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    icon_url: Mapped[str | None] = mapped_column(String, nullable=True)
    group_name: Mapped[str | None] = mapped_column(String, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    iframe: Mapped[bool] = mapped_column(Boolean, default=False)
    health_check_url: Mapped[str | None] = mapped_column(String, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String, nullable=True)  # up|down|unknown
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class GameInstallJob(Base):
    """Host install script run for a game."""
    __tablename__ = "game_install_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, default="queued")  # queued|running|done|failed
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    log_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    returncode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PathMap(Base):
    """Container path ↔ host path mapping for organize/stream."""
    __tablename__ = "path_maps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, default="default")
    container_prefix: Mapped[str] = mapped_column(String, nullable=False)
    host_prefix: Mapped[str] = mapped_column(String, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String, nullable=True)  # optional scope
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
