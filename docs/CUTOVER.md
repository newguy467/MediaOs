# *arr cutover guide

1. Run setup wizard (metadata, paths, download client, Jackett optional).
2. Import libraries: `POST /api/migrate/radarr` and `/api/migrate/sonarr`.
3. Import quality: Settings → Integrations → TRaSH (bundled packs under `data/trash/`).
4. Sync Jackett: Settings → Indexers → Sync from Jackett.
5. Point Overseerr/Jellyseerr at mediaos `ARR_API_KEY` or use built-in Requests.
6. Confirm grabs on a test movie/episode, then stop Sonarr/Radarr/etc.

## GPU converter
Set `HANDBRAKE_PRESET` / use Converter → GPU setup. Needs host `/dev/dri` or NVIDIA runtime.

## Jackett
`JACKETT_URL` + `JACKETT_API_KEY`. Auto-sync every 6h when configured.
