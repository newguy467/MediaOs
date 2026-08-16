# Session 34 — P0 + P1 polish

## P0 — Protect absorbed *arr cores
- `app/services/arr_validation.py` — connection, library shape, side-by-side dry-run
- `POST /api/migrate/validate` — full preflight (no writes)
- `POST /api/migrate/validate/connection`
- `POST /api/migrate/validate/side-by-side`
- `tests/test_arr_pipeline_smoke.py` — 8 regression smokes (validation, quality, stream rank, subtitles, path map, backup flags)

## P1 — Subtitles depth + stream-as-primary
- Bazarr-style language profiles: default profile get/set
- `GET /api/tools/subtitle-profiles`, `PUT /api/tools/subtitle-profiles/default`
- Movie + TV episode subtitle fetch uses active profile (languages + HI)
- Interactive search ranks streamable releases first when `prefer_stream_on_search=true`

## Verify
```bash
export AUTH_REQUIRE=false DATABASE_URL=sqlite:////tmp/mediaos-test.db
python3 -m pytest -q tests/test_arr_pipeline_smoke.py
```
