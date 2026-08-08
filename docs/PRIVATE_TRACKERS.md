# Private trackers

1. Add Cardigann YAML under `/config/cardigann` (or use Jackett sync).
2. Settings → Indexers → set **credentials** (username/password/cookie/apikey) on the row.
3. Credentials are stored in `indexers.credentials_json` and injected into Cardigann login on search.

Jackett: sync every 6h when `JACKETT_URL` + `JACKETT_API_KEY` are set.
