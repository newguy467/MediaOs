> **Archive note (2026-08-17):** This is the full, unedited session-by-session
> log that used to live in `todo.md` (sessions 1–23). It's kept here for
> history/context — every "what was tried, what broke, what got fixed" detail
> is preserved. `todo.md` itself was rewritten into a short, current-state
> summary; if you're looking for *what's actually left to do*, start there.
> This file is not maintained going forward — new session write-ups should
> still go in `todo.md` until it grows unwieldy again, at which point archive
> it here the same way.

---

# Session 23 — RBAC follow-up: edit-user dropdown confirmed done, test_rbac.py added

Picked up Session 22's "Not done yet" list.

## 1. Edit-existing-user role dropdown

Session 22 flagged this as still 2-option (User/Admin). Read the actual
file (`ui/src/pages/settings-userspermissions.jsx`) before writing any
code, per the standing lesson in this doc about not trusting a prior
note without checking: **the edit-user `<select>` already has all 4
roles** (guest/member/manager/admin), identical to the create-user
dropdown. No code change needed here — Session 22's note was stale by
the time this session started (unclear whether it was fixed in the same
session and the note just never got updated, or fixed by something
else). Flagging so a future session doesn't re-do this by mistake.

Verified: full `esbuild --bundle` of `app.jsx` — 999.4kb, 0 errors;
`check_ui_static.py` (59 jsx files, 50 icons), `check_version.py`,
`check_lazy_exports.mjs` all pass.

## 2. `tests/test_rbac.py` — NEW, closes the "no RBAC tests exist" gap

13 tests, two groups:
- **Pure unit tests** (no DB/auth) against `ROLE_DEFAULTS`/
  `PERMISSION_CATALOG` in `app/routers/users.py` and the `UserRole` enum
  in `app/models.py` — admin has every permission, manager has
  everything except `"users"`, member is exactly the browse/play/
  request/download set, guest is view-only (no download/queue/
  requests), and the deprecated `"user"` alias mirrors `"member"`.
- **Integration tests** via the existing `client`/`db` fixtures — a new
  `auth_on` fixture flips `app.config.settings.auth_require` on for the
  duration of a test (conftest defaults it off) and restores it after;
  a new `make_user` fixture creates a real DB user with role-default
  permissions. Covers: member gets 403 on a `require_permission
  ("settings")` route, manager gets through, guest gets 403; manager
  gets 403 on the admin-only `/api/users` (require_admin), admin gets
  through; the dedicated `require_manager` dependency (used by
  `requests.py` approve/deny) accepts manager and admin, rejects
  member; and a member with an explicit `permissions_json` override
  (`["settings"]`) gets through the settings-gated route despite their
  role default not including it — confirms the override path in
  `_perms_for()`/`get_current_permissions()` actually takes priority
  over role defaults.

**Not run — same constraint as every session in this file:**
`fastapi`/`sqlalchemy`/`pytest` aren't installed in this sandbox (no
network), so this couldn't go through a real `pytest` invocation.
Verified instead by: `python3 -m py_compile` (full repo, 0 errors) and
an `ast.parse` pass confirming every test function name resolves as
written; hand-checked every `ROLE_DEFAULTS`/`PERMISSION_CATALOG`
assertion against the literal values in `app/routers/users.py`; traced
`require_manager`'s dependency position in `requests.py`'s `approve()`
signature to confirm it's evaluated before the `db.get()` 404 lookup,
so a 404-not-403 response on a nonexistent request id is a valid signal
that a manager got past the role check; confirmed `ApproveIn()`'s
pydantic default means posting with no body is valid, so the test
doesn't need a real `MediaRequest` row.

## Still open

- The integration half of `test_rbac.py` has never actually been run
  against a live `pytest` — same testing-gap theme as every session in
  this file, just now with a concrete new test file waiting for that
  environment instead of an empty gap.
- No real `vite build` / `pip install` / `alembic upgrade` round-trip —
  same no-network constraint as always.

---

# Session 22 — Real 4-role RBAC: started, backend done, frontend partial

