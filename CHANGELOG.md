# MediaOS Changelog



## 2.0.27-dev (2026-08-13)

### Fixed (full production audit + repair — second pass)
- **CRITICAL**: `app/services/search.py` called `enrich_many()` 8 times but
  never imported it — every search path (movies, TV, music, books, adult)
  would have raised `NameError` at runtime. Added
  `from app.services.release_enrichment import enrich_many` to the import
  block. (Prior audit report falsely claimed this was fixed; it was not.)
- Removed dead/duplicate VPN config fields that shadowed the correct ones:
  `vpn_killswitch` and `vpn_interface` in `app/config.py` (correct field is
  `vpn_kill_switch`), matching entries in `app/routers/setup.py`
  `WIZARD_FIELDS` and `app/services/app_settings.py` `SETTINGS_GROUPS`.
- Fixed undefined-variable bug in `app/scheduler.py` jackett-sync error
  handler: `exp if False else exc` referenced an undefined `exp` (the
  expression always evaluated to `exc` but the dead `exp` name is a latent
  NameError risk and linter noise). Simplified to `exc`.
- Updated `README.md` version references from stale `2.0.20-dev` to
  `2.0.27-dev`.
- Regenerated `.env.example` with all 254 Settings fields (was missing from
  the distribution).

### Verified (no issues found)
- All 187 Python files compile cleanly
- Runtime import of `app.main` succeeds (54 routes registered)
- 1379 cross-module imports resolve, 0 issues
- 7334 call sites checked, 0 unresolved (1 false-positive plugin hook)
- All 15 pytest tests pass
- 4 JSON + 34 YAML config files parse cleanly
- 0 dangerous patterns (eval/exec/shell=True/os.system/pickle/unsafe-yaml)
- 0 hardcoded secrets or API keys
- Path-traversal protection verified in import_media, converter, backup, unpack
- Docker: no privileged containers, no docker.sock mounts, no-new-privileges
  on all mediaos services, restart: unless-stopped on all, healthchecks present
- VPN kill-switch enforced on all grab paths (grab.py ×3, games.py, announce_lab)
- Redis leader election uses atomic Lua scripts (renew + release)
- Gluetun VPN compose: cap_add NET_ADMIN, /dev/net/tun, healthcheck,
  qbittorrent network_mode service:gluetun with depends_on healthy



## 2.0.26-dev (2026-08-11)

### Fixed (audit session 6 — see docs/AUDIT_2.0.26-dev_IN_PROGRESS.md)
- VPN kill-switch was not enforced on two grab paths (`POST
  /games/{id}/grab-url` manual paste, and the announce-lab/cross-seed
  auto-grab) — both now call `vpn_allows_grabs()` before sending to
  qBittorrent, matching every other grab path
- `game_releases` table schema didn't match the `GameRelease` model
  (missing `edition`, `platform_id`, `quality_score`, `file_path`,
  `installed`) — broke `GET /games/{id}` on every fresh install; new
  alembic migration `20260811_0007` adds the missing columns
- Declared missing `mediaos_redis` named volume in `docker-compose.yml` (redis profile)

## 2.0.25-dev (2026-08-11)

### Multi-worker / HA
- Optional **Redis** (`REDIS_URL`): shared rate-limit/backoff, session access-token cache, scheduler leader election
- `app/services/redis_client.py` — lazy connect, hard fallback to process-local
- `app/services/leader.py` — Redis SET NX leader lock with TTL renewal
- Scheduler jobs wrapped with `_leader_job` so followers no-op
- Compose: `redis` service under profile `redis`
- Docs: `docs/OPS_REDIS_AND_HA.md`

### Maintenance / legal
- NOTICE notes redis-py MIT; definitions GPL attribution retained
- Tests: `tests/test_redis_leader.py`

## 2.0.24-dev (2026-08-11)

### Fixed / completed (remaining audit items)
- LimeTorrents built-in indexer **disabled by default** (opt-in)
- Added `NOTICE` for GPL-2.0 Jackett/Cardigann definition attribution
- CHANGELOG / ARCHITECTURE / STRUCTURE.txt titles refreshed for 2.x
- FILELIST.txt regenerated from live tree
- SQLite alembic downgrade now rebuilds `tracked_items` without additive columns
- Vite `chunkSizeWarningLimit` raised (hls.js size warning quieted)
- GPU compose overlays document healthcheck inheritance from base
- Expanded pytest smoke suite (12 tests): syntax, auth gate, OpenAPI IDs, NOTICE, migration

