# UI error / dead-code pass — status

Date: 2026-08-17

## Fixed in this pass

1. **Navigation collision bug** — `routes.jsx` had two page keys mapped to the
   same URL (`library`/`library-player` both → `/library`, `widgets`/`widget-layout`
   both → `/widgets`). `pageForPath()` resolved to whichever key was declared
   first, so clicking "Watch" or "Widgets" in the sidebar got silently reset to
   the wrong page. Removed the dead `library` alias; gave `widget-layout` its
   own path (`/widgets/layout`).
2. **Dead-end nav button** — Dashboard's "Indexers" button called
   `setPage('indexers')` but `app.jsx`'s switch had no matching case, so it
   silently fell back to the Dashboard. Added `case 'indexers'`.
3. **Crash bug** — `OverhaulDashboardPage` referenced `em.includes(...)`
   without `em` ever being defined (`ReferenceError` if rendered). Wired
   `enabledModules` through from `app.jsx` and derived `em` in the component.
4. **Crash bug** — `AdultSettingsPage` (adult.jsx) rendered `<ConfigGroupPage>`
   without importing it. Added the import.
5. **Orphaned components reconnected** — `TrashImportPanel`, `ArrDbMigratePanel`,
   `ArrMigratePanel` in `wanted.jsx` were fully built, backed by working API
   routes, but never rendered anywhere. Added an "Import tools" tab on the
   Wanted page so they're reachable.
6. **Dead imports removed** — 654 unused import specifiers cleaned up across
   55 files (verified against `npm run check:lazy`, `scripts/check_ui_static.py`,
   and a full re-scan confirming every JSX component reference still resolves).

## Fixed in follow-up pass (same date)

