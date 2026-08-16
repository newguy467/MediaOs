# Contributing to MediaOS

## Local checks (no Docker required)

```bash
pip install -r requirements.txt -r requirements-dev.txt
export AUTH_REQUIRE=false
export DATABASE_URL=sqlite:////tmp/mediaos-dev.db

# Full local gate: version + UI static + lazy exports + pytest
npm run ci:local

# Tests only
python3 -m pytest -q

# Coverage
npm run test:cov
```

Pytest uses **SQLite by default**. Production uses Postgres via Docker Compose; see `docs/CI.md` and `docs/POSTGRES_MIGRATE.md`.

## Optional browser E2E

```bash
npm run test:e2e:install
# start the UI (compose or vite dev server)
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8787 npm run test:e2e
```

Smokes **skip** if `PLAYWRIGHT_BASE_URL` is unset. CI’s optional `e2e` job runs only when the repo variable is set.

## Route ordering

Literal API paths (`/bulk`, `/search-all`, …) must be registered **before** `/{id}` path-params on the same method. `tests/test_route_order.py` guards this.

## Version

Single source: `VERSION` file (see `scripts/check_version.py`).


## Staging E2E
Set PLAYWRIGHT_BASE_URL to a running UI. For Actions, set repo variable PLAYWRIGHT_BASE_URL so the optional e2e job runs.
