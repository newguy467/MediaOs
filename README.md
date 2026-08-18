# MediaOS Next — The Unified Media & Games Operating System

**One application. One user experience. Modular services underneath.**

MediaOS Next is a complete rebuild of the MediaOS vision. Instead of stitching together a dashboard that links to seven separate \*arr web UIs, MediaOS Next is a single unified application — a custom FastAPI control plane with its own React interface — that **absorbs** Sonarr, Radarr, Lidarr, Readarr, Bazarr, and Prowlarr functionality natively. You manage movies, TV, music, books, audiobooks, comics, Live TV, podcasts, and games from one place.

> **One user experience does not mean one process or one container.** MediaOS is the brain (control plane + UI). Jellyfin streams, qBittorrent downloads, Gluetun tunnels, Tdarr transcodes, Redis and Postgres persist. Each supporting service stays in its own container, glued together by Docker Compose, and orchestrated by MediaOS.

* * *

## What MediaOS Next replaces

| You used to run… | MediaOS Next does it natively |
| --- | --- |
| Sonarr | TV series management, season packs, episode monitoring |
| Radarr | Movie management, quality profiles, upgrades |
| Lidarr | Music artist → album → track hierarchy |
| Readarr | Books & audiobooks management |
| Bazarr | Subtitle search, languages, upgrade logic |
| Prowlarr | Indexer management (Torznab / Cardigann / built-ins) |
| Jellyseerr / Overseerr | Request system + discover trending |
| Maintainerr | Cleanup / maintenance rules |
| Homepage / Organizr dashboard | Not needed — MediaOS **is** the UI |

The supporting services you still run, now as dedicated containers:

-   **Jellyfin** — streaming & playback backend (MediaOS talks to it via API)
-   **qBittorrent** — the download engine (MediaOS controls & monitors it)
-   **Gluetun** — VPN gateway with a kill-switch (qBittorrent is routed through it)
-   **Tdarr** — optional hardware transcoding farm (profile: `tdarr` or `full`)
-   **Postgres** — primary database (always-on)
-   **Redis** — queues, rate-limit registry, leader election (always-on)

* * *

## Architecture at a glance

```
┌─────────────────────────────────────────────────────────────┐
│  Browser  →  MediaOS UI (React + Vite + Tailwind + DaisyUI)  │
│  Dark purple/neon theme · left sidebar · global search ⌘K   │
└──────────────────────────────┬──────────────────────────────┘
                               │ REST + SSE (no direct access to
                               │   external services from the UI)
┌──────────────────────────────▼──────────────────────────────┐
│  MediaOS FastAPI Control Plane (one app, 592 routes)         │
│  • Movies / TV / Music / Books / Audiobooks / Comics / Games │
│  • Indexers · Quality profiles · Release search · Grab       │
│  • Wanted / Hunt · Queue · History · Failed downloads        │
│  • Naming · Metadata · Subtitles · Live TV / DVR / EPG       │
│  • VPN status & kill-switch monitoring · Activity · Calendar │
└──────┬───────────┬───────────┬───────────┬───────────┬───────┘
       │           │           │           │           │
   ┌───▼───┐   ┌──▼───┐    ┌───▼────┐  ┌──▼────┐  ┌──▼──────┐
   │Postgres│   │Redis │    │Jellyfin│  │ qBitt  │  │ Gluetun │
   │  (DB)  │   │(queue)│   │(stream)│  │(download)│ │(VPN gw)│
   └────────┘   └──────┘    └────────┘  └───┬────┘  └────▲────┘
                                            │            │
                                  network_mode: service:gluetun
                                       (kill-switch: no VPN = no downloads)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full breakdown.

* * *

## Quick start (Docker Compose)

### 1\. Clone & configure

```bash
git clone <your-repo-url> mediaos-next
cd mediaos-next

# Copy the environment template
cp .env.example .env

# Generate required secrets (Postgres password + auth API key)
bash scripts/generate_secrets.sh
```

`generate_secrets.sh` writes strong random values into `.env` for `POSTGRES_PASSWORD` and `AUTH_API_KEY`. Edit `.env` to set:

-   **Library host paths** — `MOVIES_PATH`, `TV_PATH`, `MUSIC_PATH`, … (point at your storage; container target paths like `/movies` stay fixed for hardlinks)
-   **VPN credentials** — `VPN_SERVICE_PROVIDER`, `VPN_WIREGUARD_PRIVATE_KEY` (or OpenVPN `VPN_USERNAME` / `VPN_PASSWORD`), `VPN_WIREGUARD_ADDRESSES`, `VPN_WIREGUARD_PRESHARED_KEY`
-   **qBittorrent** — `QBIT_USERNAME`, `QBIT_PASSWORD`
-   **Metadata keys** — `TMDB_API_KEY` (and optional `TVDB_API_KEY`)
-   **Timezone** — `TZ` (e.g. `America/New_York`)

> **VPN is on by default.** qBittorrent is routed through Gluetun. If the VPN tunnel drops, qBittorrent loses connectivity (kill-switch) and MediaOS reports the VPN failure in the UI. See [docs/VPN-SETUP.md](docs/VPN-SETUP.md).

### 2\. Launch the stack

```bash
# Core stack (MediaOS + Postgres + Redis + Jellyfin + qBittorrent + Gluetun)
docker compose up -d