7. **`TrashImportPanel` always-fails bug (item #5's known issue) — fixed.**
   Was POSTing `{ url, profile_name, media_type, replace_formats }`, but
   `import_trash()` explicitly 400s on `url` (client-side URL fetch was
   never implemented server-side, by design). Swapped the URL `<input>`
   for a JSON paste `<textarea>` (one of the two options this doc listed):
   client-side `JSON.parse` before submit, with a clear inline error if
   it doesn't parse, then POSTs `{ data: parsed, ... }` instead of `url`.
   Also removed the two "Preset" buttons and the `trash/presets` fetch —
   `GET /migrate/trash/presets` always returns `null` for both preset
   URLs (per the router's own comment, no built-in preset URLs exist in
   this codebase), so the buttons were dead weight that filled the input
   with an empty string. Verified: `py_compile` on `migrate.py`
   (untouched, confirming no regression), esbuild per-file check on
   `wanted.jsx`, full `app.jsx` bundle — 0 errors, 996.1kb;
   `check_ui_static.py` (59 jsx files, 50 icons) and
   `check_lazy_exports.mjs` both pass.

## Investigated this session — GPU compose layout: intentional, no change

- **GPU docker-compose layout** — resolved. `docker-compose.nvidia.yml` /
  `.amd.yml` / `.intel.yml` are deliberate override files, not a gap.
  All three are valid, tiny (~10 lines), add only new fields (`gpus`,
  `devices`, `CONVERTER_HWACCEL_DEFAULT`) with zero conflicts against the
  base `mediaos` service. The in-app GPU setup wizard
  (`app/routers/setup.py`, `app/services/converter.py`) directly
  instructs users to run `docker compose -f docker-compose.yml -f
  docker-compose.nvidia.yml up -d` — the override-file pattern is
  load-bearing, user-facing behavior. Compose `profiles:` can't do what
  merging would need here (swap partial config on the *same* service
  based on which profile is active) without duplicating the ~90-line
  `mediaos` service three times, which would be strictly worse. Left
  split, no change made.

## Backlog reconciliation — done this session

Checked the `docs/POLISH_AND_GAPS.md` / `docs/TODO_NEXT.md` "still open"
items directly against the code rather than trusting the docs' own prose
(see `docs/TODO_NEXT.md` for the full write-up). Five of six were
genuinely already done and the docs just hadn't been updated:
- Full metadata job queue (background worker + SSE progress) — done
- TorBox-specific client module tests — done
- Server-side kids profile presets — done
- Backup `include_db` flags honored in `create_backup` service — done
- Path-map apply inside organize (not only dry-run) — done

One was **not** actually done despite the changelog implying it was:
- **Score breakdown always populated from quality engine** — `score_release()`
  in `app/services/quality/profiles.py` had 4 return paths; only 2 set
  `breakdown`, so 2 of the 4 rejection reasons showed nothing in the
  Quality Explain drawer. **Fixed this session** — see `docs/TODO_NEXT.md`
  for the details.

## Also fixed this session — `.env.example` was missing entirely

Found while investigating the GPU question (checking whether GPU-overlay
vars like `RENDER_GID` had defaults documented anywhere). `.env.example`
didn't exist anywhere in the repo — breaks the documented `cp
.env.example .env` quickstart step in `README.md`, breaks `scripts/
generate_secrets.sh` (which does `[ -f "$ENV_FILE" ] || cp .env.example
"$ENV_FILE"`), and `tests/test_compose_architecture.py` explicitly
asserts it exists and is complete (would fail test collection). Rebuilt
covering all 74 vars referenced in `docker-compose.yml`, the GPU-overlay
vars, and the app-level keys from `docs/REQUIRED_KEYS.md`. Verified
against a hand-replicated copy of every assertion in
`test_compose_architecture.py` (pytest itself isn't installed in this
sandbox) — all pass. Also caught a bug in my own first draft: writing
sensitive vars as `KEY=  # sensitive` (comment inline, same line) broke
`generate_secrets.sh`'s naive `sed`-based blank-check, since the comment
text got read as the "current value" and the script thought a real
secret was already set. Moved the annotation to a comment line above
each sensitive var instead; re-ran `generate_secrets.sh` against the
fixed file and confirmed it now generates real hex secrets.

## Todo-scan completion — full repo sweep for stale/actionable items

Went beyond the 4 already-reconciled docs (`todo.md`, `docs/TODO_NEXT.md`,
`docs/POLISH_AND_GAPS.md`, this file) and grepped the whole repo for any
other file mentioning "still open / not yet / gap / known issue / todo".
Found 4 more docs (`docs/ANNOUNCE_LAB.md`, `docs/LIVETV.md`,
`docs/STORE_AND_SETUP.md`, `scripts/windows/README.md`) — read each in
context and confirmed they're intentional scope/limitation disclosures
(comparison tables, documented feature boundaries), not stale action
items. No change needed there. Also grepped `app/`/`tests/`/`scripts/`
for inline `TODO`/`FIXME`/`HACK` code comments — none found (the only
`XXX` hits are the legitimate adult-content category constant, not
markers).

Found and audited `ROADMAP.md` (the long-range v2.0 checklist, separate
from the session-notes docs) — spot-checked several `[ ]` unchecked items
against the actual code rather than assuming unchecked means undone:
- **Games completion tracking + playtime** — confirmed fully done,
  checked off (`Game.playtime_minutes` + `POST /games/{id}/playtime`
  pushes into tracking layer).
- **Stream-as-primary everywhere** — confirmed mostly done (Stream
  button in both movies.jsx and tv.jsx, `.strm` generation, debrid +
  usenet stream resolution all exist) but left unchecked since
  "everywhere" wasn't fully audited across every view.
- **Multi-user RBAC** and **Notification center** — both confirmed
  partially done, left unchecked with a note on exactly what's missing
  (RBAC: permission-preset granularity exists but no 4-value `role`
  column; notifications: 4 real providers + history endpoint exist, but
  no generic `webhooks` channel and no confirmed actionable notifications).

This closes out the todo-scan the user asked to finish — every doc in the
repo that tracks open work has now been checked against the code at least
once this session, not just against other docs' claims.

## Progress-bar color bug — fixed

- **All `.progress` bars rendered purple regardless of variant** — in
  `ui/src/styles.css`, `.progress::-webkit-progress-value` and
  `.progress::-moz-progress-bar` were grouped into the same rule as
  `.progress-primary`'s variant, so every progress bar (including
  `progress-error` / `progress-warning`) got the primary gradient,
  silently hiding disk-usage warnings like the dashboard Storage
  widget's ≥90%-used red state (`dashboard.jsx`'s `StorageWidget`).
  Fixed by scoping both rules to `.progress-primary` only, so
  DaisyUI's own `.progress-error`/`.progress-warning`/`.progress-success`
  rules (same specificity, defined earlier in the cascade) are no
  longer overridden. Verified against the real compiled
  `app/static/assets/index-DCvXGtsS.css` with the actual
  `StorageWidget` markup (TV 92% now renders red, Movies 63% stays
  purple, a warning-state bar renders yellow) — screenshot taken with
  headless Chrome.
- Also hand-patched the already-built `app/static/assets/index-*.css`
  bundle to match, since `npm run build` isn't runnable in this
  sandbox (no network for `npm ci`). Anyone building from source will
  regenerate the same fixed output; this just keeps the shipped
  static bundle in sync until then.
