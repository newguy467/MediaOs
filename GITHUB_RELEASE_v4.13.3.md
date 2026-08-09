# MediaOs v4.13.3 (2026-08-09)

Docker Compose cleanup. Ten compose files shipped in the zip, three of them
dead weight — this trims to seven, with every remaining file directly
referenced by the app's own setup wizard or real docs (verified by grep
before deleting anything, not guessed).

### Removed
- `docker-compose.gpu.yml` — duplicated `docker-compose.nvidia/intel/amd.yml`
  via a messier `extends`-based pattern; the app's own setup wizard and
  `/api/converter` endpoints already point users at the three vendor-specific
  files directly, and nothing in the repo referenced this one.
- `docker-compose.neutarr.example.yml` — was already self-labeled
  "DEPRECATED — not required" with no services defined, and referenced
  nowhere.
- `docker-compose.epg.example.yml` — duplicated the `iptv-org-epg` service
  that already ships inside `docker-compose.yml` behind the `full`/`epg`
  profile. `docs/LIVETV.md` was the only reference; updated it to
  `docker compose -f docker-compose.yml --profile epg up -d` instead of
  pointing at a separate file.

### Fixed
- `app/main.py` had two more hardcoded stale `APP_VERSION` fallbacks
  (`4.11.0`) beyond the one fixed in 4.13.2 — startup log line and the
  `/api/health` response. All three now match the release.

### Kept (all directly referenced by the app itself)
`docker-compose.yml`, `docker-compose.standalone.yml`,
`docker-compose.vpn.example.yml`, `docker-compose.nvidia.yml`,
`docker-compose.intel.yml`, `docker-compose.amd.yml`,
`docker-compose.integrations.example.yml`.
