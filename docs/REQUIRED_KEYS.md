# Required configuration keys

## Always (Movies / TV)

| Key | Purpose |
|-----|---------|
| `tmdb_api_key` | Metadata search/add for movies & TV |
| `qbit_url` (+ user/pass) | Torrent downloads |
| Indexers (builtin Cardigann / Prowlarr / Jackett) | Release search |

Optional but recommended: `tvdb_api_key`, download path mounts.

## Games

| Key | Purpose |
|-----|---------|
| `igdb_client_id` | Twitch/IGDB client id |
| `igdb_client_secret` | Twitch/IGDB secret |

Without these, Games search returns no results and a clear “not configured” message.

## Live TV / virtual channels

- Indexer-style IPTV sources or iptv-org seed
- `ffmpeg` + `ffprobe` in the image for virtual channels

## Plugins

| Key | Purpose |
|-----|---------|
| `plugin_registry_url` | GitHub raw `catalog.json` (optional; bundled catalog ships in-tree) |
| `plugin_trusted_owners` | Comma-separated GitHub owners allowlist |
| `plugins_path` | Install directory (default `/config/plugins`) |

## AI

| Key | Purpose |
|-----|---------|
| Ollama reachable | `/api/ai/*` |

## Notifications

Apprise / Discord / Telegram fields in Settings when you want push alerts.