## 2.0.23-dev (2026-08-11)

### Fixed (production audit)
- Removed duplicate `POST /api/games/from-metadata` handler (OpenAPI duplicate operationId / dead code)
- Wired `AUTH_REQUIRE` into `_auth_enabled()` (false = force open; true = credentials-gated)
- Optional CORS via `CORS_ORIGINS` (empty = same-origin only)
- `docker-compose.yml` missing `/config` and `/app/data` volume mounts (logs/plugins/setup flag were non-persistent)
- Alembic `20260811_0006` SQLite-safe downgrade (FK reflect against missing `media_items`)
- qBittorrent healthcheck on standalone compose

### Security / reliability
- CORS credentials disabled when origins is `*`
- Login rate-limit already present; RLock rate-limit snapshot retained

## 2.0.22-dev (2026-08-11)

### Fixed
- UI build blocker in `ui/src/pages/queue.jsx` (invalid nested ternary in empty-queue branch)
- Merged 2.0.19 critical backend fixes into 2.0.20 UX tree (imports, rate-limit RLock, GuidedStep, discover error handling, adult quality profile kwargs, tracked_items migration)
- Combined Alembic `20260811_0006` migration (tracked_items columns + homelab/tracking_history)
- CI: added `docker-build` job that builds the image on push/PR

### Notes
- scripts/, vite.config.js, tailwind.config.js, postcss.config.js, docker-entrypoint.sh already present from the 2.0.20 UX tree; Docker COPY path is complete
- Version unified to 2.0.22-dev across VERSION, package.json, Dockerfile, compose files, app/version.py

**Date:** 2026-08-11  
**Focus:** Full production audit repair, Live TV channel editor depth, version/schema hygiene  
**Base:** 2.0.19-dev

## Security & reliability
- `docker-compose.vpn.example.yml`: require `POSTGRES_PASSWORD`, stop hardcoding DB credentials in `DATABASE_URL`, pin Gluetun/qB/Postgres/MediaOS tags, healthchecks + `depends_on` conditions, full library volume set
- `docker-compose.integrations.example.yml`: pin FlareSolverr `v3.5.0`, unpackerr/cross-seed tags; replace weak `adminadmin` with `${QBIT_PASSWORD}`; use `${DOWNLOADS_PATH}` instead of absolute `/data/downloads`
- Alembic revision `20260811_0006` for `homelab_links` + `tracking_history` (no longer create_all-only)

## Code quality
- `app/routers/tracking.py`: module docstring placement fixed
- `app/services/homelab_links.py`: marked LEGACY; UI uses HomelabLink model + `/api/homelab/*`

## Live TV (Cinephage-depth editor)
- Multi-select checkboxes, Select all / Clear
- Bulk set group, Enable/Disable selection
- Inline Edit modal (name, group, logo URL, tvg-id)
- Client-side name filter on editor list (includes disabled channels)

## Version
- Bumped to **2.0.20-dev** across VERSION, package.json, package-lock, Dockerfile, compose defaults, app fallbacks

## Notes
- Deployment path remains **Docker** (Compose / Docker Desktop). Native Windows is out of scope.
- Sonarr/Radarr/Lidarr/Readarr/Prowlarr/Jellyseerr roles are absorbed; qBittorrent + Jellyfin remain external companions with shared path mappings.

## Converter / Tdarr (2.0.20-dev patch)
- Native **Tdarr-class** pipeline is first-class: health checks, retries, library auto-seed, pipeline API
- Optional external Tdarr via `docker-compose.tdarr.example.yml` (`--profile tdarr`)
- Soft migration `2.0.20`: `convert_jobs.attempts`, `health_ok`, `health_message`

---

# MediaOS 2.0.19-dev

**Date:** 2026-08-11  
**Focus:** UI/UX correctness, module gating, auth, and settings polish  
**Base:** 2.0.18-dev (mediaos-fix)

This release consolidates the incremental fix packs `fixed-4` … `fixed-13` into a single version bump.

---

## Summary

Sidebar and pages now respect enabled modules (including Games, Homelab, YouTube, Podcasts, Manga, Adult, Live TV, Converter). Auth uses a real login page/modal instead of `prompt()`. Library player, podcasts, queue loading, and settings shells were fixed. Dead `v2.jsx` monolith removed.

---

## Changelog by fix pack (oldest → newest)

### fixed-4 — Sidebar customization / Games visibility
- Games nav item used `mod: null` (always shown); now `mod: 'games'`
- Homelab gated with `mod: 'homelab'`
- Defaults no longer force-enable Games when backend has it off
- Side UI remains customized via Module Store enable/disable

