# Alembic down-migrations in CI

MediaOS defaults to **soft-migrate** (`app/services/schema_migrate.py`) on startup for additive column upgrades. Alembic is the **reviewed / reversible** path.

## What “down-migrate usage in CI” means

In continuous integration you prove that migrations are not one-way traps:

1. **upgrade head** on an empty DB (or copy of prod schema)
2. **downgrade -1** (or `downgrade base`) and confirm the schema rolls back cleanly
3. **upgrade head** again (idempotent re-apply)

Example job steps:

```bash
export DATABASE_URL=sqlite:///./ci-migrate.db
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Postgres variant: use a disposable service container and the same three commands.

## When to use soft-migrate vs Alembic

| Path | Use when |
|------|----------|
| Soft-migrate | Dev / simple additive columns / always-up installs |
| Alembic | You need **downgrade**, multi-env review, or audited schema history |

Revision `20260810_0002` is the first real upgrade/downgrade pair (provider IDs, series rules). New model changes should add a new revision with both `upgrade()` and `downgrade()`.
