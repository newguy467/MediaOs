# Postgres / SQLite *arr migrator

`psycopg2-binary` is already in `requirements.txt` and installed in the Docker image.

```bash
# SQLite file mounted into the container
curl -X POST /api/migrate/db -H 'Content-Type: application/json' \
  -d '{"path":"/config/radarr/radarr.db","kind":"radarr"}'

# Live or restored Postgres
curl -X POST /api/migrate/db -H 'Content-Type: application/json' \
  -d '{"postgres_url":"postgres://user:pass@host:5432/sonarr","kind":"sonarr"}'
```

UI: **Settings → Integrations → DB migrator**
