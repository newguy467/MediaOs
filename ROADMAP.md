# MediaOs v4 Roadmap — Big Bang Foundation → Full Replacement

Version: 4.0.0-foundation

## Phase 0 — Foundation (this package)
- [x] Elevated vision: full *arr ecosystem replacement
- [x] Architecture document (shared pipeline, modules, quality, hunt, maintenance)
- [x] Hybrid UI direction + Basic/Advanced modes concept
- [x] Stronger TRaSH live-sync scaffolding (Recyclarr-inspired)
- [x] Music hierarchy + completeness enhancements
- [x] Comics pull-list + story-arc scaffolding
- [x] Stream-as-primary path improvements
- [x] Maintainerr-style rules + Hunt engine stubs
- [x] Rate-limit registry UI hooks
- [x] Migration tooling upgrades
- [x] Homelab Links page concept
- [x] Updated docs, VERSION, STRUCTURE
- [x] Wizard **Modules** step (TV & Movies default; opt-in Music / Books / Audiobooks / Comics / Live TV / …)
- [x] **Module Store** page in main UI (enable/disable later)
- [x] Sidebar + mobile nav filtered by enabled modules
- [x] Modules API (`/api/modules`, setup modules endpoints)
- [x] Live TRaSH sync endpoints (`/api/quality/trash/sync`)
- [x] Hunt API foundation (`/api/hunt/plan`, `/api/hunt/run`)
- [x] Module Store card in Settings hub
- [x] Basic vs Advanced mode switch (gates quality matrix, Live TV, Converter nav)
- [x] Music hierarchy UI (artist → album tree + incomplete + track completeness)
- [x] Live TRaSH sync panel on Quality Profiles page
- [x] Prismarr-style dense dashboard control strip
- [x] YouTube notes (SponsorBlock already strong; optional proxy; YT-Lite is network-level only)

## Phase 1 — Quality & Core Pipeline (highest leverage)
- Live TRaSH Guides sync with real definitions (custom formats, scores, quality definitions, naming)
- Quality Profiles admin UI (create/edit/assign, score overrides)
- Unified release parser + scoring used by every media type
- “Keep multiple qualities” policy in organize/grab logic
- Rate-limit registry (view/edit host limits & backoffs)

## Phase 2 — Movies + TV to full replacement level
- Feature parity checklist vs Sonarr/Radarr (monitor modes, season packs, cutoff upgrades, history, blocklist)
- Stream option beside Grab in detail + interactive search
- Strong import from existing Sonarr/Radarr instances
- Dashboard calendar + queue/activity widgets (Prismarr density)

## Phase 3 — Music (Lidarr + Headphones)
- Full artist → album → track data model and UI tree
- Album completeness % + missing tracks
- Wanted hierarchy views
- MusicBrainz depth + folder organization

## Phase 4 — Comics / Manga (Mylar depth)
- Weekly pull-list automation (auto-search / auto-grab)
- Story-arc management + reading order
- Issue metatagging (ComicTagger-style)
- Publisher/series/arc organization hardened

## Phase 5 — Books, Audiobooks, Subtitles
- Readarr parity for books + audiobooks
- Bazarr-level (or better) subtitle providers + profiles + multi-language

## Phase 6 — Live TV + Streaming polish
- Channel editor (enable/order/logos/groups)
- Portal scan + bulk tools
- Polished EPG grid UX
- Stream-as-primary as first-class path across media types

## Phase 7 — Maintenance, Hunt, Homelab
- Rule engine (age/size/quality/tag/collection → actions)
- Hunt engine (aggressive missing/cutoff with prioritization)
- Homelab Apps/Links page
- Optional Plex/Tautulli “now playing” widget

## Phase 8 — Polish, Migration, Docs, Release
- Basic vs Advanced mode fully wired
- End-to-end migration guides + validation checklists
- Performance pass (large libraries)
- Public 4.0 release

## Continuous
- Multi-user permissions
- Converter improvements
- Notification coverage
- Cardigann / Torznab indexer expansion
- Community feedback loop

---

### Implementation notes for contributors

- Prefer extending existing services (`quality/`, `trash_guide_fetch.py`, `comic_pull_sync.py`, `music_completeness.py`, `stream_mode.py`, `cleanup.py`, `arr_migrator.py`) rather than inventing parallel systems.
- New domain depth (story arcs, full track hierarchy, rule engine) should land as proper models + services + routers + UI.
- Keep the shared pipeline sacred: every media type flows through the same search → score → grab/stream → organize path.
- When porting ideas from Cinephage / Mylar3 / Recyclarr / Headphones / Prismarr, extract the *behavior and data model*, not necessarily the original language or UI framework.

This foundation zip is the starting point for the big-bang v4 effort.

- [x] Comics story-arc + pull-list UI
- [x] Hunt worker wired
- [x] Dense month-grid calendar
- [x] Gluetun VPN credentials UI
- [x] GAP_AUDIT.md
