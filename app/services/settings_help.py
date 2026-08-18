"""Per-field help for Settings UI (? tooltips)."""
from __future__ import annotations

# Explicit help; anything missing falls back to a generated line from the field label.
FIELD_HELP: dict[str, str] = {
    # library / paths
    "movies_library_path": "Container path for finished movies (e.g. /movies). Not the Windows host path.",
    "tv_library_path": "Container path for series root (e.g. /tv).",
    "music_library_path": "Music library root for the Music module.",
    "books_library_path": "eBook library root.",
    "audiobooks_library_path": "Audiobook library root.",
    "podcasts_library_path": "Podcast storage folder.",
    "comics_library_path": "Comics (CBZ/CBR) root.",
    "manga_library_path": "Manga library root.",
    "youtube_library_path": "yt-dlp download / creator library folder.",
    "adult_library_path": "Adult library path (module + permissions).",
    "downloads_path": "Incomplete/completed downloads. Keep on same filesystem as libraries for hardlinks.",
    "games_library_path": "Games library / install root.",
    "movie_naming_folder": "Folder template for movies. Tokens like {title} {year}. Example: {title} ({year})",
    "episode_naming": "Episode filename template. Example: {series} - S{season:00}E{episode:00} - {title}",
    "library_prefer_hardlink": "Hardlink instead of move when source and library share a filesystem.",
    # downloads
    "qbit_url": "qBittorrent WebUI base URL. With Gluetun: http://gluetun:8080",
    "qbit_username": "qBittorrent WebUI username.",
    "qbit_password": "qBittorrent WebUI password (not the same as API cookie forever).",
    "torrent_client": "Which torrent backend MediaOS uses: qbittorrent, transmission, deluge, rtorrent, aria2.",
    "transmission_url": "Transmission RPC URL.",
    "transmission_username": "Transmission RPC username.",
    "transmission_password": "Transmission RPC password.",
    "deluge_url": "Deluge WebUI URL.",
    "deluge_password": "Deluge password.",
    "rtorrent_url": "rTorrent XML-RPC URL.",
    "aria2_url": "aria2 JSON-RPC URL.",
    "aria2_secret": "aria2 RPC secret token.",
    "allow_usenet": "Enable Usenet grab path (SABnzbd/NZBGet).",
    "usenet_client": "Preferred Usenet client: sabnzbd, nzbget, or auto.",
    "sabnzbd_url": "SABnzbd base URL.",
    "sabnzbd_api_key": "SABnzbd API key.",
    "sabnzbd_category": "Default SABnzbd category for MediaOS grabs.",
    "nzbget_url": "NZBGet base URL.",
    "nzbget_username": "NZBGet username.",
    "nzbget_password": "NZBGet password.",
    "nzbget_category": "NZBGet category.",
    # auth
    "auth_require": "Require login for the UI and API.",
    "auth_username": "Bootstrap admin username (if no DB users yet).",
    "auth_password": "Bootstrap admin password.",
    "auth_api_key": "Machine API key (X-Api-Key) for scripts.",
    "arr_api_key": "Key for /api/v3/* ARR-compat (Jellyseerr, LunaSea).",
    # system / notifications
    "apprise_url": "Apprise-compatible notify URL.",
    "discord_webhook_url": "Discord webhook for events.",
    "telegram_bot_token": "Telegram bot token.",
    "telegram_chat_id": "Telegram chat id for notifies.",
    "ntfy_url": "ntfy server base or full topic URL.",
    "ntfy_topic": "ntfy topic name.",
    "ntfy_token": "Optional ntfy access token.",
    "gotify_url": "Gotify server URL.",
    "gotify_token": "Gotify app token.",
    "webhook_url": "Generic webhook URL — receives a POSTed JSON body {event, title, message, ts}.",
    "webhook_headers": 'Optional extra headers for the webhook request, as a JSON object, e.g. {"Authorization": "Bearer xxx"}.',
    "jellyfin_url": "Jellyfin server URL for library refresh.",
    "jellyfin_api_key": "Jellyfin API key.",
    "emby_url": "Emby server URL.",
    "emby_api_key": "Emby API key.",
    # indexers
    "prowlarr_url": "Optional external Prowlarr (MediaOS has built-in indexers too).",
    "prowlarr_api_key": "Prowlarr API key.",
    "jackett_url": "Jackett base URL if used.",
    "jackett_api_key": "Jackett API key.",
    # metadata
    "tmdb_api_key": "TMDb API key for movie/TV metadata.",
    "tvdb_api_key": "TVDb API key.",
    "comicvine_api_key": "ComicVine API key.",
    "trakt_client_id": "Trakt client id for scrobble/lists.",
    # debrid / integrations common
    "real_debrid_api_key": "Real-Debrid token.",
    "torbox_api_key": "TorBox API key.",
    "alldebrid_api_key": "AllDebrid API key.",
    "premiumize_api_key": "Premiumize API key.",
    "plex_url": "Plex URL for now-playing / integrations.",
    "plex_token": "Plex token.",
    "radarr_url": "External Radarr for migration import only.",
    "sonarr_url": "External Sonarr for migration import only.",
    "prefer_stream_on_search": "Rank streamable/debrid results first in interactive search.",
}

PATH_HELP = {k: {"label": k, "help": v} for k, v in FIELD_HELP.items() if "path" in k or "naming" in k}
CLIENT_HELP = {
    "categories": "Categories keep movie/tv/music downloads in separate folders for hardlinks.",
    "apply": "Apply writes categories and optionally creates them in qBittorrent.",
}
QUALITY_HELP = {
    "hd": "Prefer 1080p WEB/BluRay; good default.",
    "uhd": "Prefer 2160p / 4K with HDR scoring boosts.",
    "anime": "Anime-friendly ranking.",
    "trash": "Import TRaSH/Recyclarr-style custom formats into scoring.",
}


def help_for(key: str, label: str | None = None) -> str:
    if key in FIELD_HELP:
        return FIELD_HELP[key]
    if label:
        return f"{label}. Change applies immediately (no restart)."
    return "Setting applies immediately (no restart)."
