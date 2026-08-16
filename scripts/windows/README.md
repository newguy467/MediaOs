# MediaOS — Windows build & test scripts

Windows equivalents of the checks this project already runs in CI
(`.github/workflows/ci.yml`) and the sandbox verification steps used
during development, so you can run them locally on Windows without
needing WSL or a Linux box.

## Quickest way to use these: the dashboard

Double-click **`dashboard.bat`**. It opens a small red/black window
with one button per script below — click a step, it runs in its own
console window so you can read the full output, and re-run it as many
times as you like.

If your machine blocks `.hta` files (some corporate policies do —
`dashboard.bat` will just silently fail to open a window in that case),
use **`menu.bat`** instead: same steps, same red/black theme, plain
console menu, no HTA involved.

You can also just double-click any numbered script directly — the
dashboard and menu are conveniences, not requirements.

## What each script does

| Script | Does |
|---|---|
| `01_install_frontend.bat` | `npm install` (run from repo root — `package.json` lives there, not in `ui\`, even though vite's source root is `ui`) |
| `02_build_frontend.bat` | `npm run build` (vite) → refreshes `app\static\assets\` |
| `03_install_backend.bat` | Creates `.venv` if missing, installs `requirements.txt` + `requirements-dev.txt` |
| `04_check_backend_imports.bat` | `python -c "import app.main"` — catches missing packages / import errors that a syntax-only check can't |
| `05_run_verify_scripts.bat` | Runs `check_version.py`, `check_ui_static.py`, `check_lazy_exports.mjs` — same checks `npm run verify` runs, but called with `python`/`node` directly since Windows usually only has `python`, not `python3`, on PATH |
| `06_run_tests.bat` | `pytest tests\ -q --tb=short` against an isolated local sqlite file |
| `07_run_dev_server.bat` | `uvicorn app.main:app --reload` against local sqlite — no Docker/Postgres needed, good for quick smoke-testing pages in a browser |
| `08_docker_up.bat` | Full stack via `docker compose up --build` — lets you pick which compose file (standard / standalone / nvidia / amd / intel); auto-generates `.env` + a `POSTGRES_PASSWORD` on first run if missing |
| `09_alembic_ci_check.bat` | Migration reversibility round-trip (`upgrade head` → `downgrade -1` → `upgrade head`) on a throwaway sqlite file — mirrors `docs/ALEMBIC_CI.md` |
| `10_git_push_branch.bat` | Pushes the current branch to `origin` (asks for confirmation first) |
| `99_full_build_all.bat` | Runs `01` → `06` in order, stops at the first failure |
| `dashboard.hta` / `dashboard.bat` | The GUI dashboard described above |
| `menu.bat` | Console-only fallback menu |
| `_common.bat` | Shared header (not run directly) — sets the repo root path and the red/black console theme |

## Typical first-time flow

1. `dashboard.bat` → **01** → **02** (frontend built)
2. `dashboard.bat` → **03** → **04** (backend deps installed and importable)
3. **05** and **06** to verify everything (or just click **99** to do 01–06 in one go)
4. **07** to smoke-test in a browser at `http://127.0.0.1:8000`, or **08** for the full Docker stack

## Notes / known limits

- These scripts are Windows-only (`.bat`/`.hta`) and were written and
  syntax-checked without access to a real Windows machine — the logic
  and known `cmd.exe` gotchas (e.g. `if cond A & B` running `B`
  unconditionally, which `menu.bat` works around with parentheses) were
  applied carefully, but if something doesn't run the way it should on
  your machine, let me know what broke and I'll fix it.
- `08_docker_up.bat`'s auto-generated password uses PowerShell for the
  in-place `.env` edit (`Set-Content`) — this needs PowerShell on PATH,
  which is standard on any Windows 10/11 install.
- None of these replace an actual browser smoke test (playback, EQ,
  crossfade/gapless timing, offline caching, lyrics sync, queue
  drag-reorder) — `07` or `08` gets the server running so you can do
  that by hand in a browser; there's no automated script for it here.

## Adding a new script later

Copy the shape of any existing numbered script: `call "%~dp0_common.bat"`
at the top, a banner `echo` block, the actual command, `if errorlevel 1
goto :fail`, and matching `:fail`/`:end` labels. Then add a button for
it in `dashboard.hta` (copy one `<button class="btn">` block) and a line
in `menu.bat` (copy one `if /i "%CHOICE%"==...` line, remembering the
parentheses).
