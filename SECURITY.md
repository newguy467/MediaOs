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
