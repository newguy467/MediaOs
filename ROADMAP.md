# MediaOS v2 Roadmap — Full Absorption Edition

Version target: **2.0.0** (major version bump from MediaOs 4.x to signal the comprehensive absorption)

## Phase 0 — Foundation for v2 (Documentation & Architecture)

- [x] New VISION.md absorbing all 11 source projects
- [x] This ROADMAP
- [ ] Updated ARCHITECTURE.md (shared pipeline + Tracking/Scrobbling layer + Games)
- [ ] Module Store expanded: Games, Scrobbling, Tracking
- [ ] License & attribution notes (ideas absorbed, clean re-implementation)
- [ ] VERSION → 2.0.0-dev
- [ ] CHANGELOG structure for major absorption

## Phase 1 — Core Pipeline Hardening (Movies + TV still king)

Priority: Make Movies + TV better than Sonarr + Radarr + Prismarr combined.

- [x] First-class **multi-quality keep** policy (bobarr philosophy) — retention_policy + grab enforcement
  - Desired qualities list per profile
  - “Keep all matching” / “Keep best N” / “Keep until cutoff”
  - UI for per-item quality retention rules
- [x] Prismarr-density dashboard & calendar — continue_watching / scrobbles / games / tracking widgets added
  - Control strip, multi-widget layout, dense month grid
  - Now-playing (Plex/Tautulli/Jellyfin) + queue + activity + calendar in one view
- [ ] Stream-as-primary everywhere (Cinephage level) — **mostly done, parent
      left unchecked pending a full audit**: distinct "Stream" button next to
      Grab confirmed in both `movies.jsx` and `tv.jsx`; `.strm` generation
      confirmed (`app/services/stream_mode.py`, `organize.py` sidecar write);
      debrid stream resolution confirmed (`stream_providers.resolve_stream`,
      multi-provider); usenet seekable streaming also exists
      (`app/services/usenet_stream.py`). Not verified: whether "everywhere"
      (every detail view / interactive search row) actually has the button,
      or just the two pages checked.
  - “Stream” button next to Grab in detail views + interactive search
  - Improved .strm generation + library placement
  - Debrid + Usenet stream paths polished
- [ ] Stronger *arr import validation + side-by-side mode

## Phase 2 — Scrobbling & Unified Tracking Layer (scrob + Yamtrack)

This is the highest-leverage new horizontal capability.

### Scrobbling Engine
- [x] Local scrobble ingestion + progress + history + continue API (webhook from Jellyfin/Plex/Emby, or direct player API)
- [x] Progress tracking (%, watched episodes, timestamps)
- [x] “Continue watching” and “Up next” surfaces
- [x] History view with filters (media type, date, user)
- [x] Optional push to Trakt / other services

### Unified Tracking
- [ ] Cross-module progress model (movies, TV, anime, games, books, comics, podcasts)
- [ ] Status: Wanted / In Progress / Completed / Dropped / On Hold
- [ ] Ratings + notes + tags
- [ ] Smart lists driven by actual watch/play history
- [ ] “Because you watched X” recommendations (local embeddings or simple collaborative later)

## Phase 3 — Live TV + Stream Depth (Cinephage)

- [ ] Full channel editor: enable/disable, reorder, logos, groups, bulk actions
- [ ] Polished EPG grid with click-to-stream / record
- [ ] Portal scan (Stalker etc.) + health checks
- [ ] Stream quality profiles and fallback logic
- [ ] Catch-up / timeshift where providers support it

## Phase 4 — Games Module (Questarr absorption)

New first-class module.

- [x] Data model: Platform → Game → Editions / Releases + API
- [x] Metadata providers (IGDB, Steam, GOG, etc. as available)
- [x] Wanted / Monitored / Library states
- [x] Automated search + grab via indexers / download clients (same pipeline)
- [ ] Installation path / emulator / launcher hooks (optional)
- [x] Completion tracking + playtime (feeds into Tracking layer) — confirmed:
      `Game.playtime_minutes` column, `POST /api/games/{id}/playtime`
      increments it and pushes completion into the tracking layer when
      playtime > 0 (`app/routers/games.py`).
