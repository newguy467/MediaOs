"""Runtime-editable Settings overrides, grouped for the Settings UI pages.

app/config.py's `Settings` is a pydantic-settings singleton populated once
from the environment / .env at process start. That's fine for API keys and
infra wiring, but it means the "Download Clients", "Library Storage", and
"System" settings pages had nothing to write to — editing them would
require an env var change + container restart.

This module adds a thin DB-backed override layer on top of that singleton:
a row in `app_settings` (key -> JSON value) always wins over the env value.
`load_overrides()` is called once at startup to apply any saved overrides;
`update_group()` applies + persists new ones immediately, so changes made
in the UI take effect without a restart.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AppSetting

# group -> { field_name: (type, label, secret) }
# type is one of: str, int, float, bool
SETTINGS_GROUPS: dict[str, dict[str, tuple[type, str, bool]]] = {
    "integrations": {
        "plex_url": (str, "Plex URL (now-playing)", False),
        "plex_token": (str, "Plex token", True),
        "tautulli_url": (str, "Tautulli URL (now-playing)", False),
        "tautulli_api_key": (str, "Tautulli API key", True),
        "radarr_url": (str, "Radarr URL (for import)", False),
        "radarr_api_key": (str, "Radarr API key", True),
        "sonarr_url": (str, "Sonarr URL (for import)", False),
        "sonarr_api_key": (str, "Sonarr API key", True),
        "lidarr_url": (str, "Lidarr URL (for import)", False),
        "lidarr_api_key": (str, "Lidarr API key", True),
        "readarr_url": (str, "Readarr URL (for import)", False),
        "readarr_api_key": (str, "Readarr API key", True),
        "prowlarr_url": (str, "Prowlarr URL", False),
        "prowlarr_api_key": (str, "Prowlarr API key", True),
        "arr_api_key": (str, "MediaOs ARR-compat API key (for Jellyseerr)", True),
    },
    "downloads": {
        "qbit_url": (str, "qBittorrent URL", False),
        "qbit_username": (str, "qBittorrent Username", False),
        "qbit_password": (str, "qBittorrent Password", True),
        "torrent_client": (str, "Active torrent client (qbittorrent|transmission|deluge|rtorrent|aria2)", False),
        "transmission_url": (str, "Transmission RPC URL", False),
        "transmission_username": (str, "Transmission Username", False),
        "transmission_password": (str, "Transmission Password", True),
        "deluge_url": (str, "Deluge WebUI URL", False),
        "deluge_password": (str, "Deluge Password", True),
        "rtorrent_url": (str, "rTorrent XML-RPC URL", False),
        "aria2_url": (str, "aria2 JSON-RPC URL", False),
        "aria2_secret": (str, "aria2 Secret Token", True),
        "allow_usenet": (bool, "Enable Usenet clients", False),
        "usenet_client": (str, "Preferred usenet client (sabnzbd | nzbget | auto)", False),
        "sabnzbd_url": (str, "SABnzbd URL", False),
        "sabnzbd_api_key": (str, "SABnzbd API Key", True),
        "sabnzbd_category": (str, "SABnzbd Category", False),
        "nzbget_url": (str, "NZBGet URL", False),
        "nzbget_username": (str, "NZBGet Username", False),
        "nzbget_password": (str, "NZBGet Password", True),
        "nzbget_category": (str, "NZBGet Category", False),
    },
    "library": {
        "movies_library_path": (str, "Movies Library Path", False),
        "tv_library_path": (str, "TV Library Path", False),
        "music_library_path": (str, "Music Library Path", False),
        "books_library_path": (str, "Books Library Path", False),
        "audiobooks_library_path": (str, "Audiobooks Library Path", False),
        "podcasts_library_path": (str, "Podcasts Library Path", False),
        "comics_library_path": (str, "Comics Library Path", False),
        "manga_library_path": (str, "Manga Library Path", False),
        "youtube_library_path": (str, "YouTube Library Path", False),
        "adult_library_path": (str, "Adult Library Path", False),
        "downloads_path": (str, "Downloads Path", False),
        "movie_naming_folder": (str, "Movie folder naming template", False),
        "episode_naming": (str, "Episode file naming template", False),
        # Prefer hardlink when organizing (same filesystem required; falls back to move)
        "library_prefer_hardlink": (bool, "Prefer hardlink when organizing into library", False),
        "jdupes_enabled": (bool, "Enable jdupes duplicate scan", False),
        "jdupes_hardlink": (bool, "jdupes hardlink mode (-L) instead of delete", False),
    },
    "metadata": {
        "tmdb_api_key": (str, "TMDb API Key", True),
        "tvdb_api_key": (str, "TVDb API Key", True),
        "tvdb_pin": (str, "TVDb PIN", True),
        "comicvine_api_key": (str, "ComicVine API Key", True),
        "trakt_client_id": (str, "Trakt client ID", False),
        "trakt_access_token": (str, "Trakt access token", True),
    },
    "indexers": {
        "prowlarr_url": (str, "Prowlarr URL (optional)", False),
        "prowlarr_api_key": (str, "Prowlarr API Key", True),
        "jackett_url": (str, "Jackett URL (optional)", False),
        "jackett_api_key": (str, "Jackett API Key", True),
        "cardigann_enabled": (bool, "Enable bundled Cardigann definitions", False),
        "cardigann_definitions_path": (str, "Cardigann definitions path", False),
        "cardigann_auto_sync": (bool, "Auto-sync Jackett YAML definitions", False),
        "cardigann_auto_sync_on_startup": (bool, "Seed definitions on startup", False),
        "cardigann_sync_interval_hours": (int, "Cardigann definition sync interval (hours)", False),
        "cardigann_fail_open": (bool, "Continue grabs if a definition fails to parse", False),
        "min_seeders": (int, "Minimum seeders", False),
        "jackett_sync_on_startup": (bool, "Sync Jackett indexers on startup", False),
        "flaresolverr_url": (str, "FlareSolverr URL", False),
        "cf_bypass_enabled": (bool, "Built-in CF bypass (curl_cffi)", False),
        "cf_impersonate": (str, "CF impersonate profile", False),
    },
    "subtitles": {
        "opensubtitles_api_key": (str, "OpenSubtitles API Key", True),
        "opensubtitles_username": (str, "OpenSubtitles Username", False),
        "opensubtitles_password": (str, "OpenSubtitles Password", True),
        "subtitle_languages": (str, "Languages (comma ISO 639-1)", False),
        "subtitle_hearing_impaired": (str, "Hearing-impaired: prefer|include|exclude", False),
        "subtitle_providers": (str, "Providers (comma list)", False),
        "subdl_api_key": (str, "SubDL API Key", True),
        "subtitle_language_profile_id": (int, "Default language profile id", False),
    },
    
    "adult": {
        "adult_library_path": (str, "Adult Library Path", False),
        "adult_passcode_enabled": (bool, "Require passcode to open Adult module", False),
        "adult_unlock_ttl_minutes": (int, "Adult unlock TTL (minutes)", False),
        "tpdb_api_key": (str, "ThePornDB API Key (optional metadata)", True),
    },
    
    "hunt": {
        "hunt_enabled": (bool, "Enable built-in Hunt engine (NeutArr/Huntarr-class)", False),
        "hunt_interval_minutes": (int, "Hunt interval (minutes)", False),
        "hunt_batch_limit": (int, "Max items per hunt cycle", False),
        "hunt_include_adult": (bool, "Include Adult library in hunt", False),
        "hunt_include_upgrades": (bool, "Also hunt upgrades for downloaded items", False),
    },
    "cleanup": {
        "cleanup_enabled": (bool, "Enable queue cleaner", False),
        "cleanup_max_strikes": (int, "Max strikes before remove", False),
        "cleanup_stall_minutes": (int, "Stall threshold (minutes)", False),
        "cleanup_min_speed_kb": (float, "Min download speed (KB/s)", False),
        "cleanup_auto_search": (bool, "Auto re-search after remove", False),
        "cleanup_seed_enabled": (bool, "Enable seed ratio cleaner", False),
        "cleanup_seed_ratio": (float, "Seed ratio target", False),
        "cleanup_seed_minutes": (int, "Seed time target (minutes)", False),
        "cleanup_skip_private": (bool, "Never remove private torrents", False),
        "cleanup_interval_minutes": (int, "Cleanup interval (minutes)", False),
        "cleanup_seed_require_both": (bool, "Require both ratio AND time", False),
        "cleanup_orphans": (bool, "Scan orphaned library files", False),
        "cleanup_orphans_delete": (bool, "Delete orphans (dangerous)", False),
    },
    "debrid": {
        "real_debrid_token": (str, "Real-Debrid token", True),
        "torbox_api_key": (str, "TorBox API key", True),
        "alldebrid_api_key": (str, "AllDebrid API key", True),
        "premiumize_api_key": (str, "Premiumize API key", True),
        "debridlink_api_key": (str, "Debrid-Link API key", True),
        "putio_token": (str, "put.io OAuth token", True),
        "easydebrid_api_key": (str, "EasyDebrid API key", True),
        "offcloud_api_key": (str, "Offcloud API key", True),
        "movie_download_mode": (str, "Movie mode: download | strm", False),
        "movie_write_strm_sidecar": (bool, "Write .strm sidecar files", False),
    },
    "youtube": {
        "youtube_library_path": (str, "YouTube Library Path", False),
        "youtube_ytdlp_path": (str, "yt-dlp Path", False),
        "youtube_format": (str, "yt-dlp Format", False),
        "youtube_auto_download_default": (bool, "Auto-download new videos", False),
        "youtube_cookies_path": (str, "Cookies file (Netscape)", False),
        "youtube_cookies_from_browser": (str, "Cookies from browser", False),
        "youtube_sponsorblock_remove": (str, "SponsorBlock remove categories", False),
        "youtube_sponsorblock_mark": (str, "SponsorBlock mark categories", False),
        "youtube_check_interval_minutes": (int, "Check interval (minutes)", False),
        "youtube_backlog_download": (bool, "Download backlog on first add", False),
        "youtube_embed_player": (bool, "Embed player in UI", False),
    },
    "usenet": {
        "nntp_host": (str, "NNTP host", False),
        "nntp_port": (int, "NNTP port", False),
        "nntp_user": (str, "NNTP username", False),
        "nntp_pass": (str, "NNTP password", True),
        "nntp_ssl": (bool, "NNTP SSL/TLS", False),
        "nntp_cache_mb": (int, "Segment cache (MB)", False),
        "nntp_prefetch_segments": (int, "Prefetch segments", False),
        "nntp_session_ttl": (int, "Session TTL (seconds)", False),
    },
    "vpn": {
        "vpn_enabled": (bool, "Enable VPN health checks", False),
        "vpn_provider": (str, "Provider (gluetun|wireguard|openvpn)", False),
        "vpn_gluetun_url": (str, "Gluetun control URL", False),
        "vpn_expected_country": (str, "Expected country (e.g. NL)", False),
        "vpn_public_ip_url": (str, "Public IP check URL", False),
        "vpn_kill_switch": (bool, "Block grabs when VPN unhealthy", False),
        "vpn_check_timeout_seconds": (float, "Check timeout (seconds)", False),
        "vpn_username": (str, "VPN username", False),
        "vpn_password": (str, "VPN password", True),
    },
    "auth": {
        "auth_username": (str, "Admin username", False),
        "auth_password": (str, "Admin password", True),
        "auth_api_key": (str, "X-API-Key", True),
        "arr_api_key": (str, "ARR-compat API key", True),
        "auth_seed_admin_username": (str, "Seed admin username", False),
        "auth_seed_admin_password": (str, "Seed admin password", True),
    },
    "system": {
        "livetv_offline_hours": (float, "Live TV: offline hours before remove", False),
        "livetv_offline_action": (str, "Live TV offline action (delete|disable)", False),
        "livetv_epg_extra_urls": (str, "Extra XMLTV EPG URLs (comma-separated)", False),
        "livetv_health_interval_minutes": (int, "Live TV health check interval (min)", False),
        "livetv_max_concurrent": (int, "Live TV max concurrent recordings (multi-tuner)", False),
        "search_interval_minutes": (int, "Auto-search interval (minutes)", False),
        "min_seeders": (int, "Minimum seeders", False),
        "download_timeout_hours": (int, "Download timeout (hours)", False),
        "max_download_failures": (int, "Max failures before blocklist", False),
        "upgrade_enabled": (bool, "Enable quality upgrades", False),
        "upgrade_min_score_gap": (int, "Min score gap to upgrade", False),
        "upgrade_search_interval_hours": (int, "Upgrade search interval (hours)", False),
        "upgrade_prevent_resolution_downgrade": (bool, "Block resolution downgrades", False),
        "failed_download_cooldown_hours": (int, "Failed download cooldown (hours)", False),
        "library_watch_enabled": (bool, "Enable library file watch", False),
        "library_watch_interval_seconds": (int, "Library watch interval (seconds)", False),
        "tv_prefer_season_packs": (bool, "Prefer season packs", False),
        "tv_rss_lookback_days": (int, "TV RSS lookback (days)", False),
        "collection_auto_add_default": (bool, "Auto-add collection members", False),
        "apprise_url": (str, "Apprise notification URL", True),
        "discord_webhook_url": (str, "Discord webhook URL", True),
        "telegram_bot_token": (str, "Telegram bot token", True),
        "telegram_chat_id": (str, "Telegram chat ID", False),
        "jellyfin_url": (str, "Jellyfin URL", False),
        "jellyfin_api_key": (str, "Jellyfin API Key", True),
        "emby_url": (str, "Emby URL", False),
        "emby_api_key": (str, "Emby API Key", True),
        "unpack_enabled": (bool, "Unpack archives after download", False),
        "unpack_delete_archive": (bool, "Delete archive after unpack", False),
        "jdupes_enabled": (bool, "Enable jdupes", False),
        "jdupes_path": (str, "jdupes binary path", False),
        "jdupes_hardlink": (bool, "jdupes hardlink mode", False),
        "library_prefer_hardlink": (bool, "Hardlink into library instead of moving (same filesystem)", False),
        "cross_seed_url": (str, "cross-seed URL", False),
        "cross_seed_api_key": (str, "cross-seed API key", True),
        "log_dir": (str, "Log directory", False),
        "podcast_auto_download_default": (bool, "Podcast auto-download default", False),
        "podcast_backlog_download": (bool, "Podcast backlog on add", False),
        "podcast_chapters_enabled": (bool, "Podcast chapters", False),
        "podcast_check_interval_minutes": (int, "Podcast check interval", False),
        "stalker_mac": (str, "Stalker Live TV MAC", False),
        "converter_hwaccel_default": (str, "Converter hwaccel default", False),
        "converter_watch_interval_minutes": (int, "Converter watch interval", False),
        "converter_watch_limit": (int, "Converter watch limit", False),
        "plugin_registry_url": (str, "Plugin catalog URL (GitHub raw JSON)", False),
        "plugin_trusted_owners": (str, "Trusted GitHub owners for plugins (comma-separated)", False),
        "plugins_path": (str, "Plugins install directory", False),
        "plugins": (str, "Extra plugin Python modules (comma-separated)", False),
    },
}


def _cast(raw: Any, type_: type) -> Any:
    if type_ is bool:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if type_ is int:
        return int(raw)
    if type_ is float:
        return float(raw)
    return str(raw)


def _all_fields() -> dict[str, tuple[type, str, bool]]:
    out: dict[str, tuple[type, str, bool]] = {}
    for fields in SETTINGS_GROUPS.values():
        out.update(fields)
    return out


def load_overrides(db: Session) -> None:
    """Apply every saved override onto the live `settings` singleton. Call once at startup."""
    fields = _all_fields()
    for row in db.query(AppSetting).all():
        if row.key not in fields:
            continue
        type_, _label, _secret = fields[row.key]
        try:
            value = _cast(json.loads(row.value), type_) if row.value is not None else None
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if value is not None:
            setattr(settings, row.key, value)


def get_group(db: Session, group: str) -> dict[str, Any]:
    fields = SETTINGS_GROUPS.get(group)
    if fields is None:
        raise KeyError(group)
    out = {}
    for key, (_type, label, secret) in fields.items():
        value = getattr(settings, key, None)
        out[key] = {
            "value": ("" if not value else "••••••••") if secret and value else value,
            "label": label,
            "secret": secret,
        }
    return out


def update_group(db: Session, group: str, payload: dict[str, Any]) -> dict[str, Any]:
    fields = SETTINGS_GROUPS.get(group)
    if fields is None:
        raise KeyError(group)
    for key, raw in payload.items():
        if key not in fields:
            continue
        type_, _label, secret = fields[key]
        # A secret field left as the masked placeholder means "unchanged" — skip it.
        if secret and raw == "••••••••":
            continue
        value = _cast(raw, type_)
        setattr(settings, key, value)
        row = db.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=json.dumps(value))
            db.add(row)
        else:
            row.value = json.dumps(value)
    db.commit()
    return get_group(db, group)
