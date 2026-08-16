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

    qbit_url: str = "http://qbittorrent:8080"  # compose overrides to http://gluetun:8080 when qB uses network_mode: service:gluetun
    qbit_username: str = "admin"
    qbit_password: str = ""  # set via QBIT_PASSWORD — no weak default

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
    prefer_stream_on_search: bool = False  # interactive UI prefers Stream; grab may still download
    games_install_script: str = ""  # optional host script: {path} {title} {id}
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
    ntfy_url: str = ""
    ntfy_topic: str = ""
    ntfy_token: str = ""
    gotify_url: str = ""
    gotify_token: str = ""

    # Jellyfin library refresh
    jellyfin_url: str = "http://jellyfin:8096"
    jellyfin_api_key: str = ""
    # Emby library refresh (same API shape as Jellyfin)
    emby_url: str = ""
    emby_api_key: str = ""

    # Auth (empty username + empty api key + no DB users = disabled)
    auth_username: str = ""
    auth_password: str = ""
    auth_api_key: str = ""
    # When true and no auth is configured, generate a one-time API key under /data
    auth_require: bool = True  # safer default; set AUTH_REQUIRE=false only for local dev
    cors_origins: str = ""  # comma-separated; empty = same-origin only; "*" for LAN labs
    # Redis (optional): multi-worker rate limits, session cache, scheduler leader election
    redis_url: str = ""  # e.g. redis://redis:6379/0 — empty = process-local fallbacks
    scheduler_leader_ttl_seconds: int = 45  # leader lock TTL; renew on each job tick
    auth_bootstrap_generate: bool = True  # generate bootstrap key file if open install  # X-API-Key header; optional alongside basic

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
    # Built-in NeutArr/Huntarr-class engine (no external NeutArr needed)
    hunt_enabled: bool = True
    hunt_interval_minutes: int = 60
    hunt_batch_limit: int = 25
    hunt_include_adult: bool = True  # include Adult module in hunt cycles
    hunt_include_upgrades: bool = False  # when True, also re-check downloaded for upgrades

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
    # Prefer hardlink when organizing into library (same filesystem required; falls back to move).
    # Default True so torrent clients keep seeding. Override with LIBRARY_PREFER_HARDLINK=false.
    library_prefer_hardlink: bool = True
    # After a successful hardlink, leave the torrent in the client so seeding continues.
    # Set LIBRARY_REMOVE_DOWNLOAD_AFTER_HARDLINK=true to remove the client item (files kept).
    library_remove_download_after_hardlink: bool = False
    # Adult (Whisparr-style) module — passcode gate
    adult_passcode_hash: str = ""  # pbkdf2 hash; empty = module locked until set
    adult_passcode_enabled: bool = True  # require unlock token for /api/adult/*
    adult_unlock_ttl_minutes: int = 60
    # Optional ThePornDB API key for metadata (leave empty to use title-only)
    tpdb_api_key: str = ""


    # LunaSea / *arr API compatibility
    arr_api_key: str = ""  # X-Api-Key for /api/v3/* shims; falls back to AUTH_API_KEY


    # Usenet (SABnzbd)
    sabnzbd_url: str = ""
    sabnzbd_api_key: str = ""
    sabnzbd_category: str = "mediaos"

    # Usenet (NZBGet)
    nzbget_url: str = ""  # e.g. http://nzbget:6789
    nzbget_username: str = "nzbget"
    nzbget_password: str = ""  # set via NZBGET_PASSWORD — no weak default
    nzbget_category: str = "mediaos"
    # Preferred usenet client when both configured: sabnzbd | nzbget | auto
    usenet_client: str = "auto"

    # Real-Debrid streaming
    real_debrid_token: str = ""

    # Trakt
    trakt_client_id: str = ""
    trakt_access_token: str = ""

    # Last.fm / ListenBrainz (music scrobbling)
    lastfm_api_key: str = ""
    lastfm_api_secret: str = ""
    lastfm_session_key: str = ""  # obtained out-of-band via auth.getToken + auth.getSession
    lastfm_scrobble_out: bool = True
    listenbrainz_token: str = ""  # ListenBrainz user token (bearer)
    listenbrainz_scrobble_out: bool = True

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
    comic_pull_auto_grab: bool = True
    comic_pull_auto_grab_limit: int = 10
    trash_guide_sync_hours: int = 168  # weekly
    trash_guide_auto_sync: bool = False  # enable periodic TRaSH guide sync
    livetv_epg_sync_hours: int = 6
    livetv_seed_iptv_org: bool = True  # seed US+Entertainment when no sources
    livetv_auto_grab: bool = True  # on startup: seed + resync + EPG index
    # Prefer local Node sidecar when present (compose service iptv-org-epg)
    livetv_epg_sidecar_url: str = "http://iptv-org-epg:3000/guide.xml"
    livetv_iptv_org_sync_hours: int = 24  # re-sync iptv-org M3U sources
    livetv_epg_extra_urls: str = ""  # comma-separated extra XMLTV URLs to merge
    livetv_offline_hours: float = 12  # remove/disable channels offline this long
    livetv_offline_action: str = "delete"  # delete | disable
    livetv_health_batch: int = 40  # channels probed per health cycle
    livetv_health_interval_minutes: int = 30  # stream health check interval
    livetv_max_concurrent: int = 2  # multi-tuner concurrent recording limit

    # Virtual TV (library → 24/7 channels)
    virtualtv_enabled: bool = True
    virtualtv_data_path: str = "data/livetv/virtual"  # HLS output + concat playlists live here
    virtualtv_schedule_horizon_hours: int = 12  # how far ahead to keep the schedule filled
    virtualtv_schedule_interval_minutes: int = 15  # how often to top the schedule back up
    virtualtv_stream_restart_hours: float = 4.0  # rebuild the ffmpeg concat feed this often to pick up new schedule
    virtualtv_default_repeat_protection_days: int = 7
    virtualtv_hls_segment_seconds: int = 6
    virtualtv_hls_playlist_size: int = 10



    # YouTube / Creator tracking (yt-dlp)
    youtube_library_path: str = "/youtube"
    adult_library_path: str = "/adult"
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
    # Tdarr-class health verification after encode
    converter_health_check: bool = True
    converter_health_min_duration_ratio: float = 0.95  # output duration >= ratio * source
    converter_health_min_size_ratio: float = 0.05  # reject near-empty outputs
    converter_max_attempts: int = 3  # re-queue on fail/health fail
    converter_auto_seed_libraries: bool = True  # seed /movies,/tv,… as watch folders
    # Optional external Tdarr server (classic Tdarr UI/nodes alongside native queue)
    tdarr_url: str = ""  # e.g. http://tdarr:8265
    tdarr_api_key: str = ""
    tdarr_enabled: bool = False

    # Movie Collections / Sagas (TMDb collection grouping) — beyond MediaOs
    collection_auto_add_default: bool = True

    # Cardigann YAML private/public tracker definitions (Jackett-compatible subset)
    cardigann_definitions_path: str = "/app/definitions"
    cardigann_enabled: bool = True
    cardigann_auto_sync: bool = True  # pull Jackett YAML defs on startup + weekly
    cardigann_auto_sync_on_startup: bool = True
    indexer_health_enabled: bool = True
    indexer_health_interval_hours: int = 6
    indexer_health_fail_disable: int = 5  # consecutive fails before auto-disable
    cardigann_sync_max_files: int = 0  # 0 = ALL Jackett defs (thousands); set e.g. 120 for light first run
    cardigann_sync_workers: int = 8  # parallel downloads when syncing full pack
    cardigann_sync_interval_hours: int = 168  # weekly, matches the current hardcoded schedule
    cardigann_fail_open: bool = True  # continue grabs if a single definition fails to parse

    # Logging
    log_level: str = "INFO"  # DEBUG|INFO|WARNING|ERROR
    log_dir: str = ""  # empty = auto /config/logs

    # Plugin / Module marketplace (GitHub-backed catalog)
    plugins_path: str = ""  # empty = /config/plugins or data/plugins
    plugin_registry_url: str = ""  # optional remote catalog JSON (GitHub raw)
    plugin_trusted_owners: str = ""  # comma-separated GitHub owners; empty = allow all
    plugins: str = ""  # comma-separated Python modules to import (env PLUGINS also works)


    vpn_username: str = ""
    vpn_password: str = ""

    # Plex / Tautulli now-playing (optional dashboard widget)
    plex_url: str = ""
    plex_token: str = ""
    tautulli_url: str = ""
    tautulli_api_key: str = ""


    # Games / IGDB (Questarr)
    igdb_client_id: str = ""
    igdb_client_secret: str = ""
    games_library_path: str = "/games"
    trakt_scrobble_out: bool = True
    webhook_secret: str = ""  # shared secret for /api/webhooks/*
    steam_api_key: str = ""
    steam_id: str = ""  # 64-bit steam id
    # UI simplicity (bobarr)
    library_mode: bool = False  # when True, hide advanced nav by default

settings = Settings()