- [ ] Module Store opt-in (off by default so Movies/TV stay clean)

## Phase 5 — Music & Comics Depth

### Music (Headphones-level)
- [x] Full artist → album → track tree with completeness %
- [ ] Missing track lists and wanted hierarchy views
- [ ] Folder organization + MusicBrainz depth
- [ ] Album completeness scoring in hunt/wanted

### Comics / Manga (Mylar3-level)
- [ ] Weekly pull-list automation + auto-grab
- [x] Story-arc UI + reading order
- [x] Issue metatagging (ComicTagger-style)
- [ ] Publisher / series / arc organization
- [ ] Reading progress (feeds Tracking layer)

## Phase 6 — Homelab & Dashboard Polish (Organizr + Prismarr)

- [x] Homelab Links API + model (UI still thin)
  - Custom icons, groups, status checks (HTTP, Docker, etc.)
  - Quick links to download clients, players, other services
- [ ] Dashboard density pass
  - Configurable widgets
  - Activity + Queue + Calendar + Now Playing + Wanted + Health in one dense view
- [ ] Basic / Advanced / Power mode switch remains

## Phase 7 — Indexer & Search Hardening (trawl influence)

- [ ] Stronger FlareSolverr / CF bypass tooling
- [ ] Rate-limit registry improvements
- [ ] Capability detection and health history
- [ ] Advanced interactive search UX

## Phase 8 — Cross-cutting Quality of Life

- [ ] Multi-user RBAC (viewer / request-only / power / admin) — **partial**:
      permission-scoped presets exist and are enforced server-side
      (`PROFILE_PRESETS` = kids/viewer/power_user in `app/routers/users.py`,
      each with its own permission list), but the underlying `role` column
      only has two literal values (`admin`, `user`) — the four-role model
      the roadmap describes isn't a first-class `role` value, it's
      permission-list granularity layered on top of `user`. Left unchecked;
      worth deciding whether that distinction matters before closing this.
- [x] Backup create/list API (UI thin)
- [x] Health trends snapshot API (indexer success, disk, stalled downloads)
- [ ] Notification center (Discord, Telegram, ntfy, Gotify, webhooks) with
      actions — **partial**: Discord, Telegram, ntfy, and Gotify are all
      implemented with real send functions and a settings-driven
      enabled/disabled state (`app/services/notifications.py`), plus a
      `GET /notifications/history` endpoint. Not confirmed: a generic
      `webhooks` channel (only the four named providers exist), and
      whether notifications support "actions" (e.g. approve/dismiss from
      the notification itself) beyond the history log.
- [x] Plugin registry stub (future community modules)
- [ ] Mobile / PWA improvements

## Phase 9 — Polish, Migration, Release

- [ ] Full migration path from MediaOs 4.x
- [ ] Import tools for existing *arr + Questarr-style libraries where possible
- [ ] Documentation site update
- [ ] Smoke tests + CI for all new modules
- [ ] Public release of MediaOS 2.0.0

---

## Implementation Notes

- All new features must respect the **shared pipeline**.
- Games and Scrobbling are **modules / layers**, not core requirements. Default install stays Movies + TV focused.
- We re-implement ideas in MediaOS’s FastAPI + SQLAlchemy + React style.
- Attribution: “Inspired by / concepts absorbed from bobarr, Cinephage, headphones, mylar3, Organizr, Prismarr, Questarr, recyclarr, scrob, trawl, Yamtrack” in docs and about page.
- Licensing: Only use code under compatible licenses; prefer clean re-implementation of public algorithms and UX patterns.

## Success Metrics for v2.0

- A user can manage Movies, TV, Music, Comics, Games, and Live TV from one UI.
- Watch progress is tracked locally and drives smart lists + continue-watching.
- Multi-quality retention is explicit and powerful.
- Dashboard feels as dense and useful as Prismarr while being the actual manager (not just a control plane).
- New users can start with Movies + TV only and enable Games / Scrobbling later via Module Store.
