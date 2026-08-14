# Converter (Tdarr-class) — fully integrated

MediaOS includes a **native Tdarr-class transcoding pipeline**. External Tdarr is optional.

## What is built in

| Capability | Implementation |
|------------|----------------|
| Presets (H.264 / HEVC / AV1 / remux / HW) | `ConvertPreset` + UI |
| Job queue + parallel workers | `ConvertJob` + scheduler (45s tick) |
| Watch folders | `ConvertWatchFolder` + interval scan |
| Library auto-seed | `/movies`, `/tv`, … registered on startup |
| Health check after encode | duration + size probe (`converter_health_check`) |
| Retries | `converter_max_attempts` re-queue on fail/health fail |
| Output modes | `new_file` / `replace` / `rename_old` |
| HW encode | CUDA / QSV / VAAPI / AMF via compose overlays |
| Savings report | `/api/converter/savings` |
| Pipeline summary | `/api/converter/pipeline` |

## API highlights

- `GET /api/converter/pipeline` — full pipeline status
- `POST /api/converter/seed-libraries` — re-seed library roots as watch folders
- `GET /api/converter/tdarr/status` — optional external Tdarr reachability
- `POST /api/converter/scan` — scan paths into queue
- `POST /api/converter/worker/tick` — process batch

## Optional classic Tdarr UI

```bash
docker compose -f docker-compose.yml -f docker-compose.tdarr.example.yml --profile tdarr up -d
```

Set `TDARR_ENABLED=true` and `TDARR_URL=http://tdarr:8265`. Library volume paths match MediaOS/Jellyfin.

## GPU

Use the existing overlays:

```bash
docker compose -f docker-compose.yml -f docker-compose.nvidia.yml up -d
# or intel / amd
```
