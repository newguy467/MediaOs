"""Fix game_releases column drift vs the GameRelease model.

20260810_0005's create_table("game_releases", ...) was written against a
different (earlier?) shape of the GameRelease model than what actually
shipped: it's missing `edition`, `platform_id`, `quality_score`,
`file_path`, `installed` (all read/written by app/routers/games.py, e.g.
`r.edition` / `r.installed` in GET /games/{id} and `GameRelease(...,
platform_id=...)` on create) and carries columns the model never declares
(`indexer`, `seeders`, `download_url`, `info_url`, `protocol`, `quality`,
`score`). Because alembic runs before `Base.metadata.create_all()` in
app/main.py's startup sequence, create_all sees the table already exists
(from this migration) and never patches it — every fresh install ends up
with a game_releases table that doesn't match the ORM model, so any query
against it (e.g. `db.query(GameRelease)...` in GET /games/{id}) raises a
"no such column" error at the database layer.

This migration is additive only: it adds the five missing columns. It
intentionally leaves the extra unused columns from 0005 in place — no code
reads them, so they're harmless, and dropping columns from a table that may
already have rows on installs that hit this bug is riskier than leaving
them.

Revision ID: 20260811_0007
Revises: 20260811_0006
Create Date: 2026-08-11
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260811_0007"
down_revision: Union[str, None] = "20260811_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_RELEASE_COLUMNS = [
    sa.Column("edition", sa.String(), nullable=True),
    sa.Column("platform_id", sa.Integer(), sa.ForeignKey("platforms.id"), nullable=True),
    sa.Column("quality_score", sa.Integer(), nullable=True),
    sa.Column("file_path", sa.String(), nullable=True),
    sa.Column("installed", sa.Boolean(), nullable=True, server_default=sa.text("false")),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "game_releases" not in set(insp.get_table_names()):
        return
    existing = {c["name"] for c in insp.get_columns("game_releases")}
    dialect = bind.dialect.name

    if dialect == "sqlite":
        # SQLite batch_alter_table recreates the table and trips on unnamed FK
        # constraints (ValueError: Constraint must have a name). Use raw ALTER
        # TABLE ADD COLUMN instead — SQLite supports it natively and it avoids
        # the constraint-naming issue entirely.
        for col in _NEW_RELEASE_COLUMNS:
            if col.name not in existing:
                col_type = col.type.compile(dialect=bind.dialect)
                col_def = f'"{col.name}" {col_type}'
                if col.nullable is not None and not col.nullable:
                    col_def += " NOT NULL"
                if col.server_default is not None:
                    default_val = col.server_default.arg
                    if hasattr(default_val, "text"):
                        default_val = default_val.text
                    col_def += f" DEFAULT {default_val}"
                bind.exec_driver_sql(
                    f'ALTER TABLE "game_releases" ADD COLUMN {col_def}'
                )
        return

    # PostgreSQL and other dialects: use standard batch_alter_table
    with op.batch_alter_table("game_releases") as batch:
        for col in _NEW_RELEASE_COLUMNS:
            if col.name not in existing:
                batch.add_column(col)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "game_releases" not in set(insp.get_table_names()):
        return
    existing = {c["name"] for c in insp.get_columns("game_releases")}
    names = [c.name for c in _NEW_RELEASE_COLUMNS if c.name in existing]
    if not names:
        return
    dialect = bind.dialect.name
    if dialect == "sqlite":
        # Avoid batch_alter_table FK reflection quirks on SQLite downgrade,
        # same approach as 20260811_0006's tracked_items downgrade.
        keep = [c["name"] for c in insp.get_columns("game_releases") if c["name"] not in names]
        if not keep:
            return
        cols_csv = ", ".join(f'"{c}"' for c in keep)
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
        bind.exec_driver_sql('ALTER TABLE "game_releases" RENAME TO "_game_releases_old"')
        bind.exec_driver_sql(
            f'CREATE TABLE "game_releases" AS SELECT {cols_csv} FROM "_game_releases_old"'
        )
        bind.exec_driver_sql('DROP TABLE "_game_releases_old"')
        bind.exec_driver_sql("PRAGMA foreign_keys=ON")
        return
    with op.batch_alter_table("game_releases") as batch:
        for name in names:
            batch.drop_column(name)
