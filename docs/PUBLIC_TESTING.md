# Public testing guide

MediaOs is ready for early public testing via Docker.

## Recommended path

```bash
docker pull ghcr.io/newguy467/mediaos:latest
# or build this release tree
docker compose -f docker-compose.standalone.yml up -d --build
```

UI: http://localhost:8787

## What to try

- Setup wizard completion
- Discover → add title
- Library status badges
- Settings groups
- (Optional) qBittorrent grab + organize

## What not to expect yet

- Full Jackett parity inside Cardigann
- Built-in VPN (use Gluetun sidecar)
- Multi-tenant hosting for multiple customers

## Feedback

GitHub Issues on the mediaos repository. Redact secrets.