### fixed-5 — First UI audit
- YouTube & Podcasts added to primary nav with proper module gates
- Dashboard Games / DVR / Live TV buttons gated on modules
- Dashboard `games_wanted` / `dvr` widgets filtered when modules off
- Settings hub: Adult & YouTube settings hidden unless modules enabled
- Fixed missing `setAdvancedFlag` import in settings-hub

### fixed-6 — Deep UI audit (runtime breakages)
- Added missing `Ic.Box` icon (Games, Module Store, Plugins, About)
- Lazy-load ConverterGpuWizard, ConverterQueue, ConverterScan, ConverterPresets
- Fixed missing `api` import on settings-config-group and settings-subtitles
- Expanded `PAGE_PATHS` for about, adult, backup, homelab, plugins, requests, tracking, etc.

### fixed-7 — UI/UX product bugs
- Removed **duplicate mobile bottom nav** (kept one fixed bar)
- Library player: `setMiniPlayer({ src, id })` → `{ path, itemId }` (playback worked)
- Library empty-state CTA is tab-aware (Movies/TV/Music/Books)
- Queue: loading state so first fetch is not shown as “empty”
- Bottom nav + sidebar close: `type="button"`, aria labels

### fixed-8 — Deeper runtime / product bugs
- Adult page: import `getAdultUnlock` / `setAdultUnlock` (unlock was throwing)
- Discover: import `getAdultUnlock`; Adult tab gated on module
- Deep links to disabled modules show **ModuleDisabled** + Module Store CTA
- api.js 401 handling improved (later replaced by full login UI)
- Podcasts empty copy made honest; users list response normalized

### fixed-9 — Remaining known gaps
- **v2.jsx** monolith replaced with re-export shim (later removed entirely)
- **Manga page** added (`/api/comics/manga`, tag-manga, sidebar + route)
- **Podcasts**: episode list, sync, download, play/stream via mini player
- **Auth**: LoginModal instead of browser `prompt()`
- Bulk `type="button"` on ~39 files (submit buttons preserved)

### fixed-10 — Module gates + auth concurrency
- Gate Scrobbling, Tracking, Converter (+ GPU/queue/scan/presets) pages
- Shared 401 waiter so concurrent requests share one login
- LoginModal: Escape, success/fail events, less optimistic close
- Podcast stream uses `podcastEpisodeId` (not raw HTTP as `path`)
- Converter DELETE actions require confirm

### fixed-11 — Auth polish
- Dedicated **`/login`** route + LoginPage
- LoginForm modes: `direct` (page) vs `bridge` (401 modal)
- Focus trap, body scroll lock, aria-modal on LoginModal
- Sign in / Sign out in sidebar and mobile topbar
- VPN + Users settings loading skeletons
- **v2.jsx removed** (nothing imported it; split pages already exist)
- Podcasts `?query=` confirmed against backend

### fixed-12 — Clean check + polish
- No critical import/icon/export issues found
- Document title updates with active page
- Setup-incomplete dismissible banner (`setupNeeded` was write-only)

### fixed-13 — Settings shells, auth notice, manga depth
- Config group / Sessions / Wanted subtitles: full skeleton shells
- Soft banner when browsing signed-out (auth still optional for local)
- Manga: MangaDex/ComicVine/All source picker, search-missing, clearer copy

---

## Files touched (high level)

- `ui/src/app.jsx` — shell, sidebar, auth, module gates, banners
- `ui/src/api.js` — 401 shared login waiter
- `ui/src/icons.jsx` — Box icon
- `ui/src/routes.jsx` — paths including login, manga
- `ui/src/pages/manga.jsx` — **new**
- `ui/src/pages/podcasts.jsx` — episodes/player
- `ui/src/pages/library.jsx`, `dashboard.jsx`, `discover.jsx`, `adult.jsx`, `queue.jsx`, `converter.jsx`
- Multiple `settings-*.jsx` — imports, skeletons, gates
- Removed: `ui/src/pages/v2.jsx`

## Upgrade notes

1. Rebuild UI: `npm run build` (or project equivalent) so `app/static` matches `ui/src`.
2. Enable **Games** / **Manga** / etc. in Module Store if those nav items should appear.
3. Auth remains optional until an API returns 401; use **Sign in** or `/login` for a session.

## Version

- Previous: **2.0.18-dev**
- Current: **2.0.19-dev**


---

## 2.0.18-dev — Cinephage themes + logo color