# With optional Tdarr transcoding farm
docker compose --profile tdarr up -d

# Full stack (Tdarr + EPG + FlareSolverr + Ollama)
docker compose --profile full up -d
```

### 3\. Open MediaOS

Navigate to **[http://localhost:8787](http://localhost:8787)** (or your `MEDIAOS_HOST_PORT`).

The first-run wizard will guide you through:

1.  **Admin account** — username / password
2.  **Libraries** — Movies & TV required; toggle Music, Books, Audiobooks, Comics, Manga, Podcasts, YouTube, Games, Adult (Adult needs a PIN)
3.  **Indexers** — Cardigann / built-in indexers seed automatically; add private tracker Torznab feeds as needed
4.  **Quality profiles** — TRaSH Guide packs are bundled; customize scores & custom formats
5.  **qBittorrent** — already connected via Gluetun if you set credentials in `.env`; verify in Settings → Downloads
6.  **Jellyfin** — already mounted with identical library paths; connect in Settings → Integrations

Then: **Discover → add media → MediaOS searches indexers → grabs via qBittorrent (through VPN) → imports to library → Jellyfin streams it.**

### Windows: use the Control Panel instead

On Windows, double-click **`Start-MediaOS.bat`** for a GUI control panel
(start/stop/restart, open the UI, health check, live logs, backup,
update, edit `.env`) instead of typing `docker compose` commands. See
`MediaOS-Guide.html` (or **`Open-MediaOS-Guide.bat`**) for a walkthrough,
and `scripts/panel/README.md` for what each button runs. Building from
source on Windows instead? See `scripts/windows/dashboard.bat`.

* * *

## What's inside MediaOS (102 features)

The `/api/health` endpoint reports the live feature list. Highlights:

-   **Movies / TV** — add, monitor, interactive search, grab, import, upgrade, naming, metadata (TMDb / TVDb), calendar, collections
-   **Music** — artist → album → track hierarchy, MusicBrainz, completeness %
-   **Books & Audiobooks** — author → book, Readarr-style management
-   **Comics & Manga** — weekly pull-lists, story arcs, reading order, ComicVine
-   **Live TV / DVR** — iptv-org seed, channel editor, EPG grid, HLS playback (hls.js), virtual channels, portal scan
-   **Games** — IGDB-backed search, grab, queue, local scrobbling
-   **Indexers** — Torznab, Cardigann YAML, curated built-ins, rate-limit registry
-   **Quality engine** — live TRaSH Guides sync, custom formats, scores, profiles
-   **Wanted / Hunt** — aggressive missing / cutoff / upgrade search with rate-limit awareness and prioritization
-   **Queue & History** — downloads, failed downloads, retry, cooldown
-   **Subtitles** — Bazarr-style multi-language search & upgrade
-   **Maintenance** — Maintainerr-style rules (age, size, quality, tags, collections)
-   **Requests** — Jellyseerr-style request flow for multi-user
-   **VPN monitoring** — Gluetun status, kill-switch enforcement, country check
-   **Notifications** — Apprise, Discord webhooks
-   **Multi-user** — roles & permissions, adult PIN gate
-   **Module Store** — opt-in advanced modules (games, scrobbling, tracking)
-   **Activity log** — every grab, import, search, notification tracked

* * *

## Project structure

```
mediaos-next/
├── docker-compose.yml          # Unified stack: MediaOS + supporting containers
├── .env.example                # All configurable vars (no hard-coded secrets)
├── scripts/
│   └── generate_secrets.sh     # Generates POSTGRES_PASSWORD + AUTH_API_KEY
├── app/
│   ├── main.py                 # FastAPI app — 592 routes, startup migrations
│   ├── config.py               # Pydantic v2 Settings (385-line env mapping)
│   ├── routers/                # 45 API routers (movies, tv, music, livetv, …)
│   ├── services/               # 75 services (vpn, quality, hunt, metadata, …)
│   ├── models/                 # SQLAlchemy 2.0 models (Postgres + SQLite)
│   └── static/                 # Pre-built React UI (dark purple/neon theme)
├── alembic/                    # 7 versioned migrations
├── tests/                      # 64+ tests (API contracts, route-order, services, compose, smoke)
└── docs/
    ├── VPN-SETUP.md            # Gluetun kill-switch configuration
    ├── QUICKSTART.md           # First 10 minutes
    ├── SETUP.md                # First-run wizard details
    ├── HARDLINKS.md            # Hardlink setup for instant imports
    ├── INDEXERS.md             # Indexer configuration
    ├── LIVETV.md               # Live TV / DVR / EPG
    └── …                       # 30+ topic docs
