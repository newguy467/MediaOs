# MediaOS Next — Architecture

## The core idea

**One application, modular services.** MediaOS Next is a single FastAPI control plane with a custom React UI that absorbs the entire \*arr ecosystem natively. It does **not** run separate Sonarr, Radarr, Lidarr, Readarr, Bazarr, or Prowlarr binaries, and it does **not** link to their web UIs. Everything the user needs lives inside MediaOS.

Supporting infrastructure — streaming, downloading, VPN, transcoding, persistence — stays in dedicated containers, glued together by Docker Compose and orchestrated by MediaOS. This is deliberate: one user experience does not mean one process or one container.

* * *

## Container topology

```
                     ┌──────────────────────────────────┐
                     │         Docker Network           │
                     │                                  │
   :8787  ──────────►│  mediaos (FastAPI control plane) │
                     │  592 routes · 45 routers         │
                     │  75 services · React UI          │
                     └───┬──────┬──────┬──────┬────┬────┘
                         │      │      │      │    │
                    ┌────▼──┐ ┌─▼──┐ ┌─▼────┐ │  ┌─▼──────────┐
                    │postgres│ │redis│ │jellyfin│ │  │ gluetun    │
                    │  :5432 │ │:6379│ │ :8096 │ │  │ VPN gateway│
                    └───────┘ └────┘ └───────┘ │  │ control:8000│
                                                │  └─────┬──────┘
                                                │        │
                                          ┌─────▼────┐   │
                                          │qbittorrent│  │
                                          │  (via     │  │
                                          │  gluetun) │  │
                                          └──────────┘   │
                                     network_mode: service:gluetun
                                       (kill-switch enforced)
```

### Always-on core (6 containers)

| Service | Image | Role | Port |
| --- | --- | --- | --- |
| `mediaos` | `ghcr.io/newguy467/mediaos:next` | Control plane + UI (the app) | 8787 |
| `mediaos-db` | `postgres:16.14-alpine` | Primary database | 5432 |
| `redis` | `redis:7.4-alpine` | Queues, rate-limit, leader election | 6379 |
| `jellyfin` | `lscr.io/linuxserver/jellyfin:10.10.3` | Streaming & playback backend | 8096 |
| `qbittorrent` | `lscr.io/linuxserver/qbittorrent:5.0.4` | Download engine (routed through VPN) | 8080, 6881 |
| `gluetun` | `qmcgaw/gluetun:v3.41.3` | VPN gateway + kill-switch | 8000 (ctrl) |

### Optional (Docker Compose profiles)

| Service | Profile | Role |
| --- | --- | --- |
| `tdarr` | `tdarr` / `full` | Hardware transcoding farm |
| `iptv-org-epg` | `epg` / `full` | Live TV EPG grabber (iptv-org) |
| `flaresolverr` | `flaresolverr` / `full` | Cloudflare bypass for indexers |
| `ollama` | `ai` / `full` | Local LLM for AI-assisted features |

Launch optional services with `docker compose --profile tdarr up -d` (or `--profile full` for everything).

* * *

## The MediaOS control plane

MediaOS is a FastAPI application (`app/main.py`, 592 routes across 45 routers). On startup it:

1.  Runs **Alembic migrations** to `head` (7 versioned migrations)
2.  Calls `Base.metadata.create_all()` as a safety net for any new models
3.  Bootstraps background scheduler (APScheduler) for hunt, indexer health, quality sync, and maintenance rules
4.  Seeds built-in indexers, quality profiles, and Live TV channels if missing

### What MediaOS absorbs (no separate \*arr needed)

| \*arr replaced | MediaOS implementation |
| --- | --- |
| **Sonarr** | `routers/tv.py`, `services/tv.py` — series, seasons, episodes, monitoring, season packs, interactive search |
| **Radarr** | `routers/movies.py`, `services/movies.py` — movies, quality profiles, upgrades, collections |
| **Lidarr** | `routers/music.py`, `services/music.py` — artist→album→track hierarchy, MusicBrainz, completeness |
| **Readarr** | `routers/books.py`, `routers/audiobooks.py` — books & audiobooks |
| **Bazarr** | `routers/subtitles.py`, `services/subtitles.py` — multi-language subtitle search & upgrade |
| **Prowlarr** | `routers/indexers.py`, `services/indexers.py` — Torznab, Cardigann YAML, built-ins, rate-limit registry |
| **Jellyseerr** | `routers/requests.py`, `routers/discover.py` — request flow + trending discover |
| **Maintainerr** | `routers/maintenance.py`, `services/maintenance.py` — cleanup rules |
| **Recyclarr** | `services/quality.py`, `routers/quality.py` — live TRaSH sync, custom formats, scores |