### UI
- **Cinephage DaisyUI theme set** (dark/colorful/light grids in Settings → Themes)
- **Logo always top-left** on every page (PageChrome sticky bar)
- **Logo accent color randomizes on each full refresh** (red / yellow / green / blue / … via hue-rotate)
- Cinephage-style active nav marker + rounded module panels

## 2.0.18-dev — dark mode toggle

### UI
- **ThemeToggle** in sidebar + mobile top bar (sun/moon)
- **Themes** settings page: light/dark switch + DaisyUI theme grid
- Preference stored in `localStorage` (`mediaos-theme`)
- Light themes get CSS overrides so forced dark styles do not crush them

## 2.0.18-dev — fix pass (logo, imports, build)

### Fixes
- **Logo**: official MediaOS mark on splash + sidebar (`logo-icon.png`, `logo-full.png`)
- **UI imports**: pages/components used `./icons.jsx` / `./storage.js` (broken) → `../`
- **Missing build files**: restored `vite.config.js`, `tailwind.config.js`, `ui/index.html`
- **JSX corruption**: games/tracking/scrobbling loading blocks; media.jsx duplicate className
- **Docker**: copies full Vite static output including public logos

## 2.0.18-dev — 2026-08-10

## 2.0.18-dev — settings split, Live TV advanced gates, lib skeletons

### UI
- **Settings** fully split: sessions, config-group, subtitles, wanted-subtitles, hub, vpn, users — `settings.jsx` is a thin barrel
- **Live TV** power actions (health check, iptv-org resync, install logos) only in Advanced mode
- **Movies / TV** first-paint **SkeletonLoader** via `libLoading` from App until library lists resolve


## 2.0.18-dev — UI density & loaders pass

### UI
- **SkeletonLoader** component for first-paint loading (grid + table)
- Games / Scrobbling / Tracking use skeletons instead of plain text
- **Stream** on interactive results always available when URL/magnet present (not only with mediaItemId)
- Live TV **basic mode**: Virtual Channels tab hidden unless Advanced is on
- Library player, Smart lists, Podcasts, YouTube redesigned with LibraryModuleShell + TeachEmpty
- Settings: Vpn + Users extracted to `settings-vpnsettingspage.jsx` / `settings-userspermissionspage.jsx` (hub remains)


## 2.0.18-dev — UI consistency pass

### UI / UX
- Games, Scrobbling, Tracking rewritten to **LibraryModuleShell** + **TeachEmpty** (Movies language)
- Silent `.catch(() => {})` reduced on user-visible loads (msg / console.warn)
- TV list search-missing errors now surface via setMsg; Stream already on series detail
- Split remaining `v2.jsx` pages: homelab, backup, plugins, widgets, external-arr
- Empty states on Games/Scrobbling/Tracking include primary CTAs
- Live TV / Quality already use advanced gating hooks

### Follow-ups
- Full Settings split, deeper Live TV basic-mode panels, skeleton loaders


### Major polish / overhaul (audit follow-up)

- **Maintenance rules** — real evaluator (age, quality score, has_file, series_status, monitored); actions `notify` / `unmonitor`; dry-run by default; API `/api/library/maintenance/*`; scheduler every 12h
- **Tracking** — `media_type` filter via join; list returns title + media_type
- **Games** — clear message when IGDB keys missing (no fake "stub" results)
- **Collections UI** — thicker search/track/progress/detail
- **Plugin hooks** — `organize_episode` added
- **Docs** — `docs/REQUIRED_KEYS.md`
- **Smoke** — `scripts/smoke_store_and_core.py`
- **UI** — fixed double `function Xfunction X` corruptions in v2 pages
- **Catalog** — left in place for later `plugin_registry_url`; notes clarify placeholders + bundled hello

## 2.0.17-dev — 2026-08-10

### Plugin store completion
- **Enable/disable** installed plugins without uninstall (`enabled` in manifest; skipped on load)
- **Update available** badge when catalog version > installed; Update button
- **Trust allowlist** `plugin_trusted_owners` (config + Settings); blocks non-listed GitHub owners
- **Installed** tab in Module Store
- **Plugins** sidebar page redirects to Module Store
- Hooks: `grab`, `organize`, plus existing `startup` / `event.*`
- Catalog: builtin Announce Lab entry → Homelab; clearer offline vs GitHub

## 2.0.16-dev — 2026-08-10