```

* * *

## Key design principles

1.  **Unified, not glued.** MediaOS implements \*arr features in its own codebase — it does not proxy to separate Sonarr/Radarr binaries. You never leave the MediaOS UI.
2.  **Modular backend.** The control plane is one container; streaming, downloading, VPN, transcoding, and persistence are separate containers. One user experience, many processes.
3.  **Clean API layer.** The React frontend talks only to the MediaOS FastAPI backend. It never reaches Jellyfin, qBittorrent, or Gluetun directly. MediaOS is the single integration point.
4.  **VPN kill-switch.** qBittorrent uses `network_mode: service:gluetun`, so its traffic is physically impossible to leave unencrypted. If Gluetun dies, qBittorrent has no network. MediaOS detects and reports this.
5.  **Consistent paths for hardlinks.** MediaOS, Jellyfin, and qBittorrent all mount the same host directories to the same in-container paths. This enables hardlinks — imports are instant, zero-copy, and don't double disk usage.
6.  **Production-grade ops.** Every core service has a healthcheck, restart policy, log rotation (json-file, 10m × 3), resource limits (mem\_limit, cpus), and `no-new-privileges:true` security.

* * *

## Development

```bash
# Run the test suite (SQLite — no Postgres needed)
export AUTH_REQUIRE=false
pip install -r requirements.txt -r requirements-dev.txt  # once
python3 -m pytest tests/ -q
# or full local CI gate (version + UI static + lazy exports + pytest):
npm run ci:local


### Database in CI / local tests

Pytest defaults to **SQLite** (`DATABASE_URL=sqlite:///...`) so the suite runs without Postgres.
Alembic migrations are exercised against that SQLite DB in CI. For production-like checks, point
`DATABASE_URL` at Postgres and run `alembic upgrade head` (see `docker-compose` for the full stack).

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for `ci:local`, pytest, and optional Playwright E2E.

Post-`1.01beta` changes are tracked under **Unreleased** in [CHANGELOG.md](./CHANGELOG.md).

## E2E (optional)

Browser smokes use Playwright and **skip** unless a live UI is available:

```bash
npm run test:e2e:install   # once: download Chromium
# start MediaOS UI (e.g. docker compose up / npm run dev)
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8787 npm run test:e2e
```

In CI the optional `e2e` job runs only when repository variable `PLAYWRIGHT_BASE_URL` is set.


# Start the app locally (SQLite, no Docker)
DATABASE_URL="sqlite:///./data/dev.db" uvicorn app.main:app --reload --port 8787

# The UI is pre-built in app/static/. To rebuild from source:
npm install && npm run build
```

* * *

## Documentation

-   [ARCHITECTURE.md](ARCHITECTURE.md) — Control plane + supporting containers
-   [docs/VPN-SETUP.md](docs/VPN-SETUP.md) — Gluetun VPN kill-switch
-   [docs/QUICKSTART.md](docs/QUICKSTART.md) — First 10 minutes
-   [docs/SETUP.md](docs/SETUP.md) — First-run wizard
-   [docs/HARDLINKS.md](docs/HARDLINKS.md) — Instant imports via hardlinks
-   [docs/INDEXERS.md](docs/INDEXERS.md) — Indexer configuration
-   [docs/LIVETV.md](docs/LIVETV.md) — Live TV / DVR / EPG
-   [VISION.md](VISION.md) — The full MediaOS vision
-   [SECURITY.md](SECURITY.md) — Security practices

* * *

## License

See [LICENSE](LICENSE). MediaOS re-implements ideas from open-source projects (Sonarr, Radarr, Lidarr, Readarr, Bazarr, Prowlarr, Jellyseerr, Maintainerr, Recyclarr, and others) in its own architecture (FastAPI + SQLAlchemy + React) under the spirit of open source. Attribution appears in the About page.

* * *

**MediaOS Next — absorb everything useful, keep one coherent system.**