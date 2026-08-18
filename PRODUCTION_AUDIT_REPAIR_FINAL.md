# MediaOS 1.01beta — Full Production Audit + Repair

Date: 2026-08-18

## Scope

Recursive review of the supplied MediaOS project archive, including backend Python source, React/Vite UI source, generated UI assets, package/dependency definitions, Dockerfiles, all shipped Compose variants, Alembic migrations, shell scripts, Windows batch/HTA tooling, indexer definitions, tests, CI/security workflows, and operational documentation.

## Final verdict

**No Critical or High issue remains identified from the source/static audit.**

The working architecture and container-side media paths were preserved. The audit did not replace the MediaOS architecture with a theoretical alternative.

A live Docker host, real VPN credentials, real Jellyfin/qBittorrent services, and package-registry access were not available in this environment, so those portions are explicitly reported as runtime limitations rather than claimed as verified.

## Issues fixed in this pass

### HIGH — fixed

**FILE:** `app/main.py`
**LINE:** 435-448
**SEVERITY:** HIGH — reliability
**PROBLEM:** Versioned schema migration failures were caught, logged as warnings, and startup continued. That can leave the application running against a partially upgraded database and convert a deterministic startup failure into scattered runtime errors.
**ROOT CAUSE:** Critical database initialization was treated as best-effort exception handling.
**FIX:** Migration failures now use `log.exception()` and are re-raised, causing startup to fail cleanly so the service supervisor/Docker restart policy can recover and the actual migration error remains visible.

### MEDIUM — fixed

**FILE:** `tests/conftest.py`
**LINE:** 8, 27-30
**SEVERITY:** MEDIUM — test reliability
**PROBLEM:** The test database used one fixed `/tmp/mediaos-test.db` path and schema-migration exceptions were silently swallowed. Parallel test processes could race on the same SQLite file, producing misleading `readonly database` / `no such table` failures.
**ROOT CAUSE:** Shared test state plus swallowed setup failures.
**FIX:** The test DB is now process-specific (`/tmp/mediaos-test-<pid>.db`) and migration failures fail the test session instead of being hidden.

## Previously repaired issues retained and re-verified

The supplied project already contained the earlier production-hardening repairs, which were retained:

- Custom Gluetun WireGuard environment mapping is complete.
- qBittorrent uses `network_mode: service:gluetun` in the main production compose.
- qBittorrent has a healthcheck, resource limits, and `no-new-privileges`.
- MediaOS waits for healthy qBittorrent and Gluetun in the main stack.
- Library mounts are consistent across MediaOS, Jellyfin, qBittorrent, and Tdarr where applicable.
- Organize/hook best-effort paths log failures instead of silently discarding all diagnostics.
- MediaOS UI theme architecture retains the preset theme selector and uses design tokens rather than `!important` theme fights.
- UI CSS contains zero `!important` declarations.
- UI static and lazy-export checks continue to pass.

## Media/download path audit

Main production compose uses consistent in-container paths:

- Movies → `/movies`
- TV → `/tv`
- Music → `/music`
- Books → `/books`
- Audiobooks → `/audiobooks`
- Podcasts → `/podcasts`
- Comics → `/comics`
- Manga → `/manga`
- YouTube → `/youtube`
- Downloads → `/downloads`

The main compose maps the same host `DOWNLOADS_PATH` into MediaOS and qBittorrent, preserving hardlink compatibility. Jellyfin and MediaOS share the library paths required for playback/organization.

## Arr / media-server compatibility review

The project intentionally absorbs the core *arr control-plane functions into MediaOS while retaining compatibility APIs and migration paths for:

- Radarr
- Sonarr
- Lidarr
- Readarr
- Prowlarr
- Jellyseerr/Overseerr/LunaSea-style Radarr/Sonarr API consumers