### Plugin store hardening (same 2.0.16 line)
- Plugin `startup` + `event` / `event.<name>` hooks actually invoked
- Settings: `plugin_registry_url`, `plugins_path`, `plugins`
- Marketplace: install_type, online_required, reinstall API
- UI: Installed-only filter, Offline OK / Needs GitHub badges, Reinstall


### Homelab Announce Lab (autobrr-style, no extra container)
- In-app filter engine under **Homelab → Announce Lab**
- Polls Torznab indexers, match/except regex filters, enqueue to qBittorrent
- Scheduler job every 5 minutes; manual “Run cycle now”
- API: `/api/homelab/announce`, `/filters`, `/run`
- Docs: `docs/ANNOUNCE_LAB.md`

## 2.0.15-dev — 2026-08-10

### Packaging fix
- Dockerfile now `COPY data` (plugin catalog + example) and alembic

### Module & Plugin Store
- Unified **Module & Plugin Store** UI: built-in modules + GitHub community plugins
- Catalog: search, category filters, refresh, install/uninstall, GitHub repo install
- Expanded bundled `data/plugin_catalog/catalog.json` (notifications, subtitles, arr-bridge, themes, webhooks, fanart, example)
- Install types: `github_archive`, `github_release`, `url`, **`bundled`** (example hello plugin)
- Spec + docs: `PLUGIN_SPEC.md`, `docs/PLUGIN_STORE.md`
- API: `GET/POST /api/plugins/marketplace`, install, GitHub install, uninstall, refresh

### Carry-forward
- LiveTV virtual channels merge (2.0.14)
- Setup wizard: Movies/TV required; other libraries click-to-enable

## 2.0.14-dev — 2026-08-10

### LiveTV merge
- Merged improved IPTV/LiveTV from `v2_0_6-dev-fixed` into 2.0.13 base
- Virtual channels + stream engine; models, Alembic `0004`, soft migrate `2.0.6`
- Health columns on `livetv_channels` (`last_ok_at`, `last_error`, `created_at`)
- Kept safer `livetv_logos` from 2.0.13

### Setup wizard & Module Store
- Movies & TV **mandatory** (locked in wizard, core in store)
- Optional modules **click-to-enable**: music, books, audiobooks, comics, manga, games, podcasts, youtube, livetv, converter, adult
- Paths step only for selected modules; `games_library_path` wired through setup API
- Module Store UI: Required vs Optional sections with toggles

### Plugin marketplace
- GitHub-backed community plugin catalog (`data/plugin_catalog/catalog.json`, overridable via `plugin_registry_url`)
- Install from catalog or any `owner/repo` archive; uninstall; load `mediaos.plugin.json` plugins
- Module Store UI: tabs for Built-in modules / Community plugins / Install from GitHub
- API: `/api/plugins/marketplace`, `/install/github`, delete, reload
- Spec: `data/plugin_catalog/PLUGIN_SPEC.md`

### Version
- Tag: `2.0.14-dev`

## 2.0.13-dev + LiveTV fix merge (2026-08-10)

Merged improved IPTV / LiveTV stack from `MediaOS-v2_0_6-dev-fixed`:

- Full `livetv` router, service, and UI page from the fixed build (virtual channels, better source handling).
- Added `virtual_channels.py` + `virtual_stream_engine.py` (library → 24/7 personal TV channels via ffmpeg HLS).
- Added `LiveTvVirtualChannel` / `LiveTvVirtualScheduleItem` models + Alembic migration `20260810_0004`.
- Scheduler jobs for virtual schedule top-up and stream supervision.
- Config keys: `virtualtv_*`.
- Kept latest `livetv_logos.py` (stronger zip import safety).
- Docs: updated `docs/LIVETV.md` from fixed build.

Base remains v2.0.13-dev.

# Changelog

## 2.0.18-dev — polish pass (audit fixes)

### Fixed
- Version consistency: VERSION, Dockerfile, package.json, and runtime fallbacks all report **2.0.18-dev**
- Games, Scrobbling, and Tracking promoted to first-class UI pages (`games.jsx`, `scrobbling.jsx`, `tracking.jsx`)
- Silent `except: pass` in games metadata search and tracking replaced with logged warnings
- Alembic migration `20260810_0005` for platforms, games, game_releases, watch_progress, scrobble_events, tracked_items
- New **About** page with attribution for absorbed open-source project ideas
- Smoke tests for games/scrobble/tracking imports and version consistency

### Notes
- Stream-as-primary, Module Store UX depth, and broader except-logging remain iterative follow-ups
- Path/hardlink organize paths already prefer hardlink then copy; further edge-case hardening tracked for next pass


