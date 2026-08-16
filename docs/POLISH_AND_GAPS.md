# MediaOS — TODO after Session 31 (13 gap slices)

## Done this pass (slices, not full product rewrites)

### Parked list 1–5 (no 1.01beta)
1. Episode-aware TV tracking — `sync_series_tracking` + `POST /api/library/tv/{id}/sync-tracking`
2. Debrid — Real-Debrid already on grab path (`rd_client.best_stream_link`)
3. Games install jobs — `GameInstallJob` model, log on install, `GET /api/games/install-jobs`
4. EPG now line + conflict badge hook + programme menu (prior)
5. CI — e2e-syntax + compose-validate; live Playwright still URL-gated

### Major gaps 1–8
1. Duplicates — `GET /api/library/duplicates`, merge endpoint
2. Status transitions — `POST /api/library/items/{id}/status` + `STATUS_FLOW`
3. Needs attention — `GET /api/library/attention` + dashboard strip
4. Permissions — existing users/roles; no redesign this pass
5. Backup — existing `/api/system/backup*`; not redesigned
6. Metadata refresh — `POST /api/library/metadata/refresh/{id}`
7. Path maps — `PathMap` model + CRUD/dry-run APIs
8. Interactive search quality — **Why** rejections details on results

## Still open (next set)

1. Duplicate merge UI in Settings/Library tools
2. Auto-sync TV tracking when episode file lands (hook organize)
3. TorBox/AllDebrid clients parity with RD
4. Install jobs panel in Games UI
5. EPG conflict detection vs DVR schedule (server-side)
6. Scheduled Playwright nightly workflow
7. Multi-user kids profile UX polish
8. Backup wizard UI (schedule + include paths)
9. Bulk metadata refresh job + progress
10. Path-map settings page
11. Quality “explain score” drawer beyond reject why
12. **`1.01beta`** when you want the tag

## Verify

```bash
export AUTH_REQUIRE=false DATABASE_URL=sqlite:////tmp/mediaos-test.db
python3 -m pytest -q
```
