# MediaOS v4.12.0 — Project Audit

Date: 2026-08-08  
Scope: incomplete features, broken pipelines, scripts, AI integration, polish gaps

---

## Severity legend

- **P0** — Broken or will fail at runtime
- **P1** — Incomplete but high-value; should finish soon
- **P2** — Polish / nice-to-have
- **P3** — Docs / packaging hygiene

---

## P0 — Fixed or must fix

| Issue | Status | Notes |
|-------|--------|-------|
| AI `queue_status` used non-existent `Download.error` / `title` | **Fixed** | Model has `last_error`, `release_title` |
| AI `blocklist_overview` used non-existent `title` | **Fixed** | Model has `release_title` |
| AI music search used `artist` instead of `artist_name` | **Fixed** | Matches `MediaItem.artist_name` |
| Shell scripts not executable (`chmod +x`) | **Fixed** | All `scripts/*.sh` now executable |
| AI endpoints require admin when auth is off | OK | `require_admin` allows open install via role flow; verify on first boot |

---

## P1 — Incomplete projects / thin pipelines

From `docs/GAP_AUDIT.md` + code review:

| Item | Current state | Recommendation |
|------|---------------|----------------|
| **Homelab Links** | `homelab_links.py` is a stub; `save_links` does not persist; no UI page | Wire to `AppSetting` + Settings/Homelab page |
| **Live TV channel editor** | EPG/auto-grab strong; enable/order/logos/groups thin | Finish channel editor UI (Cinephage-depth) |
| **Multi-quality keep policy** | `desired_qualities` exists on model; organize/grab policy thin | Enforce multi-quality on grab/organize |
| **Comic pull-list auto-grab worker** | Models + API exist; background auto-grab incomplete | Scheduler job like hunt |
| **Stream button next to Grab** | Stream-as-primary helpers exist | UI: Stream beside Grab in interactive search |
| **Stronger CF bypass** | `cf_bypass.py` + FlareSolverr | Harden stubborn indexers path |
| **\*arr DB import validation** | Migrators exist | Checklist + dry-run report in UI |
| **Plex/Tautulli now-playing widget** | Not present | Optional dashboard widget |

---

## P1 — Packaging / release tree gaps

| Gap | Impact | Action |
|-----|--------|--------|
| `app/clients/` missing from partial release extract | Runtime import failures for TMDb, qB, etc. | Always ship full tree from clean `git archive` or full unzip |
| `app/static/` (prebuilt UI) missing | Image works only after `npm run build` in Docker | Dockerfile already builds UI; local non-Docker needs static or vite dev |
| `package-lock.json` missing | Non-reproducible npm installs | Commit lockfile; include in release zip |
| `.github/workflows/` missing from working tree | No CI/CD in this copy | Restore `ci.yml`, `ghcr.yml`, `pages.yml`, `ui.yml` from main |
| Release zip built from incomplete extract | Users may get a partial app | Rebuild release from full repo checkout |

---

## P2 — Scripts & pipelines

| Script | State | Polish |
|--------|-------|--------|
| `apply_safe_ai.sh` | Good, idempotent | Keep |
| `build_release.sh` | Good; embeds notes + sha | Prefer full-tree source |
| `smoke_api.sh` | Health, cardigann, calendar, indexers | Add `/api/ai/status` optional check |
| `smoke_checks.sh` | Unit + optional API | OK |
| `smoke_unit.py` | Offline unit smoke | OK |
| `sync_cardigann_defs.sh` | Jackett sparse clone | Document network requirement; rate-limit |
| `epg-sidecar-entrypoint.sh` | Functional | Fragile on first clone failure — add retry |
| `build_docs.py` | Pages sync | Run in `pages.yml` workflow |
| `test_app_settings.py` | Exists | Ensure in CI |

**Missing automation worth adding:**

1. GitHub Action: on tag `v*` → run `build_release.sh` → upload zip + sha256 + release notes  
2. `scripts/pull_ollama_model.sh` — one-liner to pull `llama3.2` after compose up  
3. Smoke check for AI: `curl /api/ai/status` when profile `ai` is up  

---

## P2 — AI / Search polish

| Item | Notes |
|------|-------|
| Sidebar **AI Search** + floating button | Done |
| Enum vs string filters | `MediaItem.media_type` / `status` are Enums — string filters usually work with SQLAlchemy but prefer `.in_([ItemStatus.wanted, ...])` for robustness |
| Actor search | Relies on `overview` / title; no dedicated cast column — consider metadata JSON later |
| Tool results size | Capped at 40 — OK for chat |
| Confirmation flow | Proposal only; no auto-execute on "yes" yet (intentional safety) — optional follow-up tool `confirm_proposal` still read-only guidance |

---

## P3 — Docs & version consistency

| Item | Notes |
|------|-------|
| README still mixed older version strings in body | Header is 4.12.0; skim for leftover 4.7.x |
| CHANGELOG truncated vs full history | Fine for release; full history can live on GitHub |
| `STRUCTURE.txt` says 4.4.1 | Update to 4.12.0 |
| `FILELIST.txt` | Regenerate on release so it matches the zip |

---

## What is in good shape

- Core FastAPI app structure (routers/services/models) is coherent  
- Quality / TRaSH / hunt / cleanup / indexers are substantial  
- Docker multi-stage build (Node UI → Python runtime) is correct  
- Safe AI design (read-only tools + proposal gate + optional profile) is sound  
- Smoke scripts exist for offline + live checks  
- Cardigann definition sync script is practical  

---

## Recommended next polish order

1. **Ship a full-tree release** (clients, static or lockfile, workflows) — packaging integrity  
2. **Homelab Links** persist + thin UI page — quick win from GAP_AUDIT  
3. **Smoke + CI**: AI status check, restore workflows, tag → release  
4. **Live TV channel editor** + Stream-next-to-Grab — user-visible depth  
5. **Comic pull auto-grab** + multi-quality policy — pipeline completeness  

---

## AI agent field map (post-fix)

| Tool | Model fields used |
|------|-------------------|
| search_media | title, year, overview, artist_name, media_type, status, monitored, file_path |
| show_wanted | status, monitored, file_path, media_type |
| queue_status | release_title, status, last_error, media_item_id |
| blocklist_overview | release_title, reason, added_at |
| check_indexer_health | name, kind, enabled, priority, last_ok_at, last_error, credentials_json |
| list_quality_profiles | name, media_type, cutoff |

