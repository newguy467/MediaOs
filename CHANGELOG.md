# Changelog

## 4.13.5 — 2026-08-09
CI import/collection fixes so unit tests pass on push.

### Fixed
- **comics router**: define `ArcCreate`, `ArcIssueIn`, `PullCreate`, `PullFlags` and import `comic_arcs as arcsvc`
- **indexers router**: define `CredentialsIn` before first use
- **tests**: `test_trash_and_migrate` uses current `import_trash_payload` API


## 4.13.4 — 2026-08-09
Patch on top of 4.13.3 (boot-safe + compose cleanup).

### Fixed
- **Live TV model**: `fail_count`, `last_check_at`, `epg_tvg_id` on `LiveTvChannel` (health/status no longer hits missing attrs)
- **Startup ALTERs** for `livetv_channels.sort_order`, `epg_tvg_id`, `fail_count`, `last_check_at`
- **Comic pull auto-grab**: prefers `media_item_id` before name matching
- **Live TV editor UI**: enable toggles per channel, enable/disable filtered bulk, loads editor list (includes disabled)
- **Settings**: Plex / Tautulli fields in integrations group (now-playing)

## 4.13.3 — 2026-08-09
Docker Compose cleanup + remaining APP_VERSION stamps.

## 4.13.2 — 2026-08-08
Critical: setup.py start fix, livetv import order, auth hardening, CI workflows.

## 4.13.1 / 4.13.0
Safe AI, Homelab, gap features, release automation.