Native clients/compatibility code was found for qBittorrent, Prowlarr, Tdarr, Jellyfin, and the supported external integrations. The default production compose does not run separate Sonarr/Radarr/Lidarr/Readarr/Prowlarr/Jellyseerr containers because MediaOS is designed to replace those control-plane services.

Live external-service connectivity was not claimed because no live service endpoints/credentials were available in the audit environment.

## Docker / configuration review

All shipped `docker-compose*.yml` files parsed successfully with PyYAML. The Docker CLI itself is not installed in the audit environment, so `docker compose config` and real container startup could not be executed here.

The main compose was reviewed for:

- dependency ordering
- healthchecks
- restart policies
- resource limits
- logging rotation
- `no-new-privileges`
- Gluetun/qBittorrent network isolation
- library/download volume consistency
- optional profiles
- host port bindings
- GPU overlays
- Docker build context paths

No new Critical/High configuration defect was identified.

## Windows / PowerShell review

Windows batch and HTA launch/build scripts were recursively inspected. Shell quoting, `%~dp0` repository-root handling, Docker Desktop checks, Python/npm checks, virtual-environment handling, and generated PostgreSQL password handling were reviewed.

The generated password path uses Python `secrets` and passes the resulting hex string into PowerShell, avoiding user-controlled shell interpolation.

No Critical/High Windows scripting defect was identified.

## Security review

Reviewed for:

- hard-coded credentials
- Docker socket exposure
- privileged containers
- dangerous host mounts
- unsafe subprocess shell execution
- path traversal in player/restore paths
- zip-slip during backup restore
- exposed qBittorrent control UI
- VPN kill-switch architecture
- container privilege escalation

The main qBittorrent WebUI is loopback-bound by default. Gluetun is the only service with `NET_ADMIN`/TUN access in the production compose. MediaOS does not expose the Docker socket.

No Critical/High security issue was identified in the supplied source/configuration.

## Second audit / verification

### PASS

- Python compileall across backend/scripts/Alembic/tests
- YAML parse of all 8 shipped Compose files
- JSON parse of `package.json` and `package-lock.json`
- `check_version.py`
- `check_ui_static.py` — **60 JSX files / 50 icons**
- `check_lazy_exports.mjs`
- duplicate top-level Python function scan
- local-import existence scan
- Alembic `upgrade head → downgrade -1 → upgrade head`
- focused regression suite after repairs — **62 passed**
- no `TODO`/`FIXME` markers in active `app`, `ui/src`, `scripts`, or `docker` source
- no UI CSS `!important` declarations

## Tests not fully executable here

The audit sandbox is missing several runtime packages declared by the project, including APScheduler, psycopg2-binary, watchdog, curl_cffi, and redis. Network access to PyPI is unavailable, so dependencies could not be installed.

The full pytest suite was therefore attempted but cannot honestly be represented as a clean full-suite run in this environment. The project correctly declares the missing runtime dependencies in `requirements.txt`, and CI installs that file before running pytest.

The sandbox also lacks the Docker CLI and has no installed frontend `node_modules`. `npm ci` timed out because package-registry network access is unavailable, so a fresh Vite build and real Docker startup were not claimed as verified.

## Remaining warnings / limitations

1. Live Docker startup was not possible in this environment.
2. Real Gluetun VPN tunnel establishment was not tested with real credentials.
3. Real qBittorrent API login/download/seeding behavior was not tested against a live instance.
4. Real Jellyfin API/playback/transcoding behavior was not tested against a live instance.
5. Real Tdarr/EPG/FlareSolverr/Ollama sidecar communication was not tested.
6. PostgreSQL runtime behavior was not exercised; migrations were validated on SQLite.
7. Dependency vulnerability scanning requires network access or a populated advisory cache.
8. Image freshness/security of third-party container tags should be reviewed during release/update operations; this audit did not silently retag working services.

## Files modified in this audit

- `app/main.py`
- `tests/conftest.py`
- `PRODUCTION_AUDIT_REPAIR_FINAL.md`