### The shared pipeline (core services)

All media types flow through the same pipeline:

```
Add/Request → Metadata fetch → Monitor → Hunt/Search indexers
  → Quality score + custom format filter → Grab (qBittorrent via VPN)
  → Download complete → Import to library (hardlink) → Rename
  → Notify → Jellyfin scans → Stream
```

Shared services (`app/services/`):

-   **Metadata providers** — TMDb, TVDb, MusicBrainz, ComicVine, IGDB, OpenLibrary
-   **Search + Interactive Search** — release parsing, score ranking
-   **Quality Engine** — live TRaSH Guides, custom formats, quality definitions
-   **Grab** — sends to qBittorrent (or SABnzbd / NZBGet / Transmission / Deluge)
-   **Wanted / Hunt** — aggressive missing / cutoff / upgrade search
-   **Naming** — per-media-type naming templates
-   **Subtitles** — multi-language search & upgrade
-   **Maintenance** — rule engine (age, size, quality, tags → action)
-   **Activity & Notifications** — Apprise, Discord, full audit log
-   **Rate-limit registry** — per-host limits, backoffs, current state
-   **VPN monitoring** — Gluetun status, kill-switch, country verification

### Persistence

-   **PostgreSQL 16** (default in Docker) — `media_items`, `episodes`, `tracks`, `issues`, `quality_*`, `downloads`, `activity`, `rules`, `stream_links`, `users`, `indexers`, `channels`, `games`, `tracked_items`, …
-   **Redis** — job queues, rate-limit state, leader election (multi-instance)
-   **SQLite** — supported for local dev / testing (the app auto-detects dialect; migrations handle SQLite's `batch_alter_table` limitations)

Schema is managed by **Alembic** (7 migrations). The app runs `alembic upgrade head` on startup, then `create_all()` as a fallback.

* * *

## The React UI

The frontend is a **custom** React + Vite + Tailwind + DaisyUI application (not a Homepage-style dashboard). It is pre-built into `app/static/` and served by FastAPI.

-   **Theme:** `data-theme="mediaos"` — dark purple/neon identity
-   **Layout:** left navigation sidebar (MediaOS logo + Movies / TV / Music / Books / Audiobooks / Comics / Discover / Queue / Settings) with a top search bar (`⌘K` global search)
-   **Routing:** React Router with 55+ lazy-loaded page chunks
-   **Streaming:** hls.js bundled for Live TV / IPTV playback
-   **Communication:** REST + SSE to the MediaOS backend only — the UI never contacts Jellyfin, qBittorrent, or Gluetun directly

Rebuild from source (optional — the pre-built bundle ships in the image):

```bash
cd ui/ && npm install && npm run build && cp -r dist/* ../app/static/
```

* * *

## VPN kill-switch architecture

This is a critical safety feature. Download traffic must never leak your real IP.

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Indexer  │────►│ MediaOS  │────►│qBittorrent│────►│ Gluetun  │──►VPN──►Internet
│  query   │     │  (grab)  │     │(no direct │     │ (tunnel) │
└──────────┘     └──────────┘     │  egress)  │     └──────────┘
                                  └──────────┘
                                  network_mode: service:gluetun
```

-   **qBittorrent** uses `network_mode: "service:gluetun"`, which means it shares Gluetun's network namespace. It has no network interface of its own.
-   If Gluetun's tunnel drops, qBittorrent loses **all** connectivity — downloads stall, nothing leaks. This is the kill-switch.
-   **MediaOS** talks to qBittorrent via `QBIT_URL=http://gluetun:8080` (through Gluetun's published port, not qBittorrent directly).
-   **MediaOS** monitors Gluetun's control server (`/v1/publicip` / `/v1/status`) and reports VPN status + expected country in the UI. If the public IP doesn't match the VPN exit country, MediaOS flags it.
-   The qBittorrent Web UI and torrent ports are published **through Gluetun**'s port mappings, preserving the kill-switch invariant.

See [docs/VPN-SETUP.md](docs/VPN-SETUP.md) for credential configuration.

* * *

## Path consistency & hardlinks

MediaOS, Jellyfin, and qBittorrent mount the **same host directories** to the **same in-container paths**:

| Host var (`MOVIES_PATH`) | Container path | Mounted in |
| --- | --- | --- |
| `${MOVIES_PATH}` | `/movies` | MediaOS, Jellyfin, qB |
| `${TV_PATH}` | `/tv` | MediaOS, Jellyfin, qB |
| `${MUSIC_PATH}` | `/music` | MediaOS, Jellyfin |
| `${BOOKS_PATH}` | `/books` | MediaOS, Jellyfin |
| `${AUDIOBOOKS_PATH}` | `/audiobooks` | MediaOS, Jellyfin |
| `${COMICS_PATH}` | `/comics` | MediaOS, Jellyfin |
| `${MANGA_PATH}` | `/manga` | MediaOS, Jellyfin |
| `${PODCASTS_PATH}` | `/podcasts` | MediaOS, Jellyfin |
| `${YOUTUBE_PATH}` | `/youtube` | MediaOS, Jellyfin |
| `${GAMES_PATH}` | `/games` | MediaOS, Jellyfin |
| `${ADULT_PATH}` | `/adult` | MediaOS, Jellyfin |
| `${DOWNLOADS_PATH}` | `/downloads` | MediaOS, qBittorrent |

Because downloads and libraries are on the same filesystem and same paths, MediaOS imports via **hardlinks** — instant, zero-copy, no duplicate disk usage. See [docs/HARDLINKS.md](docs/HARDLINKS.md).

* * *

## Operational hardening

Every core service in `docker-compose.yml` includes:

-   **Healthcheck** — `mediaos` (curl `/api/health`), `mediaos-db` (pg\_isready), `redis` (redis-cli ping), `gluetun` (curl control server), `jellyfin` (curl `/Health`), `qbittorrent` (curl Web UI)
-   **Restart policy** — `unless-stopped` on all services
-   **`no-new-privileges:true`** — prevents container privilege escalation
-   **Log rotation** — `json-file` driver, `max-size: 10m`, `max-file: 3`
-   **Resource limits** — `mem_limit` and `cpus` per service (configurable in `.env`)
-   **Dependency ordering** — `mediaos` depends on `mediaos-db` (healthy), `redis` (healthy), `gluetun` (healthy), `qbittorrent` (started), `jellyfin` (started) — it won't start until infrastructure is ready
-   **Gluetun capabilities** — `cap_add: NET_ADMIN`, `device: /dev/net/tun` (VPN tunnel requires these)

* * *

## Configuration

All configuration flows through `.env` (see `.env.example`). The app's `Settings` class (`app/config.py`) maps environment variables to typed Pydantic v2 fields. Key categories:

-   **Docker Compose infrastructure** — `PUID`, `PGID`, `TZ`, ports, resource limits, image tags, host paths (`MOVIES_PATH`, etc.)
-   **Database** — `POSTGRES_USER`, `POSTGRES_PASSWORD` (required), `POSTGRES_DB`, `DATABASE_URL`
-   **Redis** — `REDIS_URL`
-   **VPN** — `VPN_ENABLED`, `VPN_KILL_SWITCH`, `VPN_TYPE`, `VPN_SERVICE_PROVIDER`, `VPN_WIREGUARD_PRIVATE_KEY`, `VPN_WIREGUARD_ADDRESSES`, `VPN_WIREGUARD_PRESHARED_KEY`, `VPN_USERNAME`, `VPN_PASSWORD`, etc.
-   **qBittorrent** — `QBIT_URL`, `QBIT_USERNAME`, `QBIT_PASSWORD`
-   **Jellyfin** — `JELLYFIN_URL`, `JELLYFIN_API_KEY`, `JELLYFIN_PUBLISHED_URL`
-   **Metadata providers** — `TMDB_API_KEY`, `TVDB_API_KEY`, `MUSICBRAINZ_*`, `COMICVINE_API_KEY`, `IGDB_CLIENT_ID` / `IGDB_CLIENT_SECRET`
-   **Indexers** — `INDEXER_HEALTH_ENABLED`, etc.
-   **Quality** — TRaSH sync settings, custom format defaults
-   **Notifications** — `APPRISE_URL`, `DISCORD_WEBHOOK_URL`
-   **Adult** — `ADULT_PASSCODE_ENABLED`, `ADULT_PASSCODE_HASH`, library path

No secrets are hard-coded in `docker-compose.yml` or `.env.example`. Run `bash scripts/generate_secrets.sh` to populate `POSTGRES_PASSWORD` and `AUTH_API_KEY` with strong random values.

* * *

## Testing

The test suite (57 tests) runs without external services (uses SQLite + local fallbacks):

```bash
python3 -m pytest tests/ -v
```

Coverage:

-   `test_compose_architecture.py` — service presence, VPN kill-switch (7 tests), path consistency, service config (healthchecks, restart, security, log rotation), `.env.example` completeness (9 tests)
-   `test_audit_smoke.py` — app imports, auth gate, key endpoints
-   `test_games_scrobble_smoke.py` — games / scrobbling / tracking routers + version consistency
-   `test_redis_leader.py` — rate-limit local backend, leader election without Redis, job wrapper execution