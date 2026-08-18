# Security — MediaOS 2.0.11-dev

## Threat model

MediaOS is designed primarily for **homelab / private LAN** use:

| Trust zone | Assumption |
|------------|------------|
| Host OS + Docker network | Trusted |
| Browser on the same LAN | Semi-trusted (auth required by default) |
| Internet-exposed reverse proxy | **Not default** — enable only with TLS, strong auth, and rate limiting |
| Indexers / download clients | Semi-trusted; API keys stored in config/DB |
| Metadata providers (TMDb, TVDb, …) | Trusted HTTPS endpoints |

Do **not** expose port 8787 directly to the public internet without:
- TLS termination
- `AUTH_REQUIRE=true` and strong admin credentials
- Network-level allowlists or VPN (e.g. Gluetun profile)

### Default port bindings

`docker-compose.yml` splits its port defaults by exposure risk:

| Service | Default bind | Why |
|---|---|---|
| MediaOS (8787), Jellyfin (8096) | `0.0.0.0` (LAN) | The UIs you're meant to open from other devices; `AUTH_REQUIRE=true` by default |
| qBittorrent WebUI (8080) | `127.0.0.1` (loopback) | Weak default auth, no need for LAN reach out of the box |
| Tdarr (8265), EPG sidecar (3099), FlareSolverr (8191) | `127.0.0.1` (loopback) | Internal tooling, not browsed to directly |

To open a loopback-only service to your LAN, set its `*_HOST_BIND` variable in `.env` to `0.0.0.0` (e.g. `QBIT_HOST_BIND=0.0.0.0`).

### System Monitor page — optional host-level access

The System Monitor page's CPU/memory/temperature and SMART sections work out of the box using only the MediaOS container's own view (no extra access), but that means CPU/memory reflect the container's cgroup, not the host, and there's no temperature or disk-health data. Both can be upgraded, and both are off by default because each is a real, distinct privilege tradeoff — see the commented blocks under the `mediaos` service in `docker-compose.yml`:

| Feature | What it needs | What it exposes |
|---|---|---|
| Host-level CPU/memory/temperature | Read-only bind mounts of host `/proc` and `/sys` | The host's full process list (other containers' PIDs and command lines) becomes readable from inside MediaOS |
| SMART (disk health) | `devices:` entries for the target disks + `cap_add: [SYS_RAWIO]` + `SMART_DEVICES` in `.env` | Direct read access to the raw block device from inside the container |

Enable either independently of the other.

## Hardening in 2.0.11-dev

1. **npm supply chain** — lockfile only against `https://registry.npmjs.org`; `.npmrc` pin; CI rejects IP/HTTP resolved URLs.
2. **Auth on by default** — `AUTH_REQUIRE=true`.
3. **DB-backed sessions** — access tokens issued via `AuthSession` (4h access / 7d refresh); in-memory is fallback only.
4. **Non-root runtime** — user `mediaos` (uid 1000); entrypoint fixes volume ownership when started as root, then drops privileges with `gosu`.
5. **Postgres password required** — compose fails if `POSTGRES_PASSWORD` is unset. Use `scripts/generate_secrets.sh`.
6. **Path guards** — player/library paths must resolve under configured library roots.
7. **No `shell=True`** — subprocess calls use argument lists (CI/tests assert this).

## First-run secrets

```bash
cp .env.example .env
bash scripts/generate_secrets.sh .env
# sets POSTGRES_PASSWORD + AUTH_API_KEY, forces AUTH_REQUIRE=true
docker compose -f docker-compose.standalone.yml up -d --build
```

Bootstrap admin (if no seed user): `{data_path}/bootstrap/admin-credentials.txt` (mode 0600).

## Reporting

Prefer a private GitHub security advisory over a public issue.
