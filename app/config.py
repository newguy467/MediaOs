from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://mediaos:mediaos@mediaos-db:5432/mediaos"

    tmdb_api_key: str = ""
    tvdb_api_key: str = ""
    tvdb_pin: str = ""

    prowlarr_url: str = "http://prowlarr:9696"
    prowlarr_api_key: str = ""
    radarr_url: str = ""
    radarr_api_key: str = ""
    sonarr_url: str = ""
    sonarr_api_key: str = ""
    lidarr_url: str = ""
    lidarr_api_key: str = ""
    readarr_url: str = ""
    readarr_api_key: str = ""

    # Jackett (indexer list sync → local Torznab rows)
    jackett_url: str = ""
    jackett_api_key: str = ""
    jackett_sync_on_startup: bool = True

    qbit_url: str = "http://qbittorrent:8080"
    qbit_username: str = "admin"
    qbit_password: str = "adminadmin"

    # Extra torrent clients (MediaOs parity)
    torrent_client: str = "qbittorrent"  # qbittorrent | transmission | deluge | rtorrent | aria2
    transmission_url: str = ""
    transmission_username: str = ""
    transmission_password: str = ""
    deluge_url: str = ""
    deluge_password: str = ""
    rtorrent_url: str = ""
    aria2_url: str = ""
    aria2_secret: str = ""

    movies_library_path: str = "/movies"
    tv_library_path: str = "/tv"
    downloads_path: str = "/downloads"
    music_library_path: str = "/music"
    books_library_path: str = "/books"
    audiobooks_library_path: str = "/audiobooks"

    search_interval_minutes: int = 15  # tighter continuous feel
    min_seeders: int = 3

    download_timeout_hours: int = 24
    # After this many failed grabs for same item, blocklist the release
    max_download_failures: int = 2

    # Cleanuparr-inspired queue cleaner
    cleanup_enabled: bool = True
    cleanup_max_strikes: int = 3
    cleanup_stall_minutes: int = 30
    cleanup_min_speed_kb: float = 20.0
    cleanup_auto_search: bool = True
    cleanup_orphans: bool = True
    cleanup_orphans_delete: bool = False  # report-only by default
    cleanup_interval_minutes: int = 5
    # Seeding / completed-download cleaner (Cleanuparr download-cleaner parity)
    cleanup_seed_enabled: bool = True
    cleanup_seed_ratio: float = 2.0          # remove when ratio >= this
    cleanup_seed_minutes: int = 10080       # or seeded at least this long (7d)
    cleanup_seed_require_both: bool = False # if True, need ratio AND time
    cleanup_skip_private: bool = True       # never auto-remove private torrents

    allow_usenet: bool = False
    # download = qBittorrent torrent; strm = write .strm with release URL (no local download)
    movie_download_mode: str = "download"  # download | strm
    # When organizing movies, also write a .strm alongside the video pointing at file path (optional)
    movie_write_strm_sidecar: bool = False

    upgrade_enabled: bool = True
    upgrade_min_score_gap: int = 50
    upgrade_search_interval_hours: int = 24
    # Block upgrades that lower resolution even if custom-format score is higher (MediaOs v0.13)
    upgrade_prevent_resolution_downgrade: bool = True
    # Hours to wait before re-grabbing a failed release title
    failed_download_cooldown_hours: int = 1

    # Subtitles (OpenSubtitles.com)
    opensubtitles_api_key: str = ""
    opensubtitles_username: str = ""
    opensubtitles_password: str = ""
    subtitle_languages: str = "en"  # comma-separated ISO 639-1
    # prefer | include | exclude hearing-impaired tracks
    subtitle_hearing_impaired: str = "include"
    subtitle_providers: str = "sidecar,opensubtitles,subdl"  # solid defaults; addic7ed/subscene/yify optional (HTML+CF fragile)
    subdl_api_key: str = ""

    # Library file watch (poll-based real-time)
    library_watch_enabled: bool = True
    library_watch_interval_seconds: int = 30


    # TV continuous / RSS-style
    tv_prefer_season_packs: bool = True
    tv_rss_lookback_days: int = 14  # prioritize episodes aired in this window

    # Notifications (Apprise URL, e.g. discord://...)
    apprise_url: str = ""
    discord_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Jellyfin library refresh
    jellyfin_url: str = "http://jellyfin:8096"
    jellyfin_api_key: str = ""
    # Emby library refresh (same API shape as Jellyfin)
    emby_url: str = ""
    emby_api_key: str = ""

    # Auth (empty username + empty api key + no DB users = disabled)
    auth_username: str = ""
    auth_password: str = ""
    auth_api_key: str = ""  # X-API-Key header; optional alongside basic

    # FlareSolverr (optional Cloudflare bypass for direct fetches)
    flaresolverr_url: str = ""  # e.g. http://flaresolverr:8191

    # Seed first admin when no users exist (optional)
    auth_seed_admin_username: str = ""
    auth_seed_admin_password: str = ""

    # VPN / Gluetun integration
    # When vpn_enabled + vpn_kill_switch: refuse grabs if tunnel is down
    vpn_enabled: bool = False
    vpn_provider: str = "gluetun"  # gluetun | wireguard | openvpn | other
    vpn_gluetun_url: str = "http://gluetun:8000"  # Gluetun control server
    vpn_expected_country: str = ""  # e.g. NL — empty = any
    vpn_public_ip_url: str = "https://ifconfig.io/ip"
    vpn_kill_switch: bool = True  # block torrent grabs when VPN unhealthy
    vpn_check_timeout_seconds: float = 8.0
    # Gluetun provider credentials (written to UI / documented for compose)
    vpn_service_provider: str = ""  # protonvpn | surfshark | mullvad | nordvpn | private internet access | custom
    vpn_opvn_user: str = ""  # often same as vpn_username
    vpn_opvn_password: str = ""
    vpn_wireguard_private_key: str = ""
    vpn_wireguard_addresses: str = ""
    vpn_wireguard_public_key: str = ""
    vpn_server_countries: str = ""  # e.g. Netherlands,USA
    vpn_server_cities: str = ""
    vpn_port_forwarding: bool = False
    # Hunt engine
    hunt_interval_minutes: int = 60
    hunt_batch_limit: int = 25

    # Cross-Seed (https://cross-seed.org) — notify on grab/organize
    cross_seed_url: str = ""  # e.g. http://cross-seed:2468
    cross_seed_api_key: str = ""

    # Unpack on complete (Unpackerr-style) before organize
    unpack_enabled: bool = True
    unpack_delete_archive: bool = False

    # jdupes library dedupe
    jdupes_enabled: bool = True
    jdupes_path: str = "jdupes"  # binary on PATH
    jdupes_hardlink: bool = False  # if True, -L hardlink mode when applying

    # LunaSea / *arr API compatibility
    arr_api_key: str = ""  # X-Api-Key for /api/v3/* shims; falls back to AUTH_API_KEY


    # Usenet (SABnzbd)
    sabnzbd_url: str = ""
    sabnzbd_api_key: str = ""
    sabnzbd_category: str = "mediaos"

    # Usenet (NZBGet)
    nzbget_url: str = ""  # e.g. http://nzbget:6789
    nzbget_username: str = "nzbget"
    nzbget_password: str = "tegbzn6789"
    nzbget_category: str = "mediaos"
    # Preferred usenet client when both configured: sabnzbd | nzbget | auto
    usenet_client: str = "auto"

    # Real-Debrid streaming
    real_debrid_token: str = ""

    # Trakt
    trakt_client_id: str = ""
    trakt_access_token: str = ""

    # Naming (TRaSH-style)
    movie_naming_folder: str = "{title} ({year})"
    episode_naming: str = "{series} - S{season:00}E{episode:00} - {title}"


    # Built-in CF bypass (curl_cffi) — no FlareSolverr required
    cf_bypass_enabled: bool = True
    cf_impersonate: str = "chrome124"

    # Extra debrid providers
    torbox_api_key: str = ""
    alldebrid_api_key: str = ""
    premiumize_api_key: str = ""
    debridlink_api_key: str = ""
    putio_token: str = ""
    easydebrid_api_key: str = ""
    offcloud_api_key: str = ""

    # NNTP / seekable usenet
    nntp_host: str = ""
    nntp_port: int = 563
    nntp_user: str = ""
    nntp_pass: str = ""
    nntp_ssl: bool = True
    nntp_cache_mb: int = 64
    nntp_session_ttl: int = 3600
    nntp_prefetch_segments: int = 2

    # Stalker default
    stalker_portal_url: str = ""
    stalker_mac: str = ""


    subtitle_language_profile_id: int = 1

    # Podcasts (RSS) — zero arr-ecosystem apps cover this
    podcasts_library_path: str = "/podcasts"
    podcast_check_interval_minutes: int = 30
    podcast_auto_download_default: bool = True
    # Skip auto-download of episodes older than this on first feed add (0 = grab full backlog)
    podcast_backlog_download: bool = False
    podcast_chapters_enabled: bool = True

    # Comics / Manga
    comics_library_path: str = "/comics"
    manga_library_path: str = "/manga"
    comicvine_api_key: str = ""
    trash_guide_url: str = ""  # optional JSON guide URL for matrix import
    trash_guide_path: str = ""  # optional local JSON path
    comic_pull_sync_hours: int = 12
    trash_guide_sync_hours: int = 168  # weekly
    livetv_epg_sync_hours: int = 6
    livetv_seed_iptv_org: bool = True  # seed US+Entertainment when no sources
    livetv_iptv_org_sync_hours: int = 24  # re-sync iptv-org M3U sources



    # YouTube / Creator tracking (yt-dlp)
    youtube_library_path: str = "/youtube"
    youtube_check_interval_minutes: int = 60
    youtube_auto_download_default: bool = True
    youtube_ytdlp_path: str = "yt-dlp"
    youtube_format: str = "best[height<=1080]"
    youtube_backlog_download: bool = False
    # Cookies for age-restricted / members content
    youtube_cookies_path: str = ""  # Netscape cookies.txt path e.g. /config/youtube-cookies.txt
    youtube_cookies_from_browser: str = ""  # chrome | firefox | brave | edge | chromium
    # SponsorBlock + ad-like segment removal (native yt-dlp)
    youtube_sponsorblock_remove: str = "sponsor,selfpromo,interaction,intro,outro,preview,music_offtopic"
    youtube_sponsorblock_mark: str = ""
    youtube_embed_player: bool = True
    # Optional HTTP(S)/SOCKS proxy for yt-dlp only (region unlock / tunnel)
    youtube_proxy: str = ""  # e.g. socks5://gluetun:1080 or http://host:8080
    youtube_player_note: str = ""  # optional note shown in UI (e.g. external ad-free client)

    # Converter (Tdarr-style)
    converter_watch_folders: str = ""  # comma-separated paths to auto-scan
    converter_watch_preset_id: int | None = None  # None = default preset
    converter_watch_interval_minutes: int = 15
    converter_watch_limit: int = 50
    converter_hwaccel_default: str = "none"  # none|cuda|qsv|vaapi
    converter_max_workers: int = 2  # parallel ffmpeg jobs
    converter_schedule_start_hour: int | None = None  # 0-23, None = always
    converter_schedule_end_hour: int | None = None  # exclusive end hour local/UTC

    # Movie Collections / Sagas (TMDb collection grouping) — beyond MediaOs
    collection_auto_add_default: bool = True

    # Cardigann YAML private/public tracker definitions (Jackett-compatible subset)
    cardigann_definitions_path: str = "/app/definitions"
    cardigann_enabled: bool = True
    cardigann_auto_sync: bool = True  # pull Jackett YAML defs on startup + weekly
    cardigann_auto_sync_on_startup: bool = True
    cardigann_sync_max_files: int = 0  # 0 = all; e.g. 80 for lighter first sync

    # Logging
    log_level: str = "INFO"  # DEBUG|INFO|WARNING|ERROR
    log_dir: str = ""  # empty = auto /config/logs


    vpn_username: str = ""
    vpn_password: str = ""
    vpn_killswitch: bool = False
    vpn_interface: str = ""

settings = Settings()


