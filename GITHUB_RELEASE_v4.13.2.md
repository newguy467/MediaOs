# MediaOs v4.13.2 (2026-08-08)

A critical patch release. **v4.13.1 does not start** due to a syntax error in the
setup router — this release fixes that plus a second silent-breakage bug in Live
TV, closes two auth timing/brute-force gaps, and finally ships the two CI
workflows (`ghcr.yml`, `ui.yml`) that have been flagged as missing since the
4.12 audit. No schema or config changes — if you're running 4.13.1 in a
container, it likely never came up; pull this tag and redeploy.

### Fixed — critical
- **App would not start.** `app/routers/setup.py` had a `return` statement outside its
  function (bad dedent); since `setup` is imported unconditionally by `app/main.py`,
  this broke the entire application, not just the first-run wizard.
- **Live TV entirely broken.** `app/services/livetv.py` had a stray `import re` placed
  before `from __future__ import annotations`, which Python requires to be the first
  statement in a file. Every Live TV feature (M3U sync, EPG, XMLTV export, channel
  health) imports this module and failed at import time.

### Fixed — security
- `arr_compat.require_arr_key` now compares the `X-Api-Key` with
  `secrets.compare_digest` instead of `!=`, matching the constant-time comparison used
  everywhere else in the auth layer.
- `/api/auth/login` and `/api/adult/unlock` are now rate-limited (escalating backoff,
  reusing the existing indexer backoff registry) to blunt credential/passcode
  brute-forcing.

### Fixed — other
- `app/main.py`'s `APP_VERSION` fallback was hardcoded to a stale `4.11.0`; now tracks
  the release.
- `organize.py`: cross-seed notification for single-episode TV organizes was nested
  inside the `after_organize_episode` hook's try/except, so it silently never ran if
  that hook raised. Split into its own independent try block, matching the movie path.
- `package-lock.json`'s embedded `version` field was stale at `4.11.0` (out of sync
  with `package.json`); now kept in lockstep.
- Regenerated `FILELIST.txt` against the actual tree (previously stale, per
  `docs/GAP_AUDIT.md`).

### Added
- `.github/workflows/ghcr.yml` — multi-arch (amd64/arm64) image build + push to
  `ghcr.io/<repo>` on pushes to `main`/`master` and on `v*` tags.
- `.github/workflows/ui.yml` — standalone Vite/React UI build check on PRs and pushes
  touching `ui/**`, uploads the build as an artifact.
