# MediaOS Next — Release Notes

**Version:** `1.00beta`  
**Date:** 2026-08-14  
**Codename:** MediaOS Next

* * *

## What this is

MediaOS Next is a complete rebuild of the MediaOS architecture. It replaces the old "dashboard linking to separate \*arr containers" approach with a **unified application** — a single FastAPI control plane with a custom React UI that absorbs all \*arr functionality natively.

**One user experience. Modular services underneath.**

* * *

## Architecture

### The control plane (one app)

MediaOS is a FastAPI application (592 routes, 45 routers, 75 services) that implements — natively, in its own codebase — what Sonarr, Radarr, Lidarr, Readarr, Bazarr, Prowlarr, Jellyseerr, Maintainerr, and Recyclarr each do as separate applications. The user manages everything from one UI and never leaves MediaOS.

### Supporting containers (modular)

| Container | Role |
| --- | --- |
| `mediaos` | Control plane + UI (the app) |
| `mediaos-db` | PostgreSQL 16 (primary database) |
| `redis` | Redis 7.4 (queues, rate-limit, leader) |
| `jellyfin` | Streaming & playback backend |
| `qbittorrent` | Download engine (through VPN) |
| `gluetun` | VPN gateway + kill-switch |
| `tdarr` | Optional transcoding (profile: tdarr) |
| `iptv-org-epg` | Optional EPG grabber (profile: epg) |
| `flaresolverr` | Optional CF bypass (profile: flaresolverr) |
| `ollama` | Optional local LLM (profile: ai) |

### VPN kill-switch

qBittorrent uses `network_mode: service:gluetun`, sharing Gluetun's network namespace. If the VPN tunnel drops, qBittorrent loses all connectivity — no traffic can leak. MediaOS monitors Gluetun's control server and reports VPN status in the UI.

### Path consistency & hardlinks

MediaOS, Jellyfin, and qBittorrent mount the same host directories to the same in-container paths, enabling instant zero-copy hardlink imports.

* * *

## What changed from the reference project (v2.0.27-dev)

### Architecture changes

-   **Unified docker-compose.yml** — merged the standalone stack (qBittorrent + Jellyfin) with the VPN kill-switch pattern (Gluetun) into one cohesive file
-   **Redis made always-on** (was profile-gated) — required for queues and leader election
-   **All core services have healthchecks** — including Jellyfin (was missing)
-   **Production hardening** — `no-new-privileges:true`, log rotation (json-file 10m×3), resource limits (mem\_limit, cpus), restart policies, dependency ordering with health conditions on all services
-   **`.env.example` expanded** — added Docker Compose infrastructure variables (PUID, PGID, TZ, ports, resource limits) and Docker host-path variables (MOVIES\_PATH, TV\_PATH, etc.) that the compose file references

### Bug fixes

-   **Alembic migration 0007 SQLite bug** — `batch_alter_table` on SQLite triggered `ValueError: Constraint must have a name` due to unnamed FK constraints. Fixed by using raw `ALTER TABLE ADD COLUMN` SQL for SQLite while keeping `batch_alter_table` for PostgreSQL.
-   **Stale version string** — `dashboard_widgets.py` referenced `2.0.20-dev` while the rest of the app used `2.0.27-dev`. Standardized to `1.00beta`.
-   **Missing `.gitignore`** — created comprehensive .gitignore to prevent committing `.env` secrets, databases, and build artifacts.

### Version

-   Bumped from `2.0.27-dev` → `1.00beta` across all files (VERSION, Dockerfile, version.py, main.py, dashboard\_widgets.py, plugins.py, example compose files, tests). The health endpoint now reports `version: 1.00beta`.

### Documentation

-   **README.md** — completely rewritten for MediaOS Next (unified architecture, quick start, feature list, project structure, design principles)
-   **ARCHITECTURE.md** — completely rewritten (container topology, control plane breakdown, VPN kill-switch diagram, path consistency, operational hardening)
-   **docs/VPN-SETUP.md** — new file (Gluetun kill-switch configuration, WireGuard/OpenVPN setup, verification, troubleshooting)

### Testing

-   **57 tests pass** (was 15) — added `test_compose_architecture.py` with 42 new tests covering:
    -   Service presence (all 6 core + 4 optional)
    -   VPN kill-switch (7 tests: network\_mode, dependencies, healthcheck, capabilities, env vars)
    -   Path consistency (library paths MediaOS↔Jellyfin, downloads MediaOS↔qB)
    -   Service config (restart policies, healthchecks, no-new-privileges, dependencies, log rotation)
    -   .env.example completeness (9 tests: all required vars, no hardcoded secrets)

* * *

## Verification results

| Check | Result |
| --- | --- |
| App imports | 592 routes register |
| Test suite | 57/57 pass |
| Docker Compose | 10 services, 10 volumes, valid |
| VPN kill-switch | `network_mode: service:gluetun` |
| Core healthchecks | All 6 present |
| Alembic migrations | 7/7 applied (SQLite + Postgres) |
| UI static assets | 81 files (index, CSS, JS, hls) |
| .env.example | 293 vars, no hardcoded secrets |
| Version consistency | `1.00beta` everywhere |
| .gitignore | Present (55 lines) |
| No old version refs | 0 remaining in code |
| No committed .env | Confirmed |
| Python syntax | All files compile |

* * *

## Quick start

```bash
cp .env.example .env
bash scripts/generate_secrets.sh
# Edit .env: set library paths, VPN credentials, TMDB_API_KEY, TZ
docker compose up -d
# Open http://localhost:8787
```

See [README.md](README.md) for full instructions.