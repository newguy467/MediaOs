# P5 — Migration (MediaOs 4.x + *arr → MediaOS Next)

## Meaning
Import existing libraries without starting from zero.

## Already available
1. Live *arr API: `POST /api/migrate/radarr|sonarr|lidarr|readarr`, Prowlarr indexers
2. DB import: `POST /api/migrate/db` (SQLite/Postgres)
3. Preflight: `POST /api/migrate/validate` (+ connection, side-by-side)
4. TRaSH profiles: `POST /api/migrate/trash`
5. Provider ID backfill: `POST /api/migrate/backfill-provider-ids`

## Recommended order
1. `POST /api/migrate/test` or `/validate/connection`
2. Full preflight `/validate` — review would_add_estimate
3. Run migrate for that kind
4. Path-map dry-run if container paths differ
5. Optional bulk metadata job

## Still to polish
- Guided Migration wizard UI
- Path rewrite on import via PathMap
- Quality profile name mapping
- Post-import verification report
- MediaOs 4.x-specific export if schema differs
