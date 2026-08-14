# Continuous integration

Workflows live under `.github/workflows/`.

| Workflow | Purpose |
|----------|---------|
| `ci.yml` | Version, UI static/lazy/build, pytest, Alembic round-trip |
| `security.yml` | npm audit, pip-audit, lockfile registry hygiene |

## Local parity

```bash
python3 scripts/check_version.py
python3 scripts/check_ui_static.py
npm run check:lazy
npm run build
pytest -q
python3 scripts/generate_changelog.py --note "test" --version "$(cat VERSION)"
```

## Branch protection (recommended)

Require:

- `CI success` (aggregate job in `ci.yml`)
- Optionally `security / lockfile-hygiene`

## Changelog in CI

`generate_changelog.py` is smoke-tested (dry-run). Release writers use:

```bash
npm run changelog:bump
```
