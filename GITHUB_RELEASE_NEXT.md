# MediaOS Next

**Tag:** `1.00beta`
**Codename:** MediaOS Next
**Date:** 2026-08-14

> **One application. One user experience. Modular services underneath.**

MediaOS Next is a complete rebuild of the MediaOS architecture. Instead of stitching together a dashboard that links to seven separate \*arr web UIs, MediaOS Next is a **single unified application** — a custom FastAPI control plane with its own React interface — that **absorbs** Sonarr, Radarr, Lidarr, Readarr, Bazarr, and Prowlarr functionality natively. You manage movies, TV, music, books, audiobooks, comics, Live TV, podcasts, and games from one place, and you never open a separate \*arr web UI again.

## Highlights

- **One FastAPI control plane** — 592 routes, 45 routers, 75 services implementing what the \*arr ecosystem does as separate binaries.
- **Custom React UI** (Vite + Tailwind + DaisyUI) with a dark purple/neon theme, left sidebar, and global search (`⌘K`). No Homepage-style dashboard linking — MediaOS **is** the UI.
- **Unified Docker Compose** — the standalone stack merged with the VPN kill-switch pattern into one cohesive file. 10 services, 10 volumes.
- **VPN kill-switch** — qBittorrent uses `network_mode: service:gluetun`, sharing Gluetun's network namespace. If the tunnel drops, qBittorrent loses all connectivity. No traffic can leak. MediaOS reports VPN status in the UI.
- **Production hardening** — `no-new-privileges:true`, log rotation, resource limits, restart policies, healthchecks on all core services, dependency ordering with health conditions.
- **Path consistency & hardlinks** — MediaOS, Jellyfin, and qBittorrent mount the same host directories to the same in-container paths, enabling instant zero-copy hardlink imports.
- **57 tests passing** (was 15), including 42 new compose-architecture tests.

## What it replaces

| You used to run… | MediaOS Next does it natively |
| --- | --- |
| Sonarr | TV series, seasons, episodes, season packs, monitoring |
| Radarr | Movies, quality profiles, upgrades, collections |
| Lidarr | Music artist → album → track, MusicBrainz, completeness |
| Readarr | Books & audiobooks |
| Bazarr | Multi-language subtitle search & upgrade |
| Prowlarr | Indexers — Torznab, Cardigann YAML, built-ins |
| Jellyseerr / Overseerr | Request system + discover trending |
| Maintainerr | Cleanup / maintenance rule engine |
| Recyclarr | Live TRaSH sync, custom formats, scores |
| Homepage / Organizr | Not needed — MediaOS is the UI |

## What changed from the reference project (v2.0.27-dev)

### Architecture
- Unified `docker-compose.yml` merged the standalone stack with the VPN kill-switch pattern.
- Redis made always-on (was profile-gated) — required for queues and leader election.
- All core services have healthchecks, including Jellyfin (was missing).
- Production hardening across the board (see Highlights).
- `.env.example` expanded with all Docker Compose infrastructure and host-path variables.

### Bug fixes
- **Alembic migration 0007 SQLite bug** — `batch_alter_table` on SQLite triggered `ValueError: Constraint must have a name`. Fixed with raw `ALTER TABLE` SQL for SQLite while keeping `batch_alter_table` for PostgreSQL.
- **Stale version string** — `dashboard_widgets.py` referenced `2.0.20-dev` while the rest used `2.0.27-dev`. Standardized to `1.00beta`.
- **Missing `.gitignore`** — created comprehensive `.gitignore` to prevent committing `.env` secrets, databases, and build artifacts.

### Version
Bumped from `2.0.27-dev` → `1.00beta` across all files (VERSION, Dockerfile, version.py, main.py, dashboard_widgets.py, plugins.py, example compose files, tests). The health endpoint now reports `version: 1.00beta`.

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
| .gitignore | Present |
| No old version refs | 0 remaining in code |
| No committed .env | Confirmed |
| Python syntax | All files compile |

## Quick start

```bash
cp .env.example .env
bash scripts/generate_secrets.sh
# Edit .env: set library paths, VPN credentials, TMDB_API_KEY, TZ
docker compose up -d
# Open http://localhost:8787
```

See [README.md](README.md) for full instructions, [ARCHITECTURE.md](ARCHITECTURE.md) for the architecture breakdown, and [docs/VPN-SETUP.md](docs/VPN-SETUP.md) for the VPN kill-switch configuration.

---

**Full release notes:** [RELEASE_NOTES_NEXT.md](RELEASE_NOTES_NEXT.md)
