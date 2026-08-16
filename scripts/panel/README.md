# MediaOS — Control Panel scripts

End-user operational scripts behind `MediaOS-Control-Panel.hta` (in the repo
root). These are for running MediaOS day-to-day — start it, stop it, back it
up, check on it. For building/testing the app from source, see
`scripts/windows/` instead (the developer dashboard).

Every script here takes one optional argument: the compose file to use
(default `docker-compose.yml`). The control panel passes this automatically
based on the dropdown at the top of the window; running a script directly
just uses the default.

| Script | Does |
|---|---|
| `start.bat` | `docker compose up -d`. Creates `.env` from `.env.example` and generates `POSTGRES_PASSWORD` on first run if missing. |
| `stop.bat` | `docker compose down`. Data volumes are untouched. |
| `restart.bat` | `docker compose restart`. |
| `open-ui.bat` | Opens the MediaOS UI in your browser (reads `MEDIAOS_HOST_PORT` from `.env`, defaults to 8787). |
| `health-check.bat` | Shows `docker compose ps` plus a live probe of `/api/health`. |
| `view-logs.bat` | Tails the `mediaos` container's logs (Ctrl+C to stop). |
| `backup.bat` | `pg_dump`s the database and zips it with `.env` into `backups\<timestamp>.zip`. |
| `update.bat` | `git pull` (if git is on PATH) then `docker compose up -d --build`. |
| `edit-env.bat` | Opens `.env` in Notepad (creates it from the template first if missing). |
| `open-data-folder.bat` | Opens the `data\` folder (media libraries, downloads) in Explorer. |
| `_common.bat` | Shared header (not run directly) — sets `REPO_ROOT` and the purple console theme. |

## Using these without the control panel

Double-click any script directly from `scripts\panel\`, or run it from a
terminal — they cd into the repo root themselves, so it doesn't matter where
you launch them from. To target a non-default compose file, pass it as an
argument, e.g.:

```
scripts\panel\start.bat docker-compose.standalone.yml
```

## Relationship to `scripts\windows\`

`scripts\windows\` is for people building MediaOS from source (installing
deps, running `vite build`, pytest, pushing branches). `scripts\panel\` is
for people running the already-built stack day-to-day. If you're not
touching the source code, you probably want the control panel, not the
build dashboard.
