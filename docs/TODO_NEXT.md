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

## Still open / deeper

1. Full metadata job queue (background worker + SSE progress)
2. TorBox-specific client module tests
3. Server-side kids profile presets (not just docs)
4. Backup include_db flags honored in `create_backup` service
5. Score breakdown always populated from quality engine
6. Path-map apply inside organize (not only dry-run)
7. **`1.01beta` cut** (this tag)

## Verify

```bash
export AUTH_REQUIRE=false DATABASE_URL=sqlite:////tmp/mediaos-test.db
python3 -m pytest -q
```