## 2.0.13-dev — 2026-08-10 (hardlink default + settings)

### Library organize
- **Hardlink enabled by default** (`library_prefer_hardlink=True`)
- Exposed `library_prefer_hardlink`, `jdupes_enabled`, `jdupes_hardlink` in Settings → Library group (runtime editable, no restart)
- Documented `LIBRARY_PREFER_HARDLINK=true` in `.env.example`
- Organize still falls back to move when source/dest are on different filesystems

### Carry-forward
- All 2.0.12-dev absorption work unchanged

## 2.0.12-dev — 2026-08-10 (absorption depth)

Completed thin/incomplete/weak areas from the Drive-source absorption audit.

### Games (Questarr)
- Full **IGDB** client (OAuth, search, detail, covers, genres, companies)
- Full **Steam** client (store search, app details, owned library when keyed)
- Metadata search + add-from-metadata + wanted list
- Search releases → grab pipeline endpoints
- **Games UI** maximized: library / wanted / metadata search / releases tabs

### Scrobbling (scrob)
- History responses include **title + media_type**
- Continue watching UI (progress cards)
- History table UI
- **Trakt scrobble push** endpoint (`POST /api/scrobble/trakt/push`)

### Homelab (Organizr)
- Polished **Homelab page**: groups, filter, health check, card grid launcher

### Music (headphones)
- Maximized **artist → album → track** hierarchy service with completeness %
- Hunt priority helpers for incomplete albums

### Comics (mylar3)
- **Reading-order** endpoint for story arcs
- **Metatag** endpoint writes ComicInfo.xml sidecar

### Dashboard (Prismarr)
- Dense widget helpers (continue, games, tracking summary)
- `/api/system/dashboard/dense` aggregate endpoint

### Carry-forward
- Security baseline from 2.0.11-dev unchanged


## 2.0.11-dev — 2026-08-10 (security completion)

Full pass on remaining audit items from 2.0.10-dev hardening.

### Security
- **Postgres password required** — compose uses `${POSTGRES_PASSWORD:?…}` (no more `change-me` default). Use `scripts/generate_secrets.sh`.
- **DB-backed auth tokens** — `create_token()` always prefers `app.services.sessions` / `AuthSession`; legacy in-memory is fallback only.
- **Shorter session TTLs** — access 4h, refresh 7d (was 12h / 30d; legacy in-memory 4h).
- **`revoke_access()`** helper for single-token revocation (memory + DB).
- **Volume ownership entrypoint** — `scripts/docker-entrypoint.sh` chowns data mounts when started as root, then drops to `mediaos` via `gosu`.
- **CI security workflow** — lockfile hygiene (reject IP/HTTP registries), `npm audit`, `pip-audit`.
- **Subprocess safety tests** — assert no `shell=True` / `os.system` in `app/`.
- **Auth + path-guard unit tests** — password hashing, library path escape rejection, TTL constants.
- **Threat model** documented in `SECURITY.md` (homelab LAN vs internet-exposed).
- Removed legacy `GITHUB_RELEASE_v4.*` and old `SHA256SUMS*` noise files.

### Ops
- `scripts/generate_secrets.sh` — generates `POSTGRES_PASSWORD` + `AUTH_API_KEY`, forces `AUTH_REQUIRE=true`.
- Dockerfile installs `gosu` and uses `ENTRYPOINT ["/docker-entrypoint.sh"]`.

### Carry-forward from 2.0.10-dev
- Official npm registry only in `package-lock.json` + `.npmrc`.
- `auth_require` default `true`.
- Non-root user `mediaos` (uid 1000).

## 2.0.10-dev (security hardening)

- Regenerated `package-lock.json` against official `https://registry.npmjs.org` (removed private registry URLs).
- Added project `.npmrc` pinning the official npm registry.
- Default `auth_require` / `AUTH_REQUIRE` set to `true`.
- Docker image non-root user `mediaos` (uid 1000).
- Compose files document the need to change default database passwords.

## 2.0.10-dev — 2026-08-10

### Best of both (2.0.7-final-1 + 2.0.9)

**From final-1**
- Alembic is the **sole** schema authority at startup (`alembic upgrade head`; fail closed)
- First-run **admin credentials** → `{data_path}/bootstrap/admin-credentials.txt` (not API-exposed)
- yt-dlp pinned `2026.06.09`
- Postgres `16.14-alpine`, FlareSolverr `v3.5.0`
- EPG pinned build (`docker/epg.Dockerfile` + server)
