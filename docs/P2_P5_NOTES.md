# Session 34 — P2–P5 polish

## P2 Music (Lidarr depth)
- `GET /api/music/hunt-incomplete` — lowest completeness first
- `GET /api/music/album/{id}/missing-tracks`
- `POST /api/music/album/{id}/search-missing`

## P3 Books / Audiobooks
- `GET /api/books/wanted-hierarchy` — author → wanted books
- `GET /api/audiobooks/wanted-hierarchy`

## P4 Notifications + Tracking
- `app/services/notifications.py` — Discord, Telegram, Apprise, **ntfy**, **Gotify** + history
- `GET/POST /api/system/notifications/*` (channels, history, test, send)
- Tracking statuses: planned / in_progress / completed / on_hold / dropped
- `GET /api/tracking/statuses`, `POST /api/tracking/{id}/status`
- hooks.notify routes through notification center

## P5 Live TV + Games
- Live TV bulk enable/reorder (`POST /api/livetv/channels/bulk`, `/reorder`) — confirmed present
- `POST /api/games/{id}/playtime` — increment playtime, completion → tracking

## Seek & find
See SEEK_AND_FIND.txt at zip root.

## Verify
```bash
export AUTH_REQUIRE=false DATABASE_URL=sqlite:////tmp/mediaos-test.db
python3 -m pytest -q tests/test_p2_p5_smoke.py
```
