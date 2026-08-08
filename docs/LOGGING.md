# mediaos logging

## Files
Default directory (first writable):
1. `$MEDIAOS_LOG_DIR`
2. `/config/logs`
3. `/var/log/mediaos`
4. `./logs`
5. `/tmp/mediaos-logs`

| File | Contents |
|------|----------|
| `mediaos.log` | App log (all levels), rotating 10MB × 10 |
| `mediaos-error.log` | WARNING+ only, 5MB × 5 |
| `mediaos-access.log` | HTTP access (method path status ms) |

Format: `YYYY-MM-DD HH:MM:SS | LEVEL | request_id | logger | message`

## Env
- `LOG_LEVEL` / `MEDIAOS_LOG_LEVEL` — DEBUG, INFO, WARNING, ERROR
- `MEDIAOS_LOG_DIR` — override directory

## API / UI
- UI: **Logs** (advanced sidebar)
- `GET /api/logs` — list files
- `GET /api/logs/tail?file=mediaos.log&lines=200&level=ERROR`
- `GET /api/logs/search?q=grab&file=mediaos.log`
- `POST /api/logs/level?level=DEBUG` — runtime level

## Request correlation
Every response includes `X-Request-Id`. Pass the same header on retries to keep one id across a client session.
