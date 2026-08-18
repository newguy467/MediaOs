# MediaOS — TODO after Session 32 (next-set 1–11)

## Landed this pass

1. Duplicate **merge UI** — Library tools → duplicates
2. Auto-sync TV tracking on episode organize
3. Multi-debrid grab via `resolve_stream` (RD + TorBox/AllDebrid/…)
4. Games **install jobs** panel (log tail)
5. EPG **conflict** flags vs DVR schedule
6. **E2E nightly** workflow (`.github/workflows/e2e-nightly.yml`)
7. Kids / multi-user **tips** on sessions + users settings
8. Backup **wizard** (include toggles + cron note)
9. **Bulk** metadata refresh UI + progress
10. Path-map **settings** under Library tools → paths
11. Quality **Explain** score drawer on interactive results

## "Still open / deeper" — reconciled (2026-08-17), all landed

This section previously listed 7 items as open. A doc-reconciliation pass
this session checked each one directly against the code (not against
prose elsewhere) — all landed in later sessions; this doc had just never
been updated to say so:

1. ~~Full metadata job queue (background worker + SSE progress)~~ — **done**,
   `app/services/metadata_jobs.py` + `POST /api/library/metadata/refresh`
   (bulk enqueue), SSE channel `metadata_job`.
2. ~~TorBox-specific client module tests~~ — **done**,
   `tests/test_torbox_client.py`.
3. ~~Server-side kids profile presets (not just docs)~~ — **done**,
   `app/routers/users.py` — real `PROFILE_PRESETS` catalog,
   `GET /api/users/presets` + `POST /api/users/presets/{id}/apply`, not
   just a UI tip.
4. ~~Backup `include_db` flags honored in `create_backup` service~~ —
   **done**, `app/services/backup.py`'s `create_backup()` takes and
   honors both `include_db`/`include_config`.
5. **Score breakdown always populated from quality engine** — was
   **NOT actually true** when checked. `score_release()` in
   `app/services/quality/profiles.py` had 4 return paths; only 2 set
   `breakdown`. The "rejected by custom format" and "missing required
   format" paths returned an empty `{}`, so the Quality Explain drawer
   (item 11 above) silently showed nothing for those two rejection
   reasons. **Fixed this session** — both paths now populate a real
   breakdown (`rejected` reason + matched/required format name).
   Verified all 4 `ScoreResult` construction sites set `breakdown`,
   `py_compile` clean.
6. ~~Path-map apply inside organize (not only dry-run)~~ — **done**,
   `organize.py` imports and calls `apply_path_map` from
   `library_gaps.py`, not just the dry-run preview endpoint.
7. ~~**`1.01beta` cut** (this tag)~~ — **done**, `VERSION` /
   `package.json` / `RELEASE_NOTES_1.01beta.md` all agree.

**Lesson for next time:** don't trust a "done" claim in `CHANGELOG.md`
prose without spot-checking the actual code — 6 of 7 items here really
were done, but the changelog bullet for item 5 ("Score breakdown") was
technically true (breakdown exists) while omitting that it wasn't
populated on every path. Same failure mode flagged in an earlier
session's own note: "don't re-trust old planning-note claims about
'already implemented' without reading the code first."

## Separately fixed this session (not from this list)

- **`.env.example` was missing from the repo entirely** — breaks the
  documented `cp .env.example .env` quickstart, `scripts/
  generate_secrets.sh`, and `tests/test_compose_architecture.py`
  (which asserts the file exists and is complete). Rebuilt covering
  all 74 vars referenced in `docker-compose.yml` plus GPU-overlay vars
  (`RENDER_GID`/`VIDEO_GID`/`LIBVA_DRIVER_NAME`) and the app-level keys
  from `docs/REQUIRED_KEYS.md`. Caught and fixed a bug introduced
  while writing it: an inline `KEY=  # sensitive` comment convention
  broke `generate_secrets.sh`'s naive `sed`-based "is this still
  blank" check (the comment text was read as the value, so a real
  password never got generated) — moved the annotation to a comment
  line above each sensitive var instead, verified the generate-secrets
  flow actually produces real hex passwords now.
- **GPU compose layout** (`docker-compose.nvidia/amd/intel.yml`) —
  investigated whether to merge into the main compose file via
  `profiles:`. Confirmed this is intentional design, not a gap: the
  in-app GPU setup wizard (`app/routers/setup.py`,
  `app/services/converter.py`) directly instructs users to run
  `docker compose -f docker-compose.yml -f docker-compose.nvidia.yml
  up -d` — the override-file pattern is load-bearing UI behavior.
  Compose `profiles:` also can't do what's needed here (swap partial
  config on the *same* service) without duplicating the ~90-line
  `mediaos` service three times. Left split, no change made.

## Verify

```bash
export AUTH_REQUIRE=false DATABASE_URL=sqlite:////tmp/mediaos-test.db
python3 -m pytest -q
```
