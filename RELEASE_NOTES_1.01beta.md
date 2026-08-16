# MediaOS 1.01beta

**Tag:** `1.01beta`  
**Date:** 2026-08-16

## Highlights

Polish pass on absorbed *arr cores, background jobs, notifications, tracking, and migration preflight — building on `1.00beta`.

### Reliability & *arr
- **Backup wizard flags honored** — `include_db`, `include_config`, `note`
- ***arr import preflight** — connection, library shape, side-by-side dry-run (`POST /api/migrate/validate*`)
- **Path-map apply in organize** (not only dry-run)
- **Score breakdown** always populated for interactive-search Explain drawer
- **TorBox** client unit tests
- Pipeline **smoke tests** (`test_arr_pipeline_smoke`, `test_p2_p5_smoke`)

### Jobs & metadata
- **Metadata job queue** + SSE channel `metadata_job`
- Bulk metadata UI uses jobs + progress

### Users & kids
- Server-side **profile presets**: kids / viewer / power / full
- `GET /api/users/presets`, `POST /api/users/presets/{id}/apply`

### Subtitles & stream
- Bazarr-style **language profiles** + default profile API
- Movie/TV subtitle fetch uses active profile
- **Stream-first** ranking when `prefer_stream_on_search=true`

### Music / books (Lidarr / Readarr depth)
- Music: hunt-incomplete, missing-tracks, search-missing
- Books & audiobooks: **wanted-hierarchy**

### Notifications & tracking
- Center: Discord, Telegram, Apprise, **ntfy**, **Gotify** + history
- `GET/POST /api/system/notifications/*`
- Tracking statuses: planned → in_progress → completed / on_hold / dropped
- Games **playtime** increments feed tracking

### Live TV
- Channel bulk enable/reorder APIs
- **Auto health cleanup unchanged** (scheduled probe → delete/disable after offline hours)

### Docs
- `docs/MIGRATION.md` — P5 migration runbook
- `docs/TODO_NEXT.md` — remaining polish

## Upgrade

```bash
# from previous 1.00beta tree
git pull   # or unpack release zip
# optional
export APP_VERSION=1.01beta
docker compose up -d --build
```

No required DB migration for this tag beyond existing Alembic/schema paths.

## Verify

```bash
export AUTH_REQUIRE=false DATABASE_URL=sqlite:////tmp/mediaos-test.db
python3 -m pytest -q
```

Windows: `scripts\windows\06_run_tests.bat`

## Not in this tag (still open)
- Fuller Sonarr/Radarr **arr_compat** v3 surface
- Migration **wizard UI**
- Per-series subtitle overrides
- Notifications settings page (API ready)
- Public **2.0.0** release

## Git tag

```bash
git tag -a 1.01beta -m "MediaOS 1.01beta"
git push origin 1.01beta
```