Picked up from the open-items list (was: "single role string +
require_admin, not a real role model"). Scope was bigger than a
single-turn stub — this session gets the backend fully working;
one frontend spot is left half-done (see below).

## What changed

**Role model** (`app/models.py`) — `UserRole` enum expanded from
binary `admin`/`user` to 4 real roles: `admin`, `manager`, `member`,
`guest`. Kept `user` in the enum as a deprecated alias (not removed)
so any row schema_migrate hasn't touched yet still resolves without
crashing.

**Data migration** (`app/services/schema_migrate.py`, version
`2.0.32`) — `UPDATE users/auth_sessions SET role='member' WHERE
role='user'`. Idempotent, matches zero rows on rerun.

**Default permission sets per role** (`app/routers/users.py`):
- `admin` — every permission in `PERMISSION_CATALOG`
- `manager` — everything **except** `"users"` (can run the whole app —
  settings, indexers, library, downloads — but can't create/edit/delete
  other accounts)
- `member` — browse/play/request/download (this is what `user`'s
  defaults used to be)
- `guest` — view-only (browse + play, no grab/queue/request)

Presets (kids/viewer/power/full) updated to map onto these named
roles instead of always creating a `role="user"` row with a permission
override — `kids`→`guest`, `power`→`manager`, `full`→`member`.

**The actual gap, closed**: the granular permission system
(`require_permission`, `PERMISSION_CATALOG`) already existed and was
wired into most routers — but a chunk of routes ignored it entirely
and hard-gated on literal `role == "admin"` via `require_admin`,
which meant `manager` (or any custom permission set) couldn't reach
them no matter what permissions were granted. Converted the ones that
are genuinely settings/ops-tier, not account-security-tier:
- `system.py`, `tools.py`, `library_gaps.py`, `overhaul.py` →
  `require_permission("settings")`
- `library_tools.py` (rename preview/apply) →
  `require_permission("library.manage")`
- `requests.py` (approve/deny) → new `require_manager` dependency in
  `app/auth.py` (admin-or-manager, returns a role string like
  `require_admin` did, since `resolved_by` needs a string, not the
  list `require_permission` returns)

**Left admin-only on purpose** (did not touch): `users.py` (account
management), `auth_sessions.py` (revoking other people's sessions),
`ai.py` (existing comment: "keep AI behind admin for safety"),
`migrate.py` (bulk destructive *arr imports).

**Frontend** (`ui/src/pages/settings-userspermissions.jsx`) — the
**create-user** role dropdown now offers all 4 roles, and the
role-defaults fetch uses `member` instead of the old `user` key.

## Not done yet

- The **edit-existing-user** row still has the old 2-option
  (User/Admin) dropdown — needs the same 4-option treatment as the
  create form. This is the next thing to pick up.
- No tests written for the new role/permission logic (no
  `test_rbac*.py` exists yet).
- Not verified against a live boot — only `python3 -m py_compile` on
  every touched file (all pass). No network in this sandbox, so no
  `pytest`, no `alembic upgrade` round-trip, no browser check that
  the new dropdown options actually render/save correctly.

# Session 21 — UI-fix follow-up + backlog reconciliation + missing .env.example

Continuation of the `TODO_UI_FIXES.md` pass. Note on numbering: this
repo's session count has actually gone much further than "20" in a
separate work thread (`docs/P0_P1_NOTES.md`/`docs/P2_P5_NOTES.md` show
Session 34, `CHANGELOG.md`'s "Unreleased (post-1.01beta)" covers
Sessions 11–25 on a different track) — `todo.md`'s own numbering had
just stalled at 20. Picking up the number here for continuity of this
specific doc, not as a claim this is the 21st thing ever done to the repo.

## 1. Fixed `TrashImportPanel`'s always-fails bug

Was POSTing `{ url, ... }` to `/api/migrate/trash`; the backend
explicitly 400s on `url` (URL-fetch was never implemented server-side,
by design). Swapped the URL input for a JSON paste `<textarea>`,
client-side `JSON.parse` before submit, POSTs `{ data: parsed, ... }`.
Removed the two dead "Preset" buttons (`GET /migrate/trash/presets`
always returns `null` for both). See `TODO_UI_FIXES.md` for full detail.

## 2. GPU docker-compose layout — investigated, confirmed intentional

`docker-compose.nvidia/amd/intel.yml` are deliberate override files
(`docker compose -f docker-compose.yml -f docker-compose.nvidia.yml up
-d`), not a gap. The in-app GPU setup wizard (`app/routers/setup.py`,
`app/services/converter.py`) directly instructs users to use them this
way. Compose `profiles:` can't replace this without duplicating the
~90-line `mediaos` service three times. Left split, no code change.

## 3. Found and fixed: `.env.example` was missing from the repo entirely

Breaks the documented quickstart (`cp .env.example .env`),
`scripts/generate_secrets.sh`, and `tests/test_compose_architecture.py`
(asserts existence + completeness — would fail at collection). Rebuilt
from scratch: all 74 vars referenced in `docker-compose.yml`, GPU-overlay
vars (`RENDER_GID`/`VIDEO_GID`/`LIBVA_DRIVER_NAME`), app-level keys from
`docs/REQUIRED_KEYS.md`. Verified against a hand-replicated copy of every
assertion in `test_compose_architecture.py` (pytest not installed in
this sandbox) — all pass.

**Bug caught in my own first draft:** writing sensitive vars as
`KEY=  # sensitive` (inline comment on the same line) broke
`generate_secrets.sh`'s naive `sed`-based "is this still blank" check —
the comment text got read as the current value, so a real password was
never generated; `DATABASE_URL` ended up with the comment text embedded
in it. Fixed by moving the `# sensitive` annotation to its own comment
line above each var, value left truly empty. Re-ran
`scripts/generate_secrets.sh` end-to-end against the fixed file and
confirmed it now produces real hex secrets and a correct `DATABASE_URL`.

## 4. Backlog reconciliation — `docs/TODO_NEXT.md` / `docs/POLISH_AND_GAPS.md`

Both docs had "still open" lists that were stale relative to
`CHANGELOG.md`'s "Unreleased" section. Checked every item directly
against code rather than trusting either doc's prose:

- `docs/POLISH_AND_GAPS.md`'s 12-item "Still open (next set)" — all 12
  confirmed landed (this list became `TODO_NEXT.md`'s own "Landed this
  pass" in the next session). Marked historical, points to TODO_NEXT.md.
- `docs/TODO_NEXT.md`'s 7-item "Still open / deeper" — 6 of 7 confirmed
  genuinely done by reading the actual code (metadata job queue, TorBox
  tests, kids presets, backup include_db, path-map-in-organize, 1.01beta
  tag). **1 of 7 was not actually done** despite the changelog implying
  it was:
  - **Score breakdown always populated from quality engine** —
    `score_release()` in `app/services/quality/profiles.py` had 4
    `ScoreResult` return paths; only 2 set `breakdown`. The
    "rejected by custom format" and "missing required format" paths
    returned an empty `{}`, so the Quality Explain drawer (shipped
    earlier, per the same docs) silently showed nothing for those two
    rejection reasons. **Fixed**: both paths now populate
    `{"total": score, "rejected": <reason>, ...}`. Verified all 4
    `ScoreResult` sites set `breakdown` (grep count matches), `py_compile`
    clean.

Both docs rewritten in place to reflect this — see their "reconciled
(2026-08-17)" sections.

## Verified (no network, same constraints as every prior session)

- `python3 -m py_compile` on every file in `app/` — 0 errors
- `python3 scripts/check_version.py` — OK (`1.01beta`)
- `python3 scripts/check_ui_static.py` — OK (59 jsx files, 50 icons)
- `node scripts/check_lazy_exports.mjs` — OK
- Full `esbuild --bundle` of `app.jsx` — 0 errors, 996.1kb
- Hand-replicated every assertion in `tests/test_compose_architecture.py`
  against the new `.env.example` + `docker-compose.yml` (pytest itself
  not installed in this sandbox) — all pass
- Simulated `scripts/generate_secrets.sh` against the new `.env.example`
  in a scratch directory — confirmed real secrets generated, correct
  `DATABASE_URL` interpolation

## Still open

- Same testing-gap theme as ever — no pytest actually run in this
  sandbox, only hand-replicated assertions and `py_compile`/esbuild.
- `todo.md`'s own session numbering vs. the `P0_P1_NOTES.md`/
  `TODO_NEXT.md`/`CHANGELOG.md` numbering are on different tracks and
  never got reconciled into one timeline — flagging so a future session
  doesn't assume they're the same counter.

---

# Session 20 — CI + test coverage ladder (items 1–5)

Closed the engineering-automation gap flagged after the polish audit.

## What landed

1. **GitHub Actions restored**
   - `.github/workflows/ci.yml` — static checks, pytest, alembic round-trip, UI build, aggregate success job
   - `.github/workflows/security.yml` — pip-audit + npm audit (advisory)

2. **Dev deps + local CI gate**
   - `requirements-dev.txt` (pytest, httpx, PyYAML)
   - `package.json` `ci:local` now runs version + UI static + lazy exports + **pytest**
   - `npm run test` / `test:api` scripts

3. **API contract tests** (`tests/test_api_bulk_progress.py`)
   - Bulk monitor + quality_profile for movies / books / audiobooks
   - Cross-type isolation (movies bulk ignores book ids)
   - Comic issue progress + `last_read_at` stamp
   - `widget_continue_reading` shape
   - Interactive-search 404 paths
   - Parity status smoke

4. **Route-order regression** (`tests/test_route_order.py`)
   - Same-method param-before-literal scanner across all routers
   - Explicit asserts for parity search-all, movies/books/audiobooks bulk

5. **Service smoke** (`tests/test_services_smoke.py`)
   - Parse all services, import grab/search/organize/interactive_search
   - quality `score_release` + `parse_release_title`
   - schema migrate versions 2.0.29/2.0.30
   - CONTINUE_PAGE_MAP

## Bugs found while testing (fixed)

- **Movies / books / adult `/bulk` registered after `/{item_id}`** — moved literals first (parity-style ordering).
- **AudiobookBulkIn / BookBulkIn** defined after the route that annotated them — moved classes above handlers.
- Missing **`.env.example`** keys required by compose architecture tests — restored.

## Verified

```
84 passed
```

(AUTH_REQUIRE=false, SQLite /tmp)

## Still open (honest)

- UI Playwright E2E not added (needs running stack + build)
- Full `requirements.txt` install in bare sandbox still heavy; CI uses pip in Actions
- coverage.py / codecov not wired (easy follow-up)
- `ui-build` job needs network npm in Actions (present in workflow)

---

# Session 19 — bulk actions (books/audiobooks) + Continue Reading + parity audit

Picked up the three highest-value items left open after Session 18.

## 1. Bulk actions extended to Books + Audiobooks

**Books** — backend `POST /api/books/bulk` already existed (monitor +
quality_profile). Wired the UI:
- `api.books.bulk` helper
- checkbox overlays on library grid cards (stay visible when selected)
- bulk bar: Monitor / Unmonitor / Search missing / Apply quality profile / Clear
- profiles filtered to `media_type === 'book'`

**Audiobooks** — no bulk endpoint existed. Added:
- `AudiobookBulkIn` + `POST /api/audiobooks/bulk` (registered before
  `/{item_id}` to avoid route shadowing)
- `api.audiobooks.bulk` helper
- row checkboxes + bulk bar (Monitor / Unmonitor / Search selected / Clear)

Podcasts intentionally skipped — feed-based model, not a MediaItem poster
grid; bulk monitor would need a different shape.

## 2. Comics Continue Reading

- `ComicIssue.last_read_at` column (model + schema_migrate `2.0.30` +
  alembic `20260815_0010`)
- `POST /issues/{id}/progress` now stamps `last_read_at` on every write
- `widget_continue_reading()` — in-progress issues (`last_page_read > 0`,
  not `is_read`) ordered by `last_read_at desc`
- Included in `dashboard_bundle` as `continue_reading`
- Dashboard widget "Continue reading" (enabled by default in layout)

## 3. parity.py deep audit

Route-order scan of all 16 endpoints. One real issue found and fixed:
- `GET /workers/{job_id}` (str param) was registered *before*
  `POST /workers/search-all`. Because `job_id` is a plain string, a GET
  to `/workers/search-all` would have been captured by the param route
  instead of 404'ing cleanly. Moved the literal `search-all` route above
  the param route (same pattern as earlier music/games/livetv fixes).

No duplicate endpoints vs other routers. Status map, STRM, Trakt
trending, usenet-stream Range handling, and CF-bypass test all look
coherent. Usenet stream Range parsing is careful about inclusive HTTP
ends and suffix ranges.

## Files touched

- `ui/src/api.js` — books.bulk, audiobooks.bulk
- `ui/src/pages/books.jsx` — bulk UI
- `ui/src/pages/audiobooks.jsx` — bulk UI
- `ui/src/pages/dashboard.jsx` — Continue reading widget
- `app/routers/audiobooks.py` — bulk endpoint
- `app/routers/comics.py` — last_read_at stamp on progress
- `app/routers/parity.py` — route-order fix
- `app/models.py` — ComicIssue.last_read_at
- `app/services/schema_migrate.py` — 2.0.30
- `app/services/dashboard_widgets.py` — widget_continue_reading
- `alembic/versions/20260815_0010_comic_last_read_at.py`

## Verified (no-network)

- `python3 -m py_compile` on all touched backend files — 0 errors
- Route order on parity.py: search-all before {job_id}

## Still open

- Real browser / live-DB smoke tests
- Podcasts bulk (different model; defer until requested)
- Automated test coverage gap (repo-wide)

---

# Session 18 follow-up — Movies bulk-actions UX polish (finish)

Movies bulk-actions UI from Session 18 was already in place (checkbox
overlays + bulk bar calling `POST /api/movies/bulk` + per-item search).
One remaining polish gap: selected checkboxes disappeared on mouse-out
because the overlay used only `group-hover:opacity-100`. That made it
hard to see which items remained selected while moving the cursor to
the bulk bar.

**Fix:** checkbox label opacity is now `opacity-100` whenever the item
is in `selected`, otherwise hover-reveal. Same pattern keeps the visual
quiet until you start selecting, then keeps the selection visible.

Touched only `ui/src/pages/movies.jsx`. No backend / API / icon changes.

Verified under the same no-network constraints: static structure of the
page still loads the profiles filter for `media_type === 'movie'`,
`selectedIds` drives the bar, and the three bulk handlers still call
`api.movies.bulk` / `searchNow` correctly.

## Still open (unchanged)

- Real browser smoke test of the bulk round-trip.
- Optional extension of the same bulk pattern to Books / Audiobooks /
  Podcasts (flagged in Session 18; not in scope here).
- Testing-gap items that require network / live DB.

---

# Session — router cleanup (Aug 15 2026)

Follow-up to a full code review of this zip. Fixed the two organizational
issues flagged as top priority (ahead of any individual feature): duplicate
endpoints in `app/routers/overhaul.py` that shadowed better implementations
elsewhere, and a stale version-fallback constant.

## What was found and fixed

- **Comics pull-list, duplicated and actually diverged.** `overhaul.py` had
  its own `/comics/pull-list` (GET/POST/sync) and `/comics/story-arcs`
  (GET/POST) querying `ComicPullList`/`ComicStoryArc` directly. `comics.py`
  already had a fuller version routed through `app/services/comic_arcs.py`
  (which also supports PATCH on pull items — `overhaul.py`'s copy never
  implemented that). Confirmed via grep that `ui/src/pages/comics.jsx`'s
  small "Weekly pull-list" widget (`ComicsPullPanel`) was calling the
  *weaker* `/api/overhaul/...` endpoints while the full pull-list tab on the
  same page called the *better* `/api/comics/pull` ones — two different
  DB queries against the same table, live in production on the same page.
  Fixed: `ComicsPullPanel` now calls `/api/comics/pull` +
  `/api/comics/pull/sync`. Removed the now-dead duplicate endpoints (+ the
  entirely-unreferenced `/comics/story-arcs` pair) from `overhaul.py`.
- **EPG sync, duplicated with worse error handling.** `overhaul.py`'s
  `/epg/sync` called `fetch_and_index_epg()` with no error handling.
  `livetv.py`'s `/epg/refresh` calls the exact same function but wraps it
  in try/except → proper `HTTPException(502)`. `livetv.jsx`'s "Sync EPG"
  button was calling the *worse* one. Fixed: swapped to
  `/api/livetv/epg/refresh`. Removed the now-dead `/epg/sync` and the
  entirely-unreferenced `/epg/grid` (also a thin duplicate of
  `livetv.py`'s own `/epg/grid`) from `overhaul.py`.
- **Music completeness, dead duplicate.** `overhaul.py`'s
  `/music/incomplete` and `/music/albums/{id}/completeness` called the
  same `music_completeness.py` functions as `music.py`'s own `/incomplete`
  endpoint (the one whose route-ordering bug was fixed in the prior
  session). Frontend only ever called the `music.py` version — the
  `overhaul.py` copies had zero references. Removed.
- **Confirmed NOT duplicate, left alone:** `overhaul.py`'s
  `/livetv/now-next` (genuinely different — falls back to full
  `channel_lineup()`, no equivalent in `livetv.py`), plus `/dashboard`,
  `/streams`, `/trash/import`, `/quality-files`, `/arr-instances`,
  `/trash/fetch`, `/external-arr`, `/widget-layout`.
- **Version fallback.** `app/version.py`'s `_VERSION_FALLBACK` said
  `"1.01beta"` while `VERSION`/`package.json`/`package-lock.json` (and
  `scripts/check_version.py`, which passes) all agree on `2.0.27-dev`. The
  fallback only matters if the `VERSION` file is ever missing at runtime,
  but it was misleading. Set to `2.0.27-dev` to match. Note:
  `RELEASE_NOTES_NEXT.md` describes a separate, larger rebuild that bumps
  everything to `1.01beta` — that doc appears to describe planned/future
  work that hasn't landed in this zip yet, not a bug; left it as-is since
  rewriting release notes is a product call, not a code-consistency fix.

## Verification used (same no-network constraints as prior sessions)

- `python3 -m py_compile` on `overhaul.py` and `version.py` — OK
- `esbuild` bundle checks on `comics.jsx`, `livetv.jsx` individually, and a
  full `esbuild --bundle` of `app.jsx` (react/react-dom/react-router-dom/
  hls.js externalized) — 933.7kb, 0 errors, every import resolved
- `python3 scripts/check_ui_static.py` — OK (57 jsx files, 50 icons used)
- `node scripts/check_lazy_exports.mjs` — OK
- `python3 scripts/check_version.py` — OK (2.0.27-dev)
- Grepped `ui/src/` (source only, not the stale prebuilt bundles under
  `app/static/assets/`) to confirm no remaining references to any removed
  `/api/overhaul/...` path before deleting each endpoint

## Still open (not done this session)

- `parity.py` was reviewed at the endpoint-list level but not
  individually audited line-by-line the way `overhaul.py` was — flagged
  as a candidate for the same kind of pass, not yet done.
- The automated-testing gap (449 lines of tests for 20,768 lines of
  service code, concentrated in regex/parsing-heavy areas like
  `quality/matrix.py`, `naming.py`, `cardigann.py`, `organize.py`) is
  unaddressed — this was flagged as the other top-priority item and is
  intentionally left for a separate session.
- As always: no real `vite build` / `pip install` was possible in this
  sandbox (network disabled) — verification above is a substitute, not a
  replacement, for an actual build/boot test.

---

# Session 13 — Comics K (per-issue search/grab/monitor buttons) DONE

Picked up the next item flagged in Session 12's "still open" list —
smallest of the remaining Comics gap items (K/L/M/O), touches the
same issues-table UI Session 12 just extended for reading progress.

Backend already had everything needed
(`POST /{item_id}/issues/{issue_id}/search`,
`POST /{item_id}/issues/{issue_id}/grab`, `PUT /issues/{issue_id}/monitor`
in `app/routers/comics.py`) — this session is frontend-only.

- `ui/src/api.js` — added `api.comics.searchIssue`, `.grabIssue`,
  `.monitorIssue`, mirroring the existing `issueProgress` entry's
  style.
- `ui/src/pages/comics.jsx` (`ComicDetailPage`):
  - Issues table's "Mon" column is now an interactive checkbox
    (`toggleIssueMonitor`) instead of a static ✓/— glyph, same
    pattern as `tv.jsx`'s per-episode monitor checkbox.
  - Added a per-row "Search" button (`openIssueSearch`) that opens
    `InteractiveResultsPanel` (already imported, already used
    item-level in this same file) scoped to that one issue via new
    `ixIssue`/`ixIssueResults`/`ixIssueLoading` state — kept separate
    from the existing item-level `ixResults`/`ixLoading` state so a
    per-issue search doesn't clobber an in-progress item-level one.
  - `grabIssueRelease` calls `api.comics.grabIssue` with
    `grabPayload(rel)` directly (not wrapped in `{release: ...}`) —
    matches how the item-level `grabRel` already calls the item grab
    endpoint, and the backend's `grab_issue` handler accepts either
    shape (`body.get("release") or body`).

Verified (no network, same constraints as every prior session):
`python3 -m py_compile` across every file in `app/` — 0 errors
(backend untouched this session, confirming no regression); esbuild
per-file bundle checks on `comics.jsx` (102.7kb) and `api.js`
(25.1kb) individually, plus a full esbuild `--bundle` of `app.jsx`
(react/react-dom/react-router-dom/hls.js externalized) — 938.5kb, 0
errors; `check_ui_static.py` — OK (57 jsx files, 50 icons — no new
icon needed, reused existing checkbox/button styling);
`check_version.py` — OK (`1.01beta`); `check_lazy_exports.mjs` — OK.
Cross-checked every new frontend fetch path against the router's
`@router.post`/`@router.put` decorators by hand — all three match
exactly.

**Not verified — needs a network-enabled environment:** a real
`vite build`; a browser smoke test — toggle an issue's monitor
checkbox and confirm it sticks after reload, run a per-issue search
and grab a release, confirm the issue's status flips to
`downloading` and the file shows up after the (external) download
completes.

## Still open

- Same testing-gap item (449 lines of tests for 20,768 lines of
  service code), still unaddressed.
- Comics L (manual release picker), M (manga toggle + manga-only
  view), O (`metatag_comic` path-safety + sidecar-vs-embedded XML)
  — still not started. L is the natural next pick: it's UI-only like
  K, and per the original gap-analysis note should reuse whatever
  picker component the music/video modules already have for their
  equivalent `/releases` endpoints, if one exists — check before
  building a new one.
- As always: no real `vite build` / `pip install` / `pytest` was
  possible in this sandbox (network disabled).

---

# Session 14 — Comics L (manual release picker) DONE

Next item off the Comics gap-analysis list after K. Backend already
had `GET /{item_id}/releases` (`app/routers/comics.py`, calling
`search_comic_releases`/`search_manga_releases` in
`app/services/search.py`) — frontend-only session, same as K.

**Investigated first, per the plan's "check before building a new
one":** no other module (movies/tv/music/books) has an equivalent
`GET /releases` endpoint or a dedicated picker component outside
`InteractiveResultsPanel`/`InteractiveResultsTable` in
`ui/src/components/media.jsx`. Comics' own item-level "Interactive
search" button already reuses `InteractiveResultsTable` (the plain
flat-list variant, not the fuller `Panel` with rejected/stats) — and
`/releases` returns exactly that shape, a bare ranked list. So the
existing component was the reuse target, not a new one.

**Confirmed `/releases` isn't just a dead duplicate of
interactive-search before wiring it up** (would've been consistent
with how this repo treats real duplicates — see the router-cleanup
session): `search_comic_releases`/`search_manga_releases` search
`COMIC_CATEGORY`/`MANGA_CATEGORY` and fall back to `BOOK_CATEGORY`
if empty; `interactive_comic_search`/`interactive_manga_search` (via
shared `interactive_generic_search`, also used by movies/tv/music/
books) do not have that fallback anywhere, for any media type — it's
not comics-specific tech debt, it's how the shared interactive path
works everywhere. So folding the fallback into interactive search
would've been a cross-module behavior change out of scope for a
comics-only session. `/releases` earns its keep: broader recall for
comics/manga mistagged as generic ebooks by an indexer, at the cost
of no rejection reasons/stats — a real, if narrow, distinct tool.

- `ui/src/api.js` — added `api.comics.releases(id)`.
- `ui/src/pages/comics.jsx` (`ComicDetailPage`) — new `manualPick()`
  fetches `/releases` and feeds the result into the *same*
  `ixResults`/`ixLoading` state and `InteractiveResultsTable` render
  that "Interactive search" already uses, so grabbing a manually-
  picked release goes through the identical `grabRel` → `/grab` path.
  New "Manual pick" button next to "Interactive search", with a title
  tooltip noting the tradeoff (ranked list, broader category
  fallback) since the two buttons look similar enough to need one.

Verified (no network, same constraints as every prior session):
`python3 -m py_compile` across every file in `app/` — 0 errors
(backend untouched); esbuild per-file checks on `comics.jsx`
(103.3kb) and `api.js` (25.2kb), full `app.jsx` bundle — 939.1kb, 0
errors; `check_ui_static.py` (57 jsx files, 50 icons — no new icon),
`check_version.py`, `check_lazy_exports.mjs` all pass.

**Not verified — needs a network-enabled environment:** a real
`vite build`; a browser smoke test — run Manual pick on a comic
whose only release is mistagged under Books and confirm it surfaces
where Interactive search comes up empty; grab from the Manual pick
results and confirm the item updates the same way a normal grab does.

## Still open

- Same testing-gap item, still unaddressed.
- Comics M (manga toggle + manga-only view) and O (`metatag_comic`
  path-safety + sidecar-vs-embedded XML) — still not started. Only
  O touches the backend; M is UI-only like K/L.
- As always: no real `vite build` / `pip install` / `pytest` was
  possible in this sandbox (network disabled).

---

# Session 15 — Comics M (manga toggle + manga-only view) DONE

Next item after L. Backend already had `GET /comics/manga` and
`PATCH /{item_id}/tag-manga` (`app/routers/comics.py`) — frontend-
only session, same shape as K and L.

**Read the two endpoints closely before wiring them, since they're
narrower than "manga" sounds:** `GET /manga` only queries
`MediaType.comic` rows and string-matches `quality_profile`/
`overview`/`file_path` for the word "manga" (or an exact
`quality_profile == "manga"`) — it deliberately excludes items
already stored as `MediaType.manga` (added via MangaDex), since
those obviously don't need "finding." `PATCH /tag-manga` just sets
`quality_profile = "manga"`, which is also the flag `GET /manga`'s
heuristic checks for. So these two exist to catch comics that were
added as plain ComicVine comics but are actually manga — not to
duplicate what MangaDex-sourced items already are.

Given that, a "Manga" filter that only called `GET /manga` would
hide real manga (`MediaType.manga`) from itself, which isn't what
anyone opening a "Manga" tab would expect. Frontend fix: the Manga
filter shows the *union* — items with `media_type === 'manga'` OR
a `GET /manga` hit — and "Comics" is the complement.

- `ui/src/api.js` — added `api.comics.manga()` and
  `api.comics.tagManga(id)`.
- `ui/src/pages/comics.jsx` (`ComicsPage`):
  - New `libFilter` state (`all`/`comics`/`manga`) + a 3-way button
    group next to the existing series filter input, same `join`
    styling as the Library/Story arcs/Pull list tab switcher already
    on the page.
  - `mangaIds` (a `Set`, from `GET /comics/manga`) is lazy-loaded the
    first time the person switches to Comics or Manga — mirrors how
    the Story arcs/Pull list tabs already only load on first visit,
    rather than fetching it unconditionally on every page load.
  - `filtered` now also filters on `libFilter`, treating an item as
    manga if `media_type==='manga'` or its id is in `mangaIds`.
  - (`ComicDetailPage`): new "Mark as manga" button, shown only for
    `media_type==='comic'` items not already tagged (`quality_profile
    !== 'manga'`) — calling `tagManga` then reloading, so the existing
    quality-profile badge (`MediaDetailShell`'s `qualityProfile` prop,
    already wired) immediately shows "manga" as visible confirmation
    without adding a new UI element for it.

Verified (no network, same constraints as every prior session):
`python3 -m py_compile` across every file in `app/` — 0 errors
(backend untouched); esbuild per-file checks on `comics.jsx`
(105.5kb) and `api.js` (25.3kb), full `app.jsx` bundle — 941.3kb, 0
errors; `check_ui_static.py` (57 jsx files, 50 icons — no new icon,
reused existing `join`/button styling), `check_version.py`,
`check_lazy_exports.mjs` all pass. Hand-checked every new frontend
path against the router's decorators — `GET /comics/manga` and
`PATCH /{item_id}/tag-manga` both match exactly.

**Not verified — needs a network-enabled environment:** a real
`vite build`; a browser smoke test — add a ComicVine comic that's
actually a manga, confirm it's invisible under the Manga filter
until "Mark as manga" is clicked, then confirm it appears there (and
disappears from Comics) without a page reload; confirm a true
MangaDex-sourced item shows under Manga from the start with no
tagging needed.

## Still open

- Same testing-gap item, still unaddressed.
- Comics O (`metatag_comic` path-safety + sidecar-vs-embedded XML)
  is the last item from the original gap analysis — backend-only,
  unlike K/L/M. Two distinct fixes bundled in one item: add the
  missing `_assert_under_library` check (ships-blocking, per the
  original note), and switch `ComicInfo.xml` from a sidecar file to
  a zip member for `.cbz`/`.zip` (real readers expect it embedded).
- As always: no real `vite build` / `pip install` / `pytest` was
  possible in this sandbox (network disabled).

---

# Session 18 — TV/Movies audit: Movies bulk-actions gap found & fixed

Requested follow-up: audit `tv.py`/`movies.py` the same way `overhaul.py`
and `parity.py` got audited in earlier sessions, since neither had had
that line-by-line pass done. Findings below.

## Route-ordering audit — clean, no bugs found

Walked every `@router.get/post/patch/delete` in both files in
registration order, same method as the `overhaul.py`/`parity.py`
passes. Neither file has the single-segment-catch-all-registered-
too-early bug that hit `music.py`'s `/incomplete` (fixed several
sessions back): every literal single-segment route (`/search`,
`/from-tmdb`, `/bulk`, `/refresh-series-status` on `tv.py`;
`/search`, `/search-missing`, `/bulk` on `movies.py`) is registered
*before* its file's single-segment `{id}` catch-all, or — in
`tv.py`'s case for `/bulk`/`/refresh-series-status` — there's no
competing single-segment POST catch-all in that file at all, so no
shadow risk either way.

## Duplicate-endpoint audit — clean, no bugs found

Grepped `overhaul.py`, `parity.py`, `discover.py`, `webhooks.py`,
and `requests.py` for anything movie/TV-shaped. Everything that
touches movies/TV outside their own routers is doing something
genuinely different, not a duplicate: `discover.py`'s `/movies/*` +
`/tv/*` are TMDb browse/trending (not library CRUD),
`parity.py`'s `/strm/movie` + `/trakt/trending/movies` are
streaming/discovery, `webhooks.py`'s episode-resolution helper
feeds `WatchProgress`/`ScrobbleEvent`, not the TV router. No leftover
`overhaul.py` shadow of either module survived the earlier
router-cleanup session.

## Real gap found: Movies had no bulk-actions UI, despite backend support

`ui/src/pages/movies.jsx` declared `const [selected, setSelected] =
useState({})` and `const [qp, setQp] = useState('')` at the top of
`MoviesPage` — and never used either anywhere else in the file.
Dead state, left over from an unfinished feature. Backend already
had everything needed: `POST /api/movies/bulk` (monitor +
quality-profile, identical shape to `tv.py`'s `/bulk`) and `PATCH
/{item_id}/desired-qualities`, neither ever called from the
frontend. `tv.jsx` has a full "Mass Editor" tab built on this exact
pattern (checkbox-per-card, bulk monitor/unmonitor, bulk search,
bulk profile apply) — Movies never got the equivalent, so browsing
`ui/src/api.js` showed the asymmetry too: `api.tv` includes nothing
bulk-shaped either (`tv.jsx`'s Mass Editor calls raw `fetch('/api/tv/
bulk', ...)` inline rather than through the wrapper) — but `movies`
had neither the wrapper nor the UI.

Fixed, matching the existing card-grid layout `movies.jsx` already
uses (no sidebar sub-tabs like `tv.jsx`, so didn't force that
structure onto it — added the bulk bar inline instead):

- `ui/src/api.js` — added `api.movies.bulk(body)`, mirroring the
  existing `movies.*` entries' style (`tv.jsx`'s own bulk call stays
  as a raw `fetch`, so this isn't introducing a new pattern, just
  filling the one hole in the `movies` object).
- `ui/src/pages/movies.jsx`:
  - Wired the previously-dead `selected`/`qp` state: added a
    `profiles` fetch (`api.settings.profiles()`, filtered to
    `media_type === 'movie'`, matching `tv.jsx`'s
    `media_type === 'tv'` filter) and `bulkMonitor` / `bulkSearchMissing`
    / `bulkApplyProfile` handlers.
  - Poster grid tiles now sit in a `relative group` wrapper with a
    hover-revealed checkbox overlay (`opacity-0 group-hover:opacity-100`,
    `stopPropagation` so it doesn't also open the detail page) — same
    visual pattern as `tv.jsx`'s series-grid checkboxes, adapted to
    wrap the shared `PosterTile` component instead of `tv.jsx`'s
    hand-rolled card markup (didn't touch `PosterTile` itself since
    it's shared with comics/books/etc. — the checkbox is a sibling
    overlay, not a prop `PosterTile` needs to know about).
  - A bulk-action bar (Monitor selected / Unmonitor selected / Search
    missing / quality-profile dropdown + Apply / Clear) appears above
    the grid whenever `selectedIds.length > 0`, same button set as
    `tv.jsx`'s Mass Editor tab minus the sidebar chrome.

**Verified:**
- `esbuild` per-file syntax checks on `movies.jsx` and `api.js` — 0
  errors.
- Full `esbuild --bundle` of `app.jsx` — 942.7kb, 0 errors, every
  import resolves.
- `python3 scripts/check_ui_static.py` — OK (57 jsx files, 50 icons
  — unchanged, no new icon used).
- `node scripts/check_lazy_exports.mjs` — OK.
- `python3 scripts/check_version.py` — OK (`1.01beta`).
- Full `py_compile` across every file in `app/` — 0 errors (backend
  untouched this session, ran anyway per the usual convention).
- Confirmed `media_type: str = "movie"` (not `"movies"`) in
  `app/routers/settings.py`'s profile schema before filtering on it,
  so the profile dropdown wouldn't silently come back empty.

**Not verified — needs a network-enabled environment:** a real
`vite build`; a browser smoke test — hover a movie tile, confirm the
checkbox appears and doesn't also trigger `setDetailId`, select a
few, confirm the bulk bar's monitor/unmonitor/search/profile actions
actually round-trip through `POST /api/movies/bulk` against a live
DB.

## Still open

- Same testing-gap item — zero dedicated test files for either
  `tv.py`/`movies.py`, same as everywhere else in this repo.
- No real `pip install`/`vite build`/`pytest` was possible in this
  sandbox (network disabled) — same constraint as every session.
- Didn't extend this same bulk-actions treatment to Books/Audiobooks/
  Podcasts — wasn't asked about those, and this session was scoped to
  "bring Movies to the same polish level as TV," not a library-wide
  bulk-actions sweep. Flagging in case that's wanted next.

---

# Session 17 — Comics N (dead ComicsPullPanel removed) DONE

Picked up the one item left over from the K→O run — Session 16's
"Still open" flagged that `N` got skipped by name each time L/M/O
were picked up.

`ComicsPullPanel` in `ui/src/pages/comics.jsx` was dead code: still
defined, still exported, but never imported or rendered anywhere
else (`grep -rn "ComicsPullPanel" ui/src/` outside `comics.jsx`
returns nothing) — confirmed the *earlier* router-cleanup session's
fix only repointed its `fetch()` calls from the removed
`/api/overhaul/comics/pull-list` endpoints to the working
`/api/comics/pull` ones; it never actually got wired into the page
UI. `ComicsPage`'s own "Pull list" tab (`loadPull`/`newPull` state,
the same `/api/comics/pull` endpoints) is the real, rendered
pull-list feature — this component was a fully redundant duplicate
of it, per the original gap-analysis note.

Removed the whole `ComicsPullPanel` function (lines 8–41) and its
name from the `export { ... }` statement at the bottom of the file.
Nothing else in `ui/src/` referenced it, so this is a straight
deletion, not a rewire.

**Verified:**
- Repo-wide grep for `ComicsPullPanel` outside `comics.jsx` — no
  hits (the only remaining reference is inside the stale prebuilt
  bundle `app/static/assets/comics-*.js`, same as every prior
  session's convention of ignoring build output that regenerates on
  the next `vite build`).
- `esbuild` per-file syntax check on `comics.jsx` — 0 errors.
- Full `esbuild --bundle` of `app.jsx` (react/react-dom/
  react-router-dom/hls.js externalized) — 938.7kb, 0 errors, every
  import still resolves.
- `python3 scripts/check_ui_static.py` — OK (57 jsx files, 50 icons
  — unchanged, no icon was ever exclusive to this component).
- `node scripts/check_lazy_exports.mjs` — OK.
- `python3 scripts/check_version.py` — OK (`1.01beta`).
- Backend untouched this session, so no `py_compile` regression risk
  — not re-run.

## Comics gap analysis — status

All of I through O are now done: I (session 8), J (12), K (13), L
(14), M (15), N (this session), O (16). No open items left from the
original gap list.

## Still open

- Same testing-gap item (449 lines of tests for service code that's
  now well over 20,768 lines), still unaddressed — flagged every
  session since the router-cleanup session, still the largest
  remaining item in this whole file.
- `parity.py`'s `/cf-bypass/test` and `/library-watch/status`
  overlaps were reviewed and left alone in session 10/11 as
  low-priority, confirmed-not-duplicate — no action needed, just
  noting they were a conscious "leave it" rather than an oversight.
- As always: no real `vite build` / `pip install` / `pytest` was
  possible in this sandbox (network disabled).

---

# Session 16 — Comics O (metatag_comic path-safety + embedded XML) DONE

Last item from the original Comics gap analysis. Unlike K/L/M this
one is backend-only — new service module plus a router rewrite, no
frontend caller exists yet (grepped `ui/src/` — nothing calls
`/metatag`).

**Two problems, both fixed, in a new `app/services/comic_metadata.py`:**

1. **Path safety.** The old inline version in `app/routers/comics.py`
   wrote straight to `item.file_path`'s parent with no check — every
   other file-writing service in this repo (`lyrics.py`,
   `tag_editor.py`, `comic_reader.py`, `media_player.py`) validates
   the target is under a library root first via `_assert_under_library`.
   Both new entry points (`embed_comicinfo`, `write_sidecar`) call it
   before touching disk.
2. **Sidecar → embedded.** `ComicInfo.xml` now gets written as a zip
   member inside `.cbz`/`.zip` archives — what ComicTagger/Kavita/
   ComicRack actually read — instead of a file sitting next to the
   archive that those tools never look at. Implementation mirrors
   `tag_editor.py`'s atomic-temp-copy pattern exactly: build a whole
   new zip in a temp file in the same directory (copy every existing
   member except a prior `ComicInfo.xml`, then write the new one),
   `os.replace()` into place only once the rebuild fully succeeds.
   zipfile has no in-place "replace one member" API, so a
   member-preserving rebuild is the correct way to do this without
   corrupting the archive or leaving duplicate entries.

**`.cbr`/`.rar` documented as a known limitation, not half-built:**
`unrar` (already shelled out to for *reading* .cbr in
`comic_reader.py`) is read-only, and RAR's own SDK is proprietary —
not worth vendoring for one feature. `write_sidecar()` is the
fallback for those, and for any other extension with no embed path,
so metadata isn't lost outright, just not embedded the way a
dedicated tagger would do it.

- `app/routers/comics.py`'s `metatag_comic` now dispatches to
  `embed_comicinfo` for `.cbz`/`.zip` and `write_sidecar` for
  everything else, and — matching how `music.py`'s tag-write
  endpoints already handle `TagWriteError` — raises `HTTPException
  (400, ...)` on `ComicMetaError` instead of the old behavior of
  swallowing any failure (including what would've been a path-safety
  rejection) into a `"path"` note while still returning `"ok": true`.
  Response gained an `embedded: bool` field so a caller can tell
  which path was taken.

**Verified for real, not just syntax-checked** — this is the one
piece of backend logic in the Comics work so far that's pure
stdlib (`zipfile`/`pathlib`/`tempfile`, no DB, no FastAPI) and
therefore actually exercisable without `pip install` in this
sandbox. Stubbed `app.config` (the only import blocked by the
missing `pydantic_settings` — same "no network" constraint as every
session) and ran `embed_comicinfo`/`write_sidecar` against a real
synthetic `.cbz` and a real folder-based comic:
  - embedding into a fresh `.cbz` → `ComicInfo.xml` appears as a zip
    member alongside the original page images, XML content correct
    including `html.escape` on a summary containing `&`/`<`/`>`.
  - re-embedding (simulating re-tagging) → exactly one
    `ComicInfo.xml` member afterward, not two — confirms the
    rebuild-and-replace approach doesn't duplicate entries.
  - `.cbr` (existing file, wrong extension) → `ComicMetaError:
    "Cannot embed metadata into .cbr files"`, original untouched.
  - path outside the stubbed library roots (`/etc/passwd`, `/etc`) →
    `ComicMetaError: "Path outside library roots: ..."` for both
    `embed_comicinfo` and `write_sidecar`.
  - folder-based comic → sidecar written to `<folder>/ComicInfo.xml`,
    matching the original folder-vs-file behavior.
  - no leftover `.metatag-*` temp files in the directory after either
    the successful runs or the failed ones.

Also: `python3 -m py_compile` across every file in `app/` — 0 errors;
`check_version.py`, `check_lazy_exports.mjs`, `check_ui_static.py` —
all pass (frontend untouched, confirming no regression).

**Not verified — needs a network-enabled environment:** `pip install`
+ a real backend import/boot check (this session's zip-logic test
had to stub `app.config` to route around the missing
`pydantic_settings` package); running the actual `POST /{item_id}/
metatag` endpoint through FastAPI end-to-end against a DB-backed
item; opening the resulting `.cbz` in a real reader (ComicTagger/
Kavita) to confirm it picks up the embedded metadata the way this
was written to satisfy.

## Comics gap analysis — status

All of K through O are now done:
- I — in-app reader (session 8)
- J — reading progress tracking (session 12)
- K — per-issue search/grab/monitor buttons (session 13)
- L — manual release picker (session 14)
- M — manga toggle + manga-only view (session 15)
- N — dead `ComicsPullPanel` code — **still not done**, see below
- O — `metatag_comic` path-safety + embedded XML (this session)

## Still open

- **N** was in the original gap list but got skipped over in the
  K→O run (L/M/O were picked by name each time, N never was) —
  `ComicsPullPanel` in `ui/src/pages/comics.jsx` is still exported
  and unrendered, still calling the nonexistent `/api/overhaul/
  comics/pull-list` endpoints. Cleanup, not a feature: delete the
  component and its export.
- Same testing-gap item (449 lines of tests for service code that's
  now noticeably larger than 20,768 lines), still unaddressed —
  this has been flagged every session since the router-cleanup
  session and is the largest remaining item in this whole file.
- As always: no real `vite build` / `pip install` / full `pytest`
  was possible in this sandbox (network disabled) — the direct
  zipfile-logic test above is a real exception to that, not a
  substitute for it everywhere else.

---

# MediaOs Music Addon — Finish & Ship

## Status as of this session (Aug 14 2026)

Almost everything below was already implemented when this session started
(carried over from a prior session/environment). This session did a full
manual + tooling-based code review (no network access, so no real
`npm install` / `vite build` / git push was possible — see "Verification
method used" at the bottom) and fixed two real bugs found along the way.

## 1. Setup

- [x] Repo present at root of this zip (already cloned; this **is**
      newguy467/MediaOs, currently on `main` — no feature branch created yet)
- [x] Explored repo structure to confirm baseline state

## 2. Implement Music Player Addon (re-apply previous work)

- [x] `ui/src/player/engine.js` (Web Audio engine, 10-band EQ, presets, crossfade)
- [x] `ui/src/player/store.js` (global music store: queue, transport, shuffle, repeat, likes, play counts)
- [x] `ui/src/player/useMusicPlayer.js` (React hook)
- [x] `ui/src/player/Visualizer.jsx` (canvas spectrum) — **had a bug, fixed this session**
      (log-bucket mapping used `minF = 0`, so `minF * pow(...)` was always 0 and every
      bar read the same frequency bin. Fixed to start at bin 1.)
- [x] `ui/src/player/Equalizer.jsx` (10-band EQ panel)
- [x] `ui/src/player/Lyrics.jsx` (synced LRC lyrics + plain fallback)
- [x] `ui/src/player/MusicPlayerBar.jsx` (persistent bar + Now Playing overlay)
- [x] 21 icons in `ui/src/icons.jsx` (Music, Play, Pause, SkipBack, SkipForward,
      Shuffle, Repeat, RepeatOne, Volume, VolumeMute, Queue, Lyrics, Mic, Sliders,
      Heart, HeartFill, Disc, Expand, Minimize, Gauge, X)
- [x] Styles appended to `ui/src/styles.css` (`.eq-slider`, `.lyrics-scroll`, `mr-nowplaying-in` animation)
- [x] `ui/src/app.jsx` renders `<MusicPlayerBar />` and lazy-loads `MusicPage`/`MusicDetailPage`
- [x] `ui/src/pages/music.jsx` rewritten (hierarchy/grid/incomplete/liked views, play buttons, queue actions, per-track like/queue controls)
- [x] `app/services/lyrics.py` (sidecar `.lrc`/`.txt` → embedded tags via mutagen → LRCLIB fallback)
- [x] `GET /api/music/lyrics` endpoint added to `app/routers/music.py`

## 3. Bugs found & fixed this session

- [x] **Route-ordering bug** in `app/routers/music.py`: `GET /incomplete` and
      `GET /wanted-hierarchy` were registered *after* the generic
      `GET /{item_id}` route. Since both are single path-segment routes,
      Starlette/FastAPI would match `/api/music/incomplete` against
      `/{item_id}` first (item_id="incomplete" → 422, since it's not an int),
      and the real handler was never reached. This broke the "Incomplete" tab
      in the rewritten music page. **Fixed** by moving both routes above
      `GET /{item_id}` (they now sit right after `/lyrics`, which was already
      correctly placed before `/{item_id}`).
- [x] **Visualizer log-bucket bug** — see above under Visualizer.jsx.

## 4. Verify — resolved this session

- [x] **`scripts/check_ui_static.py`**: root cause found — the regex
      `^\s{2}(\w+):\s+` requires a space after the colon, and
      `SkipForward:()=>` had none (every other key in the file has the
      colon padded, e.g. `Home:       ()=>`). It's a formatting-only
      miss, not a missing key. Added the space; `check_ui_static.py`
      now passes (`56 jsx files, 49 icons used`).
- [x] **`scripts/check_version.py`**: `VERSION` (`1.01beta`) didn't match
      `package.json`/`package-lock.json`, which both already agree on
      `2.0.27-dev`. Set `VERSION` to `2.0.27-dev` to match. Passes now.
- [x] Re-ran the same no-network verification suite after both fixes:
      `python3 -m py_compile` on touched backend files, esbuild per-file
      syntax checks, a full esbuild `--bundle` of `app.jsx`
      (react/react-dom/react-router-dom/hls.js externalized) — 0 errors,
      819.2kb bundle — and `node scripts/check_lazy_exports.mjs`. All OK.
- [x] Confirmed `httpx` was already in `requirements.txt`; added
      `mutagen==1.47.0`, which was missing (needed for the embedded-tag
      lyrics path in `app/services/lyrics.py` to actually work in
      production instead of silently no-op'ing via its `except
      ImportError`).

## 4b. Still open — needs network access, could not be done in this sandbox

- [ ] Install UI deps & run a **real** `vite build` (Tailwind/PostCSS/
      daisyUI processing, `import.meta.env`, the project's actual JSX
      transform config — none of that is exercised by esbuild alone).
- [ ] `pip install -r requirements.txt` + real backend import check
      (fastapi/sqlalchemy/pydantic aren't installed in this sandbox, so
      only syntax was checked, not imports).
- [ ] Manual/browser smoke test of the music page once a build is
      running: play/pause/seek, shuffle, repeat modes, like/unlike
      persistence across reload, EQ presets + custom band drag,
      crossfade slider, lyrics sync scroll + click-to-seek, queue
      drag-reorder, Incomplete tab, Liked tab.

## 5. Ship

- [x] Created feature branch `feature/music-addon-finish`
- [x] Committed (`aca9fa9`) with a descriptive message covering the addon,
      both bug fixes, and both verify-script fixes
- [ ] Push — **not possible in this sandbox** (network access disabled).
      The commit is sitting locally on `feature/music-addon-finish`,
      one commit ahead of `main` (`154c533`). Push it and open a PR from
      an environment with GitHub access, e.g.:
      `git push -u origin feature/music-addon-finish`
- [ ] Open PR with descriptive summary — call out the route-ordering fix
      and visualizer fix specifically (the route fix is a *reorder*, not
      new code, and a lazy diff review might miss why it matters)

## Verification method used this session (no network access)

The sandbox had `network_configuration: Enabled: false`, so `git clone`,
`npm install`, `pip install`, and any GitHub push were all impossible. In
place of that, this session did:
- `python3 -m py_compile` on every touched backend file (syntax only)
- Manual read-through of every touched frontend file, cross-checking
  every `Ic.X` icon reference against `icons.jsx` exports, every
  `store.js`/`engine.js` method call against their class definitions, and
  every frontend `fetch()`/`api.music.*` call against the actual FastAPI
  routes in `app/routers/music.py`
- `esbuild` (found preinstalled under
  `~/.npm-global/lib/node_modules/tsx/node_modules/esbuild`) per-file
  syntax checks on all touched `.js`/`.jsx` files
- A full `esbuild --bundle` of `ui/src/app.jsx` (React/react-dom/
  react-router-dom/hls.js externalized) — resolved every import across the
  whole app with zero errors, confirming no missing files/exports
- The repo's own `node scripts/check_lazy_exports.mjs` → passed
- The repo's own `python3 scripts/check_version.py` and
  `python3 scripts/check_ui_static.py` → **both currently fail**, see
  section 4 above

This is a reasonable substitute for confirming the code is well-formed and
internally consistent, but it is **not** equivalent to a real `vite build`
or running the FastAPI app — those still need to happen before shipping.

---

# Session 3 — status: A + B done and committed, C (PWA/offline) in progress

Branch `feature/music-addon-finish`, commits `aca9fa9` → `7b0b238` →
`da8df6d` (offline.js + store.js foundation, from session 2) →
`00a3851` (Continue Watching row, feature B) → `b68be10` (Global
search, feature A). Nothing is pushed — network access is still
disabled in this sandbox, same as every prior session; pushing and
opening the PR still needs to happen from an environment with GitHub
access.

Requested features:
1. Global search across all modules (movies/tv/music/books/comics/etc) — **done**
2. PWA polish + offline queue caching for music — **in progress, uncommitted, see section C**
3. Unified "Continue Listening/Watching" row on the dashboard — **done**

## A. Global search — DONE, committed (`b68be10`)

New `GET /api/search` in `app/routers/global_search.py`, registered in
`main.py`. Searches `MediaItem` (title + artist_name, all media types)
and `Game`, grouped by module. Frontend: `ui/src/components/GlobalSearch.jsx`
modal, opened via the sidebar's 'Search' nav item →
`mediaos-open-search` event (mirrors the AI-search pattern). Clicking a
result deep-links via `mediaos-open-item` — listener added to
`movies.jsx`/`tv.jsx`/`music.jsx`/`books.jsx`/`comics.jsx`.

Verified (no network, same constraints as before): `py_compile` on all
touched backend files; esbuild per-file checks on all touched JSX; a
full `esbuild --bundle` of `app.jsx` resolved with 0 errors at
971.5kb; `check_ui_static.py` and `check_lazy_exports.mjs` both pass.

Original investigation notes below are kept for reference (the plan
was implemented essentially as written).

**Key finding:** each module's existing `GET /api/<module>/search`
(`app/routers/movies.py`, `tv.py`, `music.py`, `books.py`, `comics.py`,
`audiobooks.py`) hits **external metadata providers** (TMDB, MusicBrainz,
OpenLibrary, ComicVine/MangaDex) to find new things to add — it does
NOT search your existing local library. A real unified search needs a
**new** endpoint that searches `MediaItem` (+ `Game`, separate table)
by title/artist across all media types already in the library.

**Backend plan** — new file `app/routers/global_search.py`:
```python
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import MediaItem, MediaType, Game

router = APIRouter(prefix="/search", tags=["search"])

MODULE_MAP = {
    MediaType.movie: ("movies", "Movies"),
    MediaType.tv: ("tv", "TV"),
    MediaType.music: ("music", "Music"),
    MediaType.book: ("books", "Books"),
    MediaType.audiobook: ("audiobooks", "Audiobooks"),
    MediaType.comic: ("comics", "Comics"),
    MediaType.manga: ("manga", "Manga"),
    MediaType.adult: ("adult", "Adult"),
}

@router.get("")
def global_search(query: str = Query(..., min_length=1), limit: int = Query(6, le=25),
                   db: Session = Depends(get_db)):
    q = (query or "").strip()
    if not q:
        return {"query": q, "groups": [], "total": 0}
    like = f"%{q}%"
    groups, total = [], 0
    for mt, (page, label) in MODULE_MAP.items():
        rows = (db.query(MediaItem)
                  .filter(MediaItem.media_type == mt,
                          (MediaItem.title.ilike(like)) | (MediaItem.artist_name.ilike(like)))
                  .order_by(MediaItem.title).limit(limit).all())
        if not rows:
            continue
        items = [{
            "id": r.id, "title": r.title,
            "subtitle": r.artist_name if mt == MediaType.music else (str(r.year) if r.year else None),
            "year": r.year, "poster_path": r.poster_path,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "media_type": mt.value, "page": page,
        } for r in rows]
        groups.append({"media_type": mt.value, "label": label, "page": page, "items": items})
        total += len(items)
    # Games: separate table, not MediaItem — same pattern, filter Game.title.ilike(like)
    # wrap in try/except like widget_dvr_jobs does elsewhere in this codebase, in case
    # the games module isn't migrated/enabled on some installs
    return {"query": q, "groups": groups, "total": total}
```
Register in `app/main.py`: add `global_search` to the big `from app.routers
import (...)` block, then `app.include_router(global_search.router,
prefix="/api")` alongside the others (put it near `music`/`overhaul`).

Note: `MediaItem.title.ilike()` / `.artist_name.ilike()` is portable
across Postgres and SQLite via SQLAlchemy — confirmed this is safe,
don't second-guess it next session.

**Frontend plan:**
- New component `ui/src/components/GlobalSearch.jsx` (or inline in
  app.jsx): a modal/dropdown, debounced fetch to `/api/search?query=`,
  renders `groups` with poster thumbnails. Reuse the existing
  poster-URL pattern already used elsewhere in the codebase:
  `c.poster_path.startsWith('http') ? c.poster_path : TMDB + c.poster_path`
  (see `ui/src/components/ui.jsx` line ~246 for the exact pattern,
  `TMDB` const is `'https://image.tmdb.org/t/p/w342'` from `ui/src/api.js`
  line 239).
- Trigger: add a search icon button — `ui/src/app.jsx` already has an
  `Ic.Search` icon imported and an existing `'ai-search'` nav item at
  line ~134 that dispatches `window.dispatchEvent(new CustomEvent('mediaos-open-ai'))`
  (consumed by `ui/src/AiChatPanel.jsx` line 45). **Mirror this exact
  pattern** for consistency: add a `'global-search'` nav item (or a
  dedicated button in the Sidebar/topbar) that dispatches
  `new CustomEvent('mediaos-open-search')`, and have the new
  `GlobalSearch` component listen for it the same way `AiChatPanel`
  listens for `mediaos-open-ai`. Mount `<GlobalSearch />` once near
  `<MusicPlayerBar />` in `app.jsx`'s top-level render.
- Deep-linking to the actual item (not just the module page): every
  content page already uses **local `detailId` state**, confirmed in
  `movies.jsx`, `tv.jsx`, `music.jsx`, `books.jsx`, `comics.jsx` (all
  five have `const [detailId, setDetailId] = useState(null)` and
  `if (detailId) return <XDetailPage .../>`). Plan: on search-result
  click, do `setPage(result.page)` then
  `window.dispatchEvent(new CustomEvent('mediaos-open-item', {detail: {mediaType: result.media_type, id: result.id}}))`.
  In each of the 5 page files, add a `useEffect` near the top that
  listens for `mediaos-open-item`, checks `e.detail.mediaType` matches
  that page, and calls `setDetailId(e.detail.id)`. This is 5 small,
  mechanical edits — same 3-4 lines in each file.
- `api.js`: add `api.search = (q, limit) => fetch(\`/api/search?query=${encodeURIComponent(q)}&limit=${limit||6}\`).then(r=>r.json())`
  near the top, following the existing per-module structure.

## B. Continue Listening/Watching row — DONE, committed (`00a3851`)

`widget_continue_watching()` in `app/services/dashboard_widgets.py` now
joins `MediaItem`/`Game` and returns title/media_type/poster_path/
subtitle/page instead of a bare id; orphaned progress rows (item since
deleted) are skipped. `dashboard.jsx`'s `continue_watching` widget
renders real poster cards with a progress bar; clicking one navigates
via the same `mediaos-open-item` event global search uses.

Original investigation notes below are kept for reference (the plan
was implemented essentially as written).

function `widget_continue_watching()` (around line 249), only returns
raw `media_item_id`/`game_id`/`progress_percent`/`last_watched_at`/
`source` — no title, no artwork, no media type. That's why the current
dashboard card (`ui/src/pages/dashboard.jsx` line ~354-368,
`continue_watching` widget def) literally renders
`#{c.media_item_id||c.game_id} — {progress}%` — it has nothing else to
show.

**Backend fix** — rewrite `widget_continue_watching` in
`app/services/dashboard_widgets.py` to join `MediaItem` (and `Game` for
game_id rows):
```python
def widget_continue_watching(db: Session, limit: int = 12) -> list[dict]:
    from app.models import WatchProgress, MediaItem, Game
    rows = (db.query(WatchProgress)
              .filter(WatchProgress.progress_percent > 0, WatchProgress.progress_percent < 90)
              .order_by(WatchProgress.last_watched_at.desc())
              .limit(limit).all())
    # module/page-key map — reuse same mapping as global_search.MODULE_MAP,
    # consider importing it from there instead of duplicating
    out = []
    for p in rows:
        title = subtitle = poster = media_type = page = None
        if p.media_item_id:
            item = db.get(MediaItem, p.media_item_id)
            if item:
                title = item.title
                media_type = item.media_type.value if hasattr(item.media_type, "value") else str(item.media_type)
                poster = item.poster_path
                subtitle = item.artist_name if media_type == "music" else (str(item.year) if item.year else None)
                page = {"movie":"movies","tv":"tv","music":"music","book":"books",
                        "audiobook":"audiobooks","comic":"comics","manga":"manga","adult":"adult"}.get(media_type)
        elif p.game_id:
            g = db.get(Game, p.game_id)
            if g:
                title, media_type, poster, page = g.title, "game", g.poster_path, "games"
        if not title:
            continue  # orphaned progress row — item was deleted
        out.append({
            "media_item_id": p.media_item_id, "game_id": p.game_id, "title": title,
            "subtitle": subtitle, "media_type": media_type, "poster_path": poster, "page": page,
            "progress_percent": p.progress_percent, "last_watched_at": p.last_watched_at.isoformat() if p.last_watched_at else None,
            "source": p.source,
        })
    return out
```

**Frontend fix** — `ui/src/pages/dashboard.jsx`, the `continue_watching`
widget's `render()` (around line 354): replace the plain-text `#id —
pct%` line with real cards — poster thumbnail (same TMDB-or-absolute
pattern as elsewhere), title, subtitle, a `<progress>` bar using
`c.progress_percent`, and `onClick` that does the same
`setPage(c.page)` + `mediaos-open-item` dispatch as global search (see
section A) so clicking a Continue card jumps straight into that item's
detail view. For `media_type === 'music'` rows specifically, consider
also offering a direct "Resume" play button that calls into
`musicStore` (`ui/src/player/store.js`) rather than only opening the
detail page — nice-to-have, not required for a correct fix.

## C. PWA + offline music caching — DONE, committed

`ui/public/manifest.webmanifest` (new), `ui/public/sw.js` (new,
cache-first + manual Range-slicing for `/api/player/stream` against the
same `mediaos-audio-v1` cache `offline.js` writes into,
stale-while-revalidate for the app shell, network-only for everything
else under `/api/*`), SW registration added to `ui/src/main.jsx`, and
an offline-toggle button (`Ic.Download`, active/busy states via
`store.isOffline`/`isOfflineBusy`) plus a "Download all" queue button
added to `QueuePanel()` in `ui/src/player/MusicPlayerBar.jsx`.

No 512×512 icon exists in the repo, so the manifest ships with the
existing 192×192 and 256×256 icons only — flagged as a gap, not
blocking.

Verified (no network, same constraints as prior sessions): esbuild
per-file checks on `main.jsx` and `MusicPlayerBar.jsx`; `node --check`
on `sw.js`; JSON-validated `manifest.webmanifest`; full esbuild
`--bundle` of `app.jsx` — 0 errors, 893.8kb; `check_ui_static.py` (57
jsx files, 49 icons) and `check_lazy_exports.mjs` both pass.

Original investigation notes below are kept for reference (the plan
was implemented essentially as written).

### Original notes (partially built, UNCOMMITTED, as of prior session)

**Confirmed:** `ui/index.html` already references
`<link rel="manifest" href="/manifest.webmanifest">` but **no such file
exists anywhere in the repo** — this 404s right now, so the app is not
actually installable despite having icon assets ready
(`ui/public/icon-192.png` 192×192, `logo-icon.png` 256×256,
`logo-icon-64.png` 64×64, `favicon.png` 32×32 — no 512×512 icon exists,
reuse `logo-icon.png` at 256 or ask the user for a 512 export). No
service worker exists either.

**Audio URL pattern confirmed:** `ui/src/player/store.js`,
`streamUrl(path) = "/api/player/stream?path=" + encodeURIComponent(path)`
— this is the URL a service worker needs to serve from cache when
offline. `<audio>` elements typically issue **Range-header** requests
even for same-origin src, so a naive full-response cache won't
transparently serve seeks — the SW fetch handler needs to manually
slice a `Response` body against the `Range` header and return a `206`
with `Content-Range`/`Content-Length` when serving from cache. Not yet
written — this is the trickiest remaining piece.

**Done so far (uncommitted):**
- `ui/src/player/offline.js` — NEW file, complete. Thin wrapper around
  the `Cache Storage API` (`caches.open('mediaos-audio-v1')`), all
  functions written and working: `offlineSupported()`, `isTrackCached(url)`,
  `cacheTrack(url)` (fetches the full un-ranged response and
  `cache.put`s it — deliberately full-body so the SW can slice ranges
  out of it later), `uncacheTrack(url)`, `cachedTrackUrls()`,
  `offlineCacheSizeEstimate()` (via `navigator.storage.estimate()`).
- `ui/src/player/store.js` — MODIFIED, not yet committed:
  - imports `cacheTrack, uncacheTrack, cachedTrackUrls, offlineSupported`
    from `./offline.js`
  - constructor: added `offline: {}` and `offlineBusy: {}` to
    `this.state`, calls new `this._hydrateOffline()` at the end
  - new methods added right after the constructor: `_hydrateOffline()`
    (async, best-effort — checks which queued tracks' stream URLs are
    already in the Cache Storage bucket on load and seeds
    `state.offline`), `isOffline(item)`, `isOfflineBusy(item)`,
    `toggleOffline(item)` (async — caches or uncaches a track by path,
    guards against double-clicks via `offlineBusy`), `cacheQueueForOffline()`
    (loops the whole queue and caches anything not yet cached).
  - **Not yet verified with esbuild/py_compile this session** — do
    that first thing next session before building on top of it.

**Still to build (done this session, notes kept for reference):**

1. **`ui/public/manifest.webmanifest`** (new file) — standard PWA
   manifest: `name`/`short_name` "MediaOS", `start_url: "/"`,
   `display: "standalone"`, `background_color`/`theme_color` matching
   the `<meta name="theme-color" content="#0b0914">` already in
   `index.html`, `icons` array pointing at `/icon-192.png` (192×192,
   exists) and ideally a 512 (doesn't exist yet — either generate one
   from `logo-icon.png` or just ship 192 alone and note the gap).

2. **`ui/public/sw.js`** (new file) — vanilla JS, no build step needed
   since Vite's `publicDir: "public"` copies it as-is (confirmed in
   `vite.config.js`). Needs three strategies in the `fetch` handler:
   - App shell / static assets (same-origin JS/CSS/images under
     `/assets/`, `/logo*`, `/icon*`, the HTML document): stale-while-
     revalidate or network-first-with-cache-fallback, precached on
     `install`.
   - `/api/player/stream` requests: **cache-first against the
     `mediaos-audio-v1` cache** (same name as `OFFLINE_CACHE` in
     `offline.js` — keep these in sync), with manual Range-header
     handling: if a cached full response exists for the URL, parse
     `Range: bytes=start-end` from the incoming request, slice the
     cached response's `ArrayBuffer`, and return a `new Response(slice,
     {status: 206, headers: {'Content-Range': ..., 'Content-Length':
     ..., 'Accept-Ranges': 'bytes'}})`. If no cached entry, fall
     through to `fetch(event.request)` (normal network streaming).
     **Do not auto-cache stream responses on the fly** — caching only
     happens explicitly via `offline.js`'s `cacheTrack`, to avoid
     unbounded storage growth from ordinary listening.
   - Everything else (all other `/api/*` — mutating calls, lists,
     etc.): just `fetch(event.request)`, no offline support attempted
     or expected.

3. **Register the SW** — in `ui/src/main.jsx`, after `mount(el)`, add:
   ```js
   if ("serviceWorker" in navigator) {
     window.addEventListener("load", () => {
       navigator.serviceWorker.register("/sw.js").catch(() => {});
     });
   }
   ```

4. **Offline toggle UI** — `ui/src/player/MusicPlayerBar.jsx`,
   `QueuePanel()` function (line 243): add a per-track offline toggle
   button next to the existing like/remove buttons (line ~276-285
   shows the exact pattern to copy — `btn btn-ghost btn-xs btn-circle
   opacity-0 group-hover:opacity-100`). Use `Ic.Download` (already
   exists in `icons.jsx`) with a filled/active style when
   `store.isOffline(it)` is true, spinner or disabled state when
   `store.isOfflineBusy(it)`, `onClick={(e) => { e.stopPropagation();
   store.toggleOffline(it); }}`. Also consider a "Download queue for
   offline" button near the existing `Clear` button (line 254) calling
   `store.cacheQueueForOffline()`.

5. **Verify**: esbuild per-file on `offline.js`, `store.js`,
   `MusicPlayerBar.jsx`, `main.jsx`; full esbuild bundle of `app.jsx`
   again; `python3 scripts/check_ui_static.py` (new icon usage, if
   any); manual reasoning check that `OFFLINE_CACHE` name in
   `offline.js` and the cache name used in `sw.js` are identical
   strings (`mediaos-audio-v1`) — a mismatch here silently breaks
   everything.

## Next-session startup checklist

1. `cd` into the repo, confirm still on `feature/music-addon-finish`.
2. `git log --oneline -5` — should show the PWA/offline commit on top
   of `b68be10` (global search) on top of `00a3851` (continue
   watching) on top of `da8df6d` (offline foundation). Features A, B,
   and C are all committed now; `git status --short` should be clean.
3. **All three originally-requested features (A, B, C) are done.**
   What's left from that batch is purely the "needs network access"
   items already listed in section 4b above (real `vite build`,
   `pip install` + import check, and a browser smoke test — including
   of the new SW/offline flow: toggle a track offline, go offline in
   devtools, confirm it still plays and seeks via Range requests
   served from the SW).
4. Push and open the PR from an environment with GitHub access — still
   not possible in this sandbox (network access disabled):
   `git push -u origin feature/music-addon-finish`
5. Update this file's checkboxes as you go, same as prior sessions.
6. **New batch (session 4-5): scrobbling, gapless, music smart playlists,
   radio mode, tag editor.** D (Last.fm/ListenBrainz scrobbling) and E
   (crossfade/gapless) are done and committed — see sections D and E
   above. Note E also *fixed* crossfade itself, which turned out to be a
   no-op before this session despite earlier notes claiming otherwise —
   don't re-trust old planning-note claims about "already implemented"
   without reading the code first, same lesson that prompted this note.
   Continue with F → H in order; each is written to stand alone so this
   order isn't a hard dependency chain, but F and G share the
   "genre/mood on MediaItem" gap and D/H share the mutagen file-open
   pattern, so doing them in sequence avoids re-deriving the same
   groundwork twice.
   **Update (session 6):** F's backend half is done and verified but
   **uncommitted** — models/migrations/service/router for music smart
   playlists, see section F below for the full breakdown. F's frontend
   (api.js helpers, wiring the play-count ping into store.js, the actual
   Smart Playlists tab in music.jsx, and genre/mood editing UI on the
   album detail page — there's currently no way to tag an album at all
   without a raw API call) is **not started**. Do that first next
   session, in the order listed in F's "NOT done" list, before moving on
   to G — G was scoped to reuse `MediaItem.genre`, which now exists, but
   the feature isn't end-to-end usable until F's frontend lands.

---

# Session 4 (planned) — music feature batch: D–H

Confirmed by direct code inspection (not assumption) that none of
these exist yet:
- No Last.fm/ListenBrainz client anywhere in `app/clients/` — only
  `trakt.py` exists for scrobble-out, and `scrobbling.py` only exposes
  `POST /scrobble/trakt/push`.
- `engine.js` has crossfade (0–12s slider, `this.crossfade` in
  `store.js`/`engine.js`) but no gapless mode.
- `smartlists.py`/`smartlists.jsx` are entirely movie/TV/book-oriented
  (`tmdb_list`, `trakt_trending`, `imdb_chart`, filtered by
  year/vote_average) — nothing branches on `MediaType.music`.
- `musicbrainz.py` client has search/lookup methods only — no
  similarity or recommendation logic exists in `music.py` or
  `music_hierarchy.py`.
- `lyrics.py` opens files with `mutagen.File(path, easy=False)` to
  *read* tags only. No write path (`.save()`, `EasyID3`, etc.) exists
  anywhere in the repo.

## D. Last.fm / ListenBrainz scrobbling

**Backend:**
- New `app/clients/lastfm.py` and `app/clients/listenbrainz.py`,
  mirroring `TraktClient`'s shape (`enabled()`, a `scrobble()` method).
  Last.fm's `track.scrobble` API needs an MD5-signed request
  (api_key + api_secret + session key) — see Last.fm API docs for the
  signing scheme; ListenBrainz is a simpler bearer-token POST to
  `https://api.listenbrainz.org/1/submit-listens` with
  `listen_type: "single"` and a `track_metadata` object
  (artist_name/track_name/release_name/duration_ms — all of which
  `MusicTrack` + its parent `MediaItem.artist_name` already have).
- `app/config.py`: add `lastfm_api_key`, `lastfm_api_secret`,
  `lastfm_session_key`, `lastfm_scrobble_out: bool = True`,
  `listenbrainz_token`, `listenbrainz_scrobble_out: bool = True` —
  same pattern as the existing `trakt_*` settings block (~line 213).
- `app/routers/scrobbling.py`: add `POST /scrobble/lastfm/push` and
  `POST /scrobble/listenbrainz/push`, mirroring `trakt_push` (~line
  202) almost exactly, but sourcing title/artist from `MusicTrack` +
  `MediaItem.artist_name` instead of tmdb/imdb ids (music has no
  tmdb/imdb id — `external_source == "musicbrainz"` on the album
  `MediaItem`, and the MBID is more useful to ListenBrainz's
  `additional_info.recording_mbid` than to Last.fm, which has none of
  this — pass it only to LB).
- Consider a shared `_music_scrobble_targets(db, track)` helper that
  both new endpoints call into, since the metadata-gathering (track →
  album → artist_name) is identical for both providers and only the
  outbound payload shape differs.

**Frontend:**
- `ui/src/player/store.js`: the existing `_scrobbled` flag (line 55,
  set false on line 199, checked at line 276) already fires roughly at
  the "50%+ played" threshold that both Last.fm and ListenBrainz
  expect for a scrobble to count — reuse that trigger point, don't add
  a second timer. Where it currently just sets `this._scrobbled = true`
  (line 281), also fire `api.scrobbleMusic(item)` (new `api.js`
  helper) which POSTs to whichever of `/api/scrobble/lastfm/push` /
  `/api/scrobble/listenbrainz/push` are enabled (check via a settings
  endpoint, or just let the backend no-op per its own
  `*_scrobble_out` flag like Trakt already does — simpler, mirrors
  existing pattern).
- Settings UI: `ui/src/pages/scrobbling.jsx` already exists for
  Trakt-style settings — extend it with Last.fm/ListenBrainz
  credential fields following whatever form pattern it already uses
  for Trakt (read the file first; don't assume the shape).

**Note:** Last.fm requires an authorized session key obtained via a
one-time OAuth-ish handshake (user visits a Last.fm auth URL, app
exchanges a token for a session key) — this is the fiddliest part and
worth scoping as its own sub-step rather than assuming a simple
api-key-only flow like ListenBrainz's.

## D. Last.fm / ListenBrainz scrobbling — DONE, committed

**Backend:**
- `app/clients/lastfm.py` (new) — signed `track.scrobble` client
  (`enabled()` checks api key + secret + session key; `_sign()` implements
  Last.fm's sorted-param+secret md5 signing scheme; `scrobble()` posts to
  `ws.audioscrobbler.com`). Obtaining the session key itself is a one-time
  out-of-band OAuth-ish handshake (auth.getToken → user authorizes in
  browser → auth.getSession) — **not** implemented in-app, same as Trakt's
  access token is just pasted into Settings rather than a full in-app OAuth
  flow.
- `app/clients/listenbrainz.py` (new) — bearer-token client, POSTs to
  `api.listenbrainz.org/1/submit-listens` with `listen_type: "single"`,
  passing `recording_mbid` into `additional_info` when available.
- `app/config.py` — added `lastfm_api_key`, `lastfm_api_secret`,
  `lastfm_session_key`, `lastfm_scrobble_out: bool = True`,
  `listenbrainz_token`, `listenbrainz_scrobble_out: bool = True`, same
  pattern as the existing `trakt_*` block.
- `app/services/app_settings.py` — wired all six into the existing
  `metadata` settings group (right next to Trakt) — this means they show
  up in the Settings UI automatically via the generic `ConfigGroupPage`
  form, **no new frontend settings page was needed**.
- `app/routers/scrobbling.py` — new `POST /scrobble/lastfm/push` and
  `POST /scrobble/listenbrainz/push`, both taking a `track_id` and sourcing
  title/artist/album/duration/MBID from the DB via a shared
  `_music_scrobble_meta()` helper (looks up `MusicTrack` → parent album
  `MediaItem.artist_name`) rather than trusting client-supplied metadata —
  mirrors how `trakt_push` looks up tmdb/imdb ids from the DB instead of
  the request body. Each endpoint no-ops (`{"ok": false, "reason":
  "disabled"}`) when its `*_scrobble_out` flag is off, same pattern as
  Trakt.

**Frontend:**
- `ui/src/api.js` — new `api.scrobble.lastfm(trackId)` /
  `api.scrobble.listenbrainz(trackId)` helpers.
- `ui/src/player/store.js` — `_maybeScrobble()` (the existing ~50%-played
  threshold that already drove local play-count tracking) now also calls
  new `_scrobbleOut(item)`, which fires both push calls unconditionally
  and fire-and-forget (`.catch(()=>{})` — a failed/disabled push must
  never interrupt playback). The backend's own `*_scrobble_out`/
  `enabled()` checks decide whether anything actually goes out, exactly as
  planned last session — no settings check needed on the frontend.

**Not done — scoped out:** a dedicated Last.fm/ListenBrainz section in the
settings UI beyond the generic config-group form (not needed, see above);
`track.updateNowPlaying` (only `track.scrobble` was implemented, matching
the "push a completed play" scope this was planned for).

Verified (no network, same constraints as every prior session):
`python3 -m py_compile` on all 5 touched/new backend files; `esbuild`
per-file checks on `api.js` and `store.js`; a full `esbuild --bundle` of
`app.jsx` — 0 errors, 894.9kb; `check_ui_static.py` (57 jsx files, 49
icons), `check_lazy_exports.mjs`, and `check_version.py` all pass.

## E. Gapless playback — DONE, committed (`eab4938`)

**Correction to the plan above, found by reading the actual code before
touching it (glad I checked — the plan's premise was wrong):** crossfade
did **not** already do dual-`<audio>` overlap-and-fade. `engine.js` had a
single `<audio>` element; `setCrossfade()` only stored a number, and
store.js's old `_maybePrefetchCrossfade` set a `_cfDone` flag and did
nothing else — no gain ramp, no second deck. Crossfade was, in effect, a
no-op. Built both crossfade *and* gapless together on a real dual-deck
architecture instead of layering gapless on top of a fake crossfade.

`engine.js` rewritten around two `<audio>` elements ("decks"), each with
its own `MediaElementSourceNode` → per-deck `GainNode`, both feeding into
one shared EQ filter chain → analyser → master gain → destination (Web
Audio nodes sum multiple inputs, so this works without duplicating the
10-band EQ). `engine.prepareNext(url)` preloads the idle deck;
`engine.tickCrossfade(ct, dur)` — called from store's `timeupdate` — starts
a real `linearRampToValueAtTime` overlap when crossfade > 0 and the
prefetch is ready, handing off "now playing" to the incoming deck
immediately via a new `trackadvance` event rather than at the end of the
fade. Gapless (`crossfade === 0 && gaplessEnabled`) flips decks instantly
on the active deck's `ended` event if the prefetch was ready in time;
falls back to the old full-reload path otherwise. `setCrossfade(>0)` and
`setGaplessEnabled(true)` are mutually exclusive, enforced in `engine.js`
itself (not just the UI) so no caller can get them both on at once.

`store.js` keeps owning queue/shuffle/repeat — engine has no playlist
knowledge. New `_peekNextIndex()` computes what would play next without
mutating state, caching the random pick for shuffle so the prefetched
track and the eventual real advance agree instead of rolling twice.
`_onEngineAdvance()` syncs store state when the engine flips decks on its
own (no second network load). Every queue-mutating method
(`enqueueNext`/`removeAt`/`moveInQueue`/`toggleShuffle`/`cycleRepeat`)
invalidates any in-flight prefetch so a stale target can't get handed off.

`MusicPlayerBar.jsx`: added a "Gapless" toggle (reused `Ic.Disc`, no new
icon) next to the crossfade slider; the slider visually disables itself
while Gapless is on.

Also fixed a Web Audio edge case while at it: interrupting a crossfade
mid-fade (e.g. manual skip) now calls `cancelScheduledValues()` on both
decks' gain nodes, not just clearing the `setTimeout` — otherwise a
pending `linearRampToValueAtTime` automation keeps running under the new
track.

Verified (no network, same constraints as every prior session): esbuild
per-file checks on all three touched files; full esbuild `--bundle` of
`app.jsx` — 0 errors, 904.7kb; `check_ui_static.py` (57 jsx files, 49
icons) and `check_lazy_exports.mjs` both pass; `py_compile` across all
backend files (untouched this round) to confirm nothing else broke.

**Still needs real browser testing** — Web Audio timing behavior
(crossfade smoothness, gapless swap latency, whether `audio.play()` on a
preloaded-but-never-started element is fast enough to feel gapless)
varies by browser and isn't something esbuild/py_compile can confirm,
same caveat as the SW Range-slicing work from session 3.

## F. Smart/dynamic playlists for music

- `app/models.py` `SmartList` (~line 376) and `MediaItem` — check
  whether `SmartList` already has a generic-enough shape to add a
  `media_type == "music"` branch, or whether music-specific filter
  columns are needed (genre, mood, min play count, "added after X").
  `MediaItem` has no `genre` column today (only `Game.genres` at
  ~line 828) — decide whether to add
  `MediaItem.genre: Mapped[str | None]` (new Alembic migration,
  follow the pattern in `alembic/versions/20260810_0002_provider_ids_and_series_rules.py`
  for how prior columns were added) or derive genre from MusicBrainz
  data fetched at add-time and stored in `external_ids` JSON instead —
  a real column is simpler to filter/query on and matches how
  `genre_filter` already exists elsewhere (line 338) as a substring/OR
  pattern to copy.
- `app/services/smartlists.py`: add a `_music` source type (e.g.
  `"library_genre"`, `"library_mood"`, `"library_recent"`,
  `"library_most_played"`) that queries local `MediaItem`/`MusicTrack`
  + `WatchProgress.play_count` instead of hitting an external API like
  the existing TMDb/Trakt/IMDb sources do — this is a different shape
  from every existing `SUPPORTED_SOURCES` entry (~line 15), since
  those all pull *new* items to add, while a music smart playlist is
  filtering the *existing* library into a saved, live-updating view.
  Worth deciding: is this the same `SmartList` model repurposed, or a
  lighter-weight new concept (a saved query) — repurposing risks
  bending a "discover new items" model into a "filter my library"
  model that doesn't fit its other columns (`min_year`/`max_year`
  vote-average filters don't map cleanly to "recently added").
- `smartlists.jsx`: extend the page's list/create UI to branch on a
  music-oriented source type with genre/mood/play-count fields instead
  of the year/vote-average fields it currently shows.

## G. Radio / mix mode — DONE, committed (`55dcf76`)

**Design decision, confirmed by reading the actual client before writing
code (per the lesson from E and F above):** `app/clients/musicbrainz.py`
does not have a similarity endpoint, confirming the plan's option (b) was
never realistic — went with (a), a purely local heuristic.

`app/services/music_radio.py` (new) — `radio_queue(db, seed_track_id,
limit)` ranks candidates same-artist-different-album first, then
same-genre-different-artist (comma-list OR match against `MediaItem.genre`,
reusing the exact convention `music_smartlists._tag_filter` already
established), then falls back to most-played library-wide so a sparsely-
tagged library still returns a non-empty queue instead of coming back
empty. Only downloaded tracks are returned, same rule as smart playlists.

**Deviation from the original plan:** did not join `WatchProgress`/
`ScrobbleEvent` to de-prioritize recent repeats — checked both tables
first and neither tracks plays at the per-track level (`WatchProgress`
is keyed to the album `MediaItem`, and there's no time-aware per-track
play log, only `MusicTrack.play_count`, which is cumulative). De-
duplication against the seed and within one radio batch is enforced
instead; recency-aware exclusion would need a new time-stamped per-track
play-event table, which felt out of scope for this pass — noted here in
case a future session wants to add one.

`app/routers/music.py` — new `GET /api/music/radio?seed_id=&limit=`,
placed above `GET /{item_id}` (the route-ordering class of bug from an
earlier session).

Frontend: `store.js` gets a persisted `radioEnabled` flag + `toggleRadio()`
(same pattern as shuffle/repeat), and `next()`'s existing end-of-queue
branch now calls new `_extendRadio()` when radio mode is on — fetches
from the track that just finished, appends the results to the queue via
the same `lsSet`+`_set` pattern every other queue mutation uses, advances
into the first new track, and falls back to stopping (radio-off behavior)
on an empty/failed fetch. `MusicPlayerBar.jsx` gets a Radio toggle button
next to Repeat in both the compact bar and expanded Now Playing view,
reusing the existing (previously unused) `Ic.Radio` icon.

Verified (no network, same constraints as every prior session):
`python3 -m py_compile` on `music_radio.py`/`music.py`; esbuild per-file
checks on `store.js`, `api.js`, `MusicPlayerBar.jsx`; full esbuild
`--bundle` of `app.jsx` — 0 errors, 858.2kb; `check_ui_static.py` (57
jsx files, 49 icons), `check_version.py`, `check_lazy_exports.mjs` all
pass.

**Not verified — needs a network-enabled environment:** real `vite
build`; `pip install` + backend import check; a browser smoke test
seeding radio from a real track (the uploaded AJ McLean album is the
first real candidate for this, once it's actually imported into a
library — see the note in the previous chat turn about that still being
a manual/scan-path step, not yet done) and confirming: same-artist
candidates surface first, toggling radio off makes the queue stop
normally at the end instead of extending, and repeated end-of-queue
extensions don't loop the same handful of tracks.

Original planning notes kept below for reference — the heuristic
approach was implemented essentially as scoped, minus the
recency-exclusion piece noted above.

- `app/clients/musicbrainz.py` has no similarity endpoint —
  MusicBrainz itself doesn't really do "similar artists" well; likely
  need either (a) a same-genre/same-decade heuristic purely from local
  library data (reuse whatever genre field comes out of F above), or
  (b) call out to a real recommendation source. Decide this before
  writing code — don't assume MusicBrainz can do it.
- New `app/services/` module (e.g. `music_radio.py`) with a function
  like `radio_queue(db, seed_item_id, limit=20)` that returns
  candidate `MediaItem`/`MusicTrack` rows by genre + artist overlap +
  excluding what's already been played recently (join
  `WatchProgress`/`ScrobbleEvent` to de-prioritize repeats).
- `app/routers/music.py`: new `GET /api/music/radio?seed_id=` endpoint
  calling into it.
- Frontend: `store.js` — when the queue empties and a "radio mode"
  toggle is on, auto-fetch and append via the new endpoint instead of
  just stopping. Needs a `radioEnabled` state flag + a check in
  whatever method currently handles end-of-queue (find it before
  assuming its name).

**Next-session startup checklist:**
1. Confirm `55dcf76` is on top of `git log --oneline -3`.
2. If network access is available: import the AJ McLean album (files +
   cover.jpg uploaded this session) into a real library via scan-paths
   or the add flow, confirm its genre populates ("Pop", from ID3 tags),
   run the actual browser smoke test listed above.
3. Continue to H (tag editor) — see the corrected `## H. Tag editor`
   section below (this was previously mislabeled as a second "## G."
   heading; fixed this session, content unchanged).



**Design decision, made after reading the actual models first (per the
lesson from session 4's E section):** `SmartList` was **not** repurposed.
Its whole shape (`source_ref` against an external API, `min_year`/
`max_year`/`min_vote_average`, `last_added_count`) is built around
discovering and adding *new* items from TMDb/Trakt/IMDb. A music smart
playlist is the opposite — a saved, live-re-evaluated *filter over the
library already on disk*, with nothing to "run" or "add". Built a
separate `MusicSmartlist` model instead, per the todo's own note that
repurposing risked bending a "discover new items" shape into a "filter my
library" shape that doesn't fit.

**Backend — done, verified, not yet committed:**
- `app/models.py`:
  - `MediaItem.genre` / `MediaItem.mood` — nullable `String`, comma-
    separated tags, substring/OR-matched (same convention as
    `LiveTvVirtualChannel.genre_filter`, reused rather than invented).
    Generic on `MediaItem`, not music-only, so other modules can adopt the
    same columns later without another migration.
  - `MusicTrack.play_count` — `Integer default=0`, local play counter,
    separate from the Last.fm/ListenBrainz *outbound* scrobbling from
    session 4 (that pushes plays out; this counts them locally for
    filtering, and works whether or not scrobble-out is configured).
  - `MusicSmartlist` (new table) — `name`, `source` (one of
    `library_genre`/`library_mood`/`library_recent`/`library_most_played`),
    `genre_filter`, `mood_filter`, `added_within_days`, `min_play_count`,
    `result_limit`.
- `app/services/schema_migrate.py` — soft-migrate version `2.0.28` adds the
  two new columns for existing installs (`music_smartlists` itself is a
  brand-new table, so `create_all` handles it — no ALTER needed, same
  reasoning as every other new-table addition in this codebase).
- `alembic/versions/20260815_0008_music_genre_mood_smartlists.py` — new
  revision (`down_revision = "20260811_0007"`) mirroring the same two
  columns plus a `create_table`/`drop_table` pair for `music_smartlists`,
  with both `upgrade()` and `downgrade()` — matches the
  `docs/ALEMBIC_CI.md` requirement that new model changes get a reversible
  revision, not just a soft-migrate entry.
- `app/services/music_smartlists.py` (new) — `resolve_smartlist(db, sl)`,
  one function per source, returns already-downloaded tracks only
  (`file_path IS NOT NULL` — an undownloaded row can't be queued). Genre/
  mood sources query albums matching the tag filter, then pull their
  tracks; `library_recent` filters `MediaItem.added_at` against
  `added_within_days` (default 30 if unset); `library_most_played` queries
  `MusicTrack` directly ordered by `play_count desc`, filtered by
  `min_play_count` (default 1).
- `app/routers/music_smartlists.py` (new) — full CRUD (`GET`/`POST`/
  `PATCH`/`DELETE` on `/api/music-smartlists`) plus
  `GET /api/music-smartlists/{id}/tracks` which calls `resolve_smartlist`
  live on every request (no caching, no stored result set — by design,
  since "live-updating" is the whole point). Registered in `app/main.py`
  right after `music.router`.
- `app/routers/music.py`:
  - `PATCH /{item_id}` (existing album-update endpoint) now also accepts
    `genre`/`mood` query params — no new endpoint needed, this was the
    natural place since it already does partial updates on the same
    `MediaItem` row.
  - `MusicOut` — added `genre`/`mood` fields so the album detail view can
    read current tags back.
  - New `POST /track/{track_id}/played` — bumps `MusicTrack.play_count`.
    **Not yet called from anywhere** (see frontend gap below) — this is
    the piece that makes `library_most_played` actually accumulate data
    over time instead of staying at 0.

**Route-ordering check (learned the hard way in an earlier session):**
`music_smartlists.py` is its own router with its own prefix
(`/music-smartlists`), not routes bolted onto `music.py` — this sidesteps
the generic-`/{item_id}`-shadows-a-later-route class of bug entirely
rather than needing to re-verify ordering by hand. The one new route added
directly to `music.py` (`/track/{track_id}/played`) is a 3-segment path,
so it can't collide with the existing single-segment `/{item_id}`.

**Verified this session (no network, same constraints as every prior
session):** `python3 -m py_compile` on all 7 touched/new backend files;
`python3 scripts/check_version.py` and `check_ui_static.py` both still
pass (no frontend touched yet, so this is a no-op sanity check, not a
real signal); a full `esbuild --bundle` of `app.jsx` — 0 errors, 904.3kb,
unchanged from session 4's number since nothing frontend changed.

**NOT done — frontend, needed before this is usable at all:**
1. `ui/src/api.js` — add `api.musicSmartlists = { list, create, update,
   remove, tracks(id) }` (mirror the existing `api.smartlists` helper
   shape at ~line 196) and `api.music.trackPlayed = trackId =>
   fetch('/api/music/track/'+trackId+'/played', {method:'POST'})`.
2. `ui/src/player/store.js` — in `_scrobbleOut(item)` (~line 310, right
   next to the existing `api.scrobble.lastfm`/`.listenbrainz` calls), also
   fire `api.music.trackPlayed(item.id).catch(()=>{})`. Same
   fire-and-forget pattern, same trigger point — do **not** add a second
   threshold timer, reuse `_maybeScrobble`'s existing ~50%-played check.
   This is the piece that makes `library_most_played` non-empty.
3. `ui/src/pages/music.jsx` — add a `'smart'` option to the `view` state
   (currently `hierarchy | grid | incomplete | liked`, ~line 44) and a
   join-button next to the existing four (~line 106). New
   `SmartPlaylistsView` component, same shape as `LikedView` in this file:
   list existing smart playlists (`api.musicSmartlists.list()`), a small
   create form (name + source dropdown + the relevant filter field(s) —
   genre/mood text input, or a days number, or a min-plays number,
   switched on source), and clicking one calls
   `api.musicSmartlists.tracks(id)` and renders results with the same
   track-row markup `LikedView` already uses, reusing `trackToQueueItem`
   (~line 17) to build the queue and `musicStore.setQueue(...)` to play —
   don't reinvent either.
4. Album/track genre+mood editing — right now `genre`/`mood` can only be
   set via a raw PATCH call (curl/API client), there's no UI. Cheapest
   fix: two small text inputs on the existing album detail page
   (`MusicDetailPage`, ~line 275) near wherever `quality_profile` is
   already editable — read that pattern first rather than assuming its
   shape, same lesson as always. Without this, `library_genre`/
   `library_mood` smart playlists have nothing to match against on a
   fresh library.
5. Verify after 1–3: esbuild per-file on `api.js`, `store.js`,
   `music.jsx`; full esbuild `--bundle` of `app.jsx` again;
   `check_ui_static.py` (new icon usage, if any — plan is to reuse
   `Ic.Sliders` for the Smart tab, no new icon needed, but confirm after
   writing the JSX).
6. Ship: commit backend once frontend is at least functional (a
   half-shipped feature with a table and no UI is worse than not
   committing yet) — or commit backend now with a clear "frontend WIP"
   message if picking this up across multiple sessions again. Left
   uncommitted as of this session for that reason; `git status --short`
   currently shows the 4 modified + 3 new files listed above.

**Next-session checklist for F specifically:**
1. Start at frontend item 1 above (`api.js` helpers) — everything else
   depends on it.
2. Don't forget item 4 (genre/mood UI) — it's easy to build the whole
   smart-playlist UI and only notice at the end that there's no way to
   actually tag an album, same class of oversight as G/H below sharing a
   dependency.
3. After F frontend is done and verified, continue to G (Radio/mix mode)
   — note G was already planned to reuse whatever genre field came out of
   F, so `MediaItem.genre` from this session is exactly that dependency,
   already in place.

## H. Tag editor (metadata write-back)

- `app/services/lyrics.py` already has the read-side mutagen pattern
  (~line 34-40, `mutagen.File(path, easy=False)`) — new write path
  should live in its own module (e.g. `app/services/tag_editor.py`)
  rather than overloading `lyrics.py`, since this is a distinct
  concern (writing title/artist/album/track-number/cover art, not
  just reading lyrics).
- Use `mutagen.File(path, easy=True)` for simple text tags
  (title/artist/album/tracknumber — works across MP3/FLAC/M4A
  uniformly), but embedding cover art needs format-specific handling
  (`mutagen.id3.APIC` for MP3, `mutagen.flac.Picture` for FLAC,
  `mutagen.mp4.MP4Cover` for M4A) — there's no single easy-mode API
  for images, budget real time for this branch.
- `app/routers/music.py`: new `PATCH /api/music/track/{track_id}/tags`
  (text fields) and `POST /api/music/track/{track_id}/artwork` (image
  upload) endpoints. After a successful write, also update the
  corresponding `MusicTrack`/`MediaItem` DB columns so the library
  view and the write-back stay in sync (don't let the file and the DB
  drift).
- Frontend: a small edit modal on the album/track detail view in
  `music.jsx` — form fields for the text tags, an image upload/crop
  for artwork, calling the two new endpoints.
- Safety: write to a temp copy and swap-on-success rather than editing
  in place, so a crash mid-write can't corrupt the user's file —
  mutagen's `.save()` is not atomic by default.


---

# Session 6 — status: F DONE (`2305be4`, `514f998`); G (radio/mix mode) DONE, committed (`55dcf76`)

Branch `feature/music-addon-finish`, `2305be4` on top of `0302a2c`.
`git status --short` is clean except for `todo.md` itself and the
still-untracked `scripts/windows/` tooling (unrelated to F, left as-is).

Frontend built in the planned order and each step verified with esbuild
before moving to the next, per F's "NOT done" list:
- [x] `ui/src/api.js` — `api.musicSmartlists.{list,create,update,remove,tracks}`
      + `api.music.trackPlayed`
- [x] `ui/src/player/store.js` — `_scrobbleOut()` now also fires
      `api.music.trackPlayed(item.id)` on the existing ~50%-played
      threshold (no second timer added)
- [x] `ui/src/pages/music.jsx` — new `'smart'` view + join-button,
      `SmartPlaylistsView` component (list/create/expand-to-preview/play,
      mirrors `LikedView`'s track-row shape)
- [x] `ui/src/pages/music.jsx` — `MusicDetailPage` Tags card (genre/mood
      text inputs, Save → `api.music.update(id, {genre, mood})`) — this
      was the missing piece with no UI at all before this session

Verified (no network, same constraints as every prior session):
`python3 -m py_compile` on all touched/new backend files; esbuild
per-file checks on `api.js`, `store.js`, `music.jsx`; full esbuild
`--bundle` of `app.jsx` — 0 errors, 875.8kb; `check_ui_static.py` (57
jsx files, 49 icons), `check_version.py`, and `check_lazy_exports.mjs`
all pass.

**Not verified — still needs a network-enabled environment:** a real
`vite build`; `pip install -r requirements.txt` + backend import check
(fastapi/sqlalchemy aren't installed in this sandbox, so only syntax
was checked); a browser end-to-end smoke test of the actual loop —
create a smart playlist, tag an album with a genre, confirm it resolves
into the playlist, play it, and separately play a track past 50% and
confirm `play_count` increments so `library_most_played` isn't
permanently empty. Also still not pushed — `git push -u origin
feature/music-addon-finish` needs to happen from an environment with
GitHub access, same as every prior session.

**Next-session startup checklist:**
1. `cd` into the repo, confirm still on `feature/music-addon-finish`,
   confirm `55dcf76` is on top of `git log --oneline -3` (F committed as
   `2305be4`, G committed as `55dcf76`, both this session).
2. If a network-enabled environment is available, do the still-open
   verification for both F and G first (real build, real import check,
   browser smoke tests — including seeding radio mode from a real track)
   before starting new feature work — neither has been exercised
   end-to-end, only verified for internal consistency.
3. The AJ McLean "hi my name is Alex - EP" mp3s + cover.jpg uploaded this
   session are real test data with real ID3 tags (genre=Pop already set)
   — importing them via scan-paths or the add flow gives F and G their
   first real library data to test against instead of an empty table.
4. Continue to H (tag editor / metadata write-back) — see the corrected
   `## H. Tag editor` section above (previously mislabeled as a second
   "## G." heading; fixed this session).

## Tooling note (session 6, added after the F write-up above): Windows build/test scripts

`scripts/windows/` now has a full set of `.bat` scripts covering
everything a session normally has to explain how to run manually — see
`scripts/windows/README.md` for the full list. Short version:

- `01`–`06` cover frontend install/build, backend install/import-check,
  verify scripts, and pytest — Windows equivalents of the exact commands
  `.github/workflows/ci.yml` runs, plus the import-check step used to
  verify sessions in this sandbox (which can't run `pip install` at all
  due to no network access — see session 5's write-up on that).
- `07`/`08` run the app locally (sqlite, no Docker) or the full Docker
  stack.
- `09` is the alembic upgrade/downgrade/upgrade round-trip from
  `docs/ALEMBIC_CI.md` — relevant to F's new migration
  (`20260815_0008_music_genre_mood_smartlists.py`) once there's a
  Windows box available to actually run it.
- `dashboard.bat` opens a small red/black GUI (an HTA) with a button per
  script; `menu.bat` is a console-only fallback if HTA is blocked by
  policy.

This doesn't change anything about F's status above — still backend-done/
frontend-not-started — it's just the tooling to make the next session's
verification steps (and the "real vite build" / "browser smoke test"
gaps noted in session 5, which this sandbox genuinely cannot run) doable
on a real Windows machine without re-deriving the commands each time.

---

# Session 7 — status: H (tag editor / metadata write-back) DONE, uncommitted

Branch `feature/music-addon-finish`, on top of `7ba3bc1` (session 6's
last commit). Built per the "## H. Tag editor" plan left by session 6 —
followed it as written rather than re-deriving the approach:

- [x] `app/services/tag_editor.py` (new) — `write_text_tags()` via
      mutagen `easy=True` for title/artist/album/tracknumber (one path
      across MP3/FLAC/M4A), and `write_artwork()` with format-specific
      handling (ID3 `APIC` for MP3, FLAC `Picture`, MP4 `MP4Cover` —
      no single easy-mode API for images, as the plan flagged). Both
      write to a temp copy in the same directory and `os.replace()`
      into place only on success, so a bad tag value or crash mid-write
      can't corrupt the source file.
- [x] `app/routers/music.py` — `PATCH /api/music/track/{track_id}/tags`
      (new `TrackTagsUpdate` pydantic model) and
      `POST /api/music/track/{track_id}/artwork` (`UploadFile`, JPEG/PNG
      only, 10MB cap). After a successful tag write, the endpoint mirrors
      whatever mutagen actually wrote back into `MusicTrack.title`/
      `track_number` and the parent `MediaItem.artist_name`/`title`, so
      the library view can't drift from the file on disk.
- [x] `requirements.txt` — added `python-multipart==0.0.12`, required by
      FastAPI's `UploadFile` for the artwork endpoint (wasn't needed by
      anything else in the app before this).
- [x] `ui/src/api.js` — `api.music.updateTrackTags()` /
      `api.music.uploadTrackArtwork()`.
- [x] `ui/src/icons.jsx` — new `Ic.Edit` (pencil) icon; none of the
      existing 49 fit an "edit" affordance.
- [x] `ui/src/pages/music.jsx` — new `TrackTagEditor` modal (title/
      artist/album/track-number fields + cover-art file input with a
      preview thumbnail, daisyUI `modal modal-open` pattern matching
      `AddModal` in `components/ui.jsx`); wired to a new per-row Edit
      button in `MusicDetailPage`'s tracks table (next to the existing
      +Next/+Q buttons), state-gated on `editingTrack`.

Verified (no network, same constraints as every prior session):
`python3 -m py_compile` on `tag_editor.py` and `music.py`; esbuild
per-file checks on `music.jsx`, `icons.jsx`, `api.js`; full esbuild
`--bundle` of `app.jsx` — 0 errors, 928.2kb; `check_ui_static.py` (57
jsx files, **50** icons — the new `Ic.Edit` correctly picked up),
`check_version.py`, and `check_lazy_exports.mjs` all pass.

**Not verified — still needs a network-enabled environment:** a real
`vite build`; `pip install -r requirements.txt` (mutagen's format
classes — `mutagen.id3`, `mutagen.flac`, `mutagen.mp4` — were only
import-checked by reading the code, not actually imported, since
mutagen isn't installed in this sandbox) + backend import check; a
browser end-to-end smoke test — edit a track's title/artist, confirm
the file's tags actually changed on disk (e.g. via a second `mutagen.File`
read or a tool like `kid3`) and the library view updated to match;
upload cover art to an MP3 **and** a FLAC **and** an M4A file (three
different code paths, only one likely to get manually tested first);
confirm a crashed/interrupted write really does leave the original
file untouched (the atomic-swap logic itself wasn't exercised, only
read through). Also still not pushed — `git push -u origin
feature/music-addon-finish` needs to happen from an environment with
GitHub access, same as every prior session. **Committed this session**
as `7b24397` (superseding the "not yet committed" note originally
written here).

**Next-session startup checklist:**
1. `cd` into the repo, confirm still on `feature/music-addon-finish`,
   confirm whether this session's H work got committed (check
   `git log --oneline -3` and `git status --short` — if the tag-editor
   files are still showing as modified/untracked, commit them first
   before anything else).
2. If a network-enabled environment is available, do H's still-open
   verification above first — especially the three-format artwork
   smoke test and confirming the atomic swap actually protects the
   file — before starting new feature work.
3. `todo.md`'s original batch list (session 4's `12dbc5c` plan) is now
   fully done: D (scrobbling), E (crossfade/gapless), F (smart
   playlists), G (radio/mix), H (tag editor) all shipped across
   sessions 4-7. No more planned batch items remain in this file as of
   this session — next session should check with whoever's driving
   for new feature requests rather than assuming there's a queued item.

---

# Comics module — gap analysis + batch plan (added session 8)

Full-repo review of `ui/src/pages/comics.jsx`, `app/routers/comics.py`,
`app/services/comic_arcs.py`, `app/services/comic_pull_sync.py`, and
`app/clients/comicvine.py`. What's solid: library add/search
(ComicVine + MangaDex), story arcs w/ reading-order linking, weekly
pull-list + sync, per-issue tracking, interactive search/grab, quality
profiles — a real Mylar-style backend. What's missing or needs work,
in priority order:

## I. In-app reader — DONE this session, see write-up below

## J. Reading progress tracking — NOT started
`ComicIssue` has no "read" flag or current-page column, so there's
nothing to power a "Continue Reading" row the way music has
`play_count`. Needs a small alembic migration (`is_read` bool +
`last_page_read` int on `comic_issues`), a
`POST /api/comics/issues/{id}/progress` endpoint, and the reader
(`ComicReader` in `ui/src/pages/comics.jsx`, built this session)
calling it on page-change (debounced) and on close. Natural follow-up
to I now that the reader itself exists — was deliberately left out of
this session to keep the reader change reviewable on its own.

## K. Per-issue actions in the UI — NOT started
Backend already has `POST /issues/{id}/search`, `POST /issues/{id}/grab`,
and `PUT /issues/{id}/monitor` (`app/routers/comics.py`) — the issues
table in `ComicDetailPage` only just gained a Read button (this
session); it's still otherwise read-only. Add per-row buttons for
search/grab/monitor-toggle, same pattern as the Read button just added.

## L. Manual release picker — NOT started
`GET /{item_id}/releases` (a ranked list, meant for a picker UI) exists
server-side and is never called from the frontend — only auto-search
and interactive-search are wired up. Low effort: reuse whatever
picker component the music/video modules already have for their
equivalent endpoints, if one exists — check before building a new one.

## M. Manga toggle + manga-only view in the UI — NOT started
`PATCH /{item_id}/tag-manga` and `GET /manga` both exist backend-side
with no button or filter to reach them from `ComicsPage`.

## N. `ComicsPullPanel` dead/broken code — NOT started (cleanup)
Fully written and exported from `comics.jsx` (`export {
ComicsPullPanel, ... }`) but never rendered anywhere, and it calls
`/api/overhaul/comics/pull-list` + `.../sync` — endpoints that don't
exist. The real pull-list lives at `/api/comics/pull*` and works fine
through `ComicsPage`'s actual `pull` tab. Delete `ComicsPullPanel` and
its export rather than fixing it — it's a duplicate of working
functionality, not a partial feature.

## O. `metatag_comic` — two real problems, NOT started
- No `_assert_under_library` path-safety check before writing
  `ComicInfo.xml` to disk — every other file-writing service in this
  repo (`lyrics.py`, `tag_editor.py`, `comic_reader.py` as of this
  session, `media_player.py`) validates the target is under a library
  root first. This one writes straight to `item.file_path`'s parent
  with no check. Fix before this endpoint ships to anyone untrusted.
- Writes `ComicInfo.xml` as a *sidecar* next to the archive, not
  embedded inside it. Real comic readers/taggers (ComicTagger, Kavita,
  ComicRack) expect `ComicInfo.xml` **inside** the `.cbz` zip — as
  written, this metadata is invisible to virtually every downstream
  tool. Fix: for `.cbz`/`.zip`, open with `zipfile` in append mode (or
  rewrite via the same atomic-temp-copy pattern `tag_editor.py` uses)
  and write/replace `ComicInfo.xml` as a zip member. `.cbr`/`.rar`
  can't be modified in place the same way (RAR write support is a
  licensing/tooling mess) — document that as a known limitation rather
  than half-implementing it.

---

# Session 8 — status: I (in-app comic reader) DONE, uncommitted

Branch `feature/music-addon-finish` (comics work continues on the same
branch as the music batch — no separate branch cut for it), on top of
`7b24397`.

- [x] `app/services/comic_reader.py` (new) — `list_pages()` /
      `read_page()` covering every extension `organize.py`'s
      `COMIC_EXTENSIONS` recognizes: `.cbz`/`.zip` via stdlib
      `zipfile`, `.cbt` via stdlib `tarfile`, `.cbr`/`.rar` and `.cb7`
      by shelling out to the same `unrar`/`7z` CLI tools
      `app/services/unpack.py` already uses for torrent extraction (no
      new Python archive dependency for those two), and `.pdf` via
      PyMuPDF rendered to PNG per page at 150 DPI. Nothing is extracted
      to a temp directory — every page comes back as in-memory bytes.
- [x] `app/routers/comics.py` — two route pairs:
      `GET /issues/{issue_id}/pages` + `GET /issues/{issue_id}/page/{index}`
      for a single split-out issue file, and
      `GET /{item_id}/pages` + `GET /{item_id}/page/{index}` for a
      volume stored as one file (one-shots, or issues never split out).
      Checked route ordering against the existing single-segment
      `GET /{item_id}` catch-all — all four new routes are 2-3 segment
      paths so there's no repeat of the route-ordering bug from the
      music session 1 writeup.
- [x] `requirements.txt` — added `PyMuPDF==1.24.10` for PDF page
      rendering.
- [x] `ui/src/pages/comics.jsx` — new `ComicReader` component:
      full-screen overlay, page counter, prev/next buttons + a range
      slider, keyboard arrows (←/→) and Escape-to-close, click-left-half/
      click-right-half of the page image to go back/forward (standard
      comic-reader UX), a fit-width/fit-height toggle. Wired to a new
      "Read" button in `ComicDetailPage`'s action bar (whole-item, only
      shown when `item.file_path` is set) and a new "Read" column in
      the issues table (per-issue, only shown when that issue has a
      `file_path`).

Verified (no network, same constraints as every prior session):
`python3 -m py_compile` on `comic_reader.py` and `comics.py`; esbuild
per-file check on `comics.jsx`; full esbuild `--bundle` of `app.jsx` —
0 errors, 933.8kb; `check_ui_static.py` (57 jsx files, 50 icons —
unchanged, reused the existing `Ic.Book`/`Ic.X` rather than adding new
icons), `check_version.py`, and `check_lazy_exports.mjs` all pass.

**Not verified — still needs a network-enabled environment:** `pip
install -r requirements.txt` (PyMuPDF wasn't importable in this
sandbox, so the PDF path — `import fitz`, `doc.page_count`,
`page.get_pixmap()` — was only read through, never executed); whether
`unrar` and `7z` CLI binaries are actually present in the target
deploy image (`unpack.py` assumes they are for torrent extraction, so
this is an existing assumption, not a new one, but worth confirming
once — if either binary is missing, `.cbr`/`.cb7` reading fails
cleanly with a caught `FileNotFoundError` → `ComicReadError`, it
doesn't crash the request); a real `vite build`; and the actual
browser smoke test — open a `.cbz`, a `.cbr`, a `.cb7`, a `.cbt`, and
a `.pdf` comic and confirm every page renders, in the right order, for
all five formats (only `.cbz`/zipfile and `.cbt`/tarfile use pure
stdlib and are lowest-risk; `.cbr`/`.cb7` depend on CLI tool output
format assumptions — `unrar lb` / `7z l -ba` — that were read from
tool docs/memory, not tested against real tool output; `.pdf` depends
on PyMuPDF being installed and producing valid pixmaps at 150 DPI).
Not pushed, not committed yet either — same as every prior session's
starting state, see checklist below.

**Next-session startup checklist:**
1. `cd` into the repo, confirm still on `feature/music-addon-finish`,
   check `git status --short` — if `comic_reader.py` and the
   `comics.py`/`comics.jsx`/`requirements.txt` changes are still
   showing as modified/untracked, commit them first.
2. If a network-enabled environment is available: `pip install`, then
   smoke-test the reader against one real file per format (`.cbz`,
   `.cbr`, `.cb7`, `.cbt`, `.pdf`) before trusting any of the
   non-`.cbz` code paths. `.cbr`/`.cb7` are the highest-risk — their
   page-listing regex/split logic against `unrar lb` / `7z l -ba`
   output was never run against real tool output.
3. Continue to J (reading progress) next — it's the natural follow-on
   now that the reader exists and was deliberately scoped out of this
   session. K/L/M/N/O (see gap-analysis above) are all smaller and
   independent of each other; any order is fine.

* * *

# Session 9 — no-network code review pass (control-panel work continued)

No network access again this session (same as every prior one — `npm
install` → 403, `pip install` → no matching distribution). Since the
`vite build`/`pip install`/push/PR items from Session 8 are still
blocked for the same reason, this session did another full static
review instead and found + fixed two real bugs beyond what Session 8
caught.

## Bugs found & fixed this session

- [x] **Route-shadowing bug, same root cause as the Session 8
      `/incomplete` fix, found in two more routers** (wrote a small
      script scanning all 48 files in `app/routers/` for a literal
      single-segment route registered *after* a same-prefix
      `/{param}` route — FastAPI/Starlette match by registration
      order and 422 on failed type-conversion rather than falling
      through):
      - `app/routers/games.py`: `GET /{game_id}` (int) was registered
        before `GET /search` and `GET /wanted` — both were 422'ing.
        Moved both above `/{game_id}`, left a comment explaining why.
      - `app/routers/livetv.py`: `GET /channels/{channel_id}` (int)
        was registered before `GET /channels/editor` — the channel
        editor list was 422'ing. Moved it above, same comment style.
      - Re-ran the scanner after the fix: 0 remaining shadowing
        issues across all 48 router files.

- [x] **Version split-brain at runtime** — `app/version.py` docstring
      calls `get_version()` "Single source of version", but it was
      only actually called from 2 places (`backup.py`, `system.py`
      router). Three other places independently hardcoded
      `os.environ.get("APP_VERSION", "1.01beta")` and never read the
      `VERSION` file at all: `app/main.py` (FastAPI app version,
      startup log line, and — importantly — the `/api/health`
      endpoint the new control panel's Health Check button hits),
      plus `app/services/dashboard_widgets.py` and
      `app/services/plugins.py` (core plugin version tags). Net
      effect: `/api/health` reported `1.01beta` while
      `system.py`'s info endpoint reported `2.0.27-dev` (from the
      `VERSION` file) — two different "current version" answers
      depending which endpoint you asked. Fixed by routing all five
      call sites through `get_version()` instead of duplicating the
      fallback logic.

## Found, not fixed — needs a product decision, not a code fix

- [ ] **Which version number is actually current: `1.01beta` or
      `2.0.27-dev`?** `VERSION`/`package.json`/`package-lock.json`
      say `2.0.27-dev` (Session 8 set this deliberately to fix
      `check_version.py`). But `Dockerfile` (`ARG APP_VERSION=`),
      both `docker-compose*.yml` image tag defaults,
      `RELEASE_NOTES_NEXT.md`, `GITHUB_RELEASE_NEXT.md`, and
      `ARCHITECTURE.md` all describe a completed rename to `1.01beta`
      "across all files ... The health endpoint now reports
      `version: 1.01beta`" — which no longer matches reality after
      Session 8's revert. `tests/test_games_scrobble_smoke.py::
      test_version_consistent` still hardcodes
      `assert ver == "1.01beta"` and would fail against the current
      `VERSION` file. **Did not touch any of these** — picking one
      number and rewriting the other six files is a release-naming
      decision, not a bug fix, so it needs a human call before the
      next session touches it.

## Also re-verified clean this session

- [x] `python3 -m py_compile` on every file in `app/` (previously
      only touched files were checked) — 0 errors.
- [x] `esbuild` syntax check on every file in `ui/src/` individually,
      plus a full `--bundle` of `app.jsx` (react/react-dom/
      react-router-dom/hls.js externalized) — 0 errors, 835.9kb.
- [x] `check_version.py`, `check_ui_static.py` (57 jsx files, 50
      icons), `check_lazy_exports.mjs` — all still pass after the
      route-order and version-source edits.

---

# Session 10 — version rename finished (`1.01beta`); parity.py audit done

Picked up the two items Session 9 left open: the version-number
product decision, and the `parity.py` audit that mirrored the
`overhaul.py` cleanup. Decision from whoever's driving: **`1.01beta`
is correct** — finish the rename described in `RELEASE_NOTES_NEXT.md`/
`GITHUB_RELEASE_NEXT.md`, not revert to `2.0.27-dev`.

## Version rename — DONE

Scoped this to *just* the version string, not the much larger
"MediaOS Next" architectural rebuild those release-notes files also
describe (merged docker-compose, VPN killswitch as a required
component, 42 new compose-architecture tests, README/ARCHITECTURE
rewrites) — that's a different, much bigger reference project and
none of it exists in this zip. Doing that rebuild wasn't part of
what was asked and isn't a small follow-on to a version bump.

Updated, per the release notes' own list of touch points:
- `VERSION`: `2.0.27-dev` → `1.01beta`
- `package.json` / `package-lock.json` (both the root and the nested
  `packages[""]` block) → `1.01beta`
- `app/version.py`'s `_VERSION_FALLBACK` → `1.01beta`
- `CHANGELOG.md` — added a `## 1.01beta (2026-08-15)` entry (the
  script has a soft WARN if the current version isn't mentioned)

Already correct, no change needed: `Dockerfile` (`ARG
APP_VERSION=1.01beta`), `docker-compose.standalone.yml`'s image tag
default, and `main.py`/`dashboard_widgets.py`/`plugins.py`/
`system.py`/`backup.py` (already routed through `get_version()` as of
Session 9's fix — nothing hardcoded left to touch there).

**Found and fixed a real blocker along the way:**
`scripts/check_version.py` enforced strict-semver
(`^\d+\.\d+\.\d+` — three dot-separated numeric groups) on the
`VERSION` file. `1.01beta` only has one dot, so it would have failed
that check immediately — meaning the "Version consistency: 1.01beta
everywhere" claim in the release notes was never actually validated
against this repo's own check script. Loosened the regex to
`^\d+\.\d+` (still rejects empty/garbage, now accepts this project's
beta-style tag). `scripts/check_version.py` passes:
`Version check OK (1.01beta)`.

`tests/test_games_scrobble_smoke.py::test_version_consistent` (which
already hardcoded `1.01beta` and was failing before this session)
now passes — confirmed by reading the assertions and running them
manually (pytest itself isn't installed in this sandbox).

Grepped the whole repo for any remaining `2.0.27` reference: only
hits left are inside `CHANGELOG.md`'s existing historical entry (correct —
it's a past changelog record, not a current-version claim) and
`todo.md`'s own session logs (also correct — historical record).
Nothing live references the old version anymore.

## parity.py audit — DONE

Full route-by-route comparison of all 18 endpoints in
`app/routers/parity.py` against every other router (same kind of
pass as the `overhaul.py` cleanup, using grep across all `app/routers/`
files plus `ui/src/api.js` and a repo-wide search for callers):

- **`/storage` — real duplicate, removed.** Byte-identical to
  `system.py`'s `/storage` (both just call
  `app.services.storage.library_storage()`, no differences at all).
  Deleted `parity.py`'s copy. Confirmed via repo-wide grep that
  neither `/api/storage` nor `/api/parity/storage` has any caller
  anywhere (frontend, HTA control panel, or docs) — unlike the
  `overhaul.py` cleanup, this wasn't a "wrong one is live in
  production" situation, just dead duplicate logic in two places.
- **`/cf-bypass/test` — confirmed NOT a duplicate of `system.py`'s
  `/cf-bypass`.** Different methods on `cf_bypass_client`: `system.py`
  calls `.status()` (cached config state), `parity.py` calls
  `.test(url)` (an actual live probe). Left both alone.
- **`/library-watch/status` — confirmed NOT a duplicate of
  `tools.py`'s `/library-watch`.** Different response shapes —
  `parity.py`'s merges `status()` with a `poll_once()` result,
  `tools.py`'s returns only `poll_once()`. Different paths (no
  shadowing possible), and neither has any current caller either.
  Left alone; flagging here in case someone wants to consolidate
  these two later, but it's not an active bug.
- Every remaining route (`delay-profiles`, `workers` +
  `workers/{job_id}`, `strm/movie`, `trakt/trending/movies` +
  `trakt/trending/shows`, `workers/search-all`, `streams/providers`,
  `streams/resolve`, all five `usenet-stream/*` routes) is defined
  **only** in `parity.py` — confirmed via grep across every other
  router file, no collisions anywhere.

## Verification used (same no-network constraints as every prior session)

- `python3 -m py_compile` on every file in `app/` (not just touched
  files) — 0 errors
- `python3 scripts/check_version.py` — OK (`1.01beta`)
- `python3 scripts/check_ui_static.py` — OK (57 jsx files, 50 icons)
- `node scripts/check_lazy_exports.mjs` — OK
- Manually ran `test_version_consistent`'s assertions (pytest not
  installed in this sandbox)
- Repo-wide grep for `2.0.27` and for any caller of the removed
  `/api/parity/storage` path, before and after the edit

## Still open

- Same testing-gap item flagged in the router-cleanup session — still
  unaddressed, still intentionally out of scope for a review-only
  session.
- As always: no real `vite build` / `pip install` / `pytest` was
  possible in this sandbox (network disabled).

---

# Session 11 — library-watch redundancy consolidated

Follow-up to Session 10's parity.py audit, which found `parity.py`'s
`/library-watch/status` and `tools.py`'s `/library-watch` were
different-but-overlapping (different response shapes, no caller for
either) and left both alone as low priority. Picked up per request.

**Kept:** `tools.py`'s `/library-watch` — the more natural home for a
maintenance/watch-status endpoint alongside `jdupes`/`cross-seed`/
`cleanup` in that router. Enriched its response to match the fuller
of the two old shapes (`{**status(), "poll": poll_once()}` — was
previously only `poll_once()`'s result, missing `mode`/`tracked`/
`roots` from `status()`).

**Removed:** `parity.py`'s `/library-watch/status` entirely — its
handler was identical to the enriched `tools.py` version above, so
this is now a straight dedup, not just "two similar-but-different
things." Confirmed via repo-wide grep no caller referenced either
path (frontend, HTA control panel, or docs) before or after the
change.

Verified (no network, same constraints as every session): full
`py_compile` across every file in `app/` — 0 errors;
`scripts/check_version.py` — OK (`1.01beta`); `check_ui_static.py` —
OK (57 jsx files, 50 icons); `check_lazy_exports.mjs` — OK.

## Still open

- Same testing-gap item, still unaddressed.
- Comics J/K/L/M/O from the session-8 gap analysis — still not
  started (see that section above for the full list).
- As always: no real `vite build` / `pip install` / `pytest` was
  possible in this sandbox (network disabled).

---

# Session 12 — Comics J (reading progress tracking) DONE

Backend:
- `app/models.py` — `ComicIssue.is_read` (bool, default False) and
  `.last_page_read` (int, nullable).
- `app/services/schema_migrate.py` — soft-migrate version `2.0.29`
  adds both columns for existing installs.
- `alembic/versions/20260815_0009_comic_reading_progress.py` — mirrors
  the same two columns for CI, `down_revision = "20260815_0008"`,
  idempotent (checks table/column existence before altering), full
  `upgrade()`/`downgrade()` pair — same shape as session 6's music
  genre/mood/play_count revision, used as the template.
- `app/routers/comics.py`:
  - `IssueOut` now returns `is_read`/`last_page_read` so the issues
    table can render them.
  - New `POST /issues/{issue_id}/progress` (`IssueProgressIn`:
    `last_page_read: int | None`, `is_read: bool | None`, updates
    whichever fields are present). `library.view` permission — this
    is a passive read-tracking call triggered by viewing pages, not a
    library-management action, same reasoning as music's
    `/track/{id}/played`. 3-segment path, no route-ordering risk
    against the single-segment `/{item_id}` catch-all.

Frontend:
- `ui/src/api.js` — `api.comics.issueProgress(issueId, body)`.
- `ui/src/pages/comics.jsx`:
  - `ComicReader` now takes `issueId`/`initialPage`/`onProgress`
    props. Resumes at `initialPage` on open. Debounces a progress
    save 800ms after the page stops changing, and saves once more on
    close (covers both "reads for a while then walks away" and
    "flips through fast then closes immediately"). `is_read` is
    computed as `index >= count - 1` at save time — reaching the last
    page marks it read, going back down un-reads it, matching how a
    person would expect a "read" checkmark to behave rather than
    treating it as a one-way flag.
  - **Scoped to per-issue reads only**, per the plan this was written
    against: the whole-item/one-shot reader path (`item_pages`/
    `item_page`, used when a volume has no split-out issues) has
    nothing to attach progress to — there's no `comic_issues` row for
    it. Left that path alone rather than inventing a parallel
    progress store for it.
  - Per-issue Read button now passes `issueId`/`initialPage` through;
    the issues table shows a small ✓ badge next to the button when
    `iss.is_read`. `onProgress` updates the row in local state
    immediately (no need to refetch the whole issues list after
    closing the reader).

Verified (no network, same constraints as every session):
`python3 -m py_compile` on all 4 touched/new backend files, plus a
full `py_compile` across every file in `app/`; esbuild per-file checks
on `comics.jsx` and `api.js`; full esbuild `--bundle` of `app.jsx` —
0 errors, 935.0kb; `check_ui_static.py` (57 jsx files, 50 icons —
unchanged, reused the existing success-badge styling, no new icon),
`check_version.py`, `check_lazy_exports.mjs` all pass. Grepped route
ordering across `comics.py` again — no collisions.

**Not verified — needs a network-enabled environment:** `pip install`
+ real backend import check; the alembic upgrade/downgrade round-trip
(`docs/ALEMBIC_CI.md`) against a real SQLite/Postgres DB; a browser
smoke test — open an issue, flip a few pages, close, reopen and
confirm it resumes where you left off; read to the last page and
confirm the ✓ badge appears without a manual refresh; confirm
`pytest` doesn't choke on the new columns anywhere unexpected.

## Still open

- Same testing-gap item, still unaddressed.
- Comics K/L/M/O — still not started (see the session-8 gap-analysis
  section above). K (per-issue search/grab/monitor buttons) is the
  natural next one — it's the smallest of the four and touches the
  same issues-table UI this session just extended.
- A "Continue Reading" row on the dashboard (the thing J was written
  to power) hasn't been built yet — J only lays the data down. If
  that's wanted, it'd mirror `widget_continue_watching` from the
  music-session dashboard work: join `comic_issues` where
  `0 < progress < finished`, ordered by whatever timestamp tracks
  "last read at" — note `is_read`/`last_page_read` as added this
  session have **no timestamp column**, so "most recently read" isn't
  answerable yet. Would need a small follow-up migration
  (`last_read_at`) before a Continue Reading row could sort
  correctly — flagging now so it's not a surprise later.
- As always: no real `vite build` / `pip install` / `pytest` was
  possible in this sandbox (network disabled).
