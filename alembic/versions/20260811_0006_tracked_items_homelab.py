"""Add tracked_items missing columns + homelab_links and tracking_history tables.

Combines the 2.0.19 tracked_items column fix with the 2.0.20 homelab/tracking
history tables so both land under a single revision after 20260810_0005.

Revision ID: 20260811_0006
Revises: 20260810_0005
Create Date: 2026-08-11
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260811_0006"
down_revision: Union[str, None] = "20260810_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TRACKED_COLUMNS = [
    sa.Column("season_number", sa.Integer(), nullable=True),
    sa.Column("episode_number", sa.Integer(), nullable=True),
    sa.Column("rewatch_count", sa.Integer(), nullable=True, server_default="0"),
    sa.Column("started_at", sa.DateTime(), nullable=True),
    sa.Column("completed_at", sa.DateTime(), nullable=True),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    # --- tracked_items missing columns (from 2.0.19 fix pass) ---
    if "tracked_items" in tables:
        existing = {c["name"] for c in insp.get_columns("tracked_items")}
        with op.batch_alter_table("tracked_items") as batch:
            for col in _NEW_TRACKED_COLUMNS:
                if col.name not in existing:
                    batch.add_column(col)

    # --- tracking_history + homelab_links (from 2.0.20) ---
    if "tracking_history" not in tables:
        op.create_table(
            "tracking_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tracked_item_id", sa.Integer(), sa.ForeignKey("tracked_items.id"), nullable=True),
            sa.Column("media_item_id", sa.Integer(), sa.ForeignKey("media_items.id"), nullable=True),
            sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=True),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    if "homelab_links" not in tables:
        op.create_table(
            "homelab_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("url", sa.String(), nullable=False),
            sa.Column("icon_url", sa.String(), nullable=True),
            sa.Column("group_name", sa.String(), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default="0"),
            sa.Column("enabled", sa.Boolean(), server_default=sa.text("true")),
            sa.Column("iframe", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("health_check_url", sa.String(), nullable=True),
            sa.Column("last_status", sa.String(), nullable=True),
            sa.Column("last_check_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    dialect = bind.dialect.name

    # Drop dependents first. On SQLite, avoid reflecting missing parent tables
    # by issuing raw DROP when needed.
    for t in ("tracking_history", "homelab_links"):
        if t not in tables:
            continue
        if dialect == "sqlite":
            bind.exec_driver_sql(f'DROP TABLE IF EXISTS "{t}"')
        else:
            op.drop_table(t)

    # Re-inspect after drops
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "tracked_items" not in tables:
        return
    existing = {c["name"] for c in insp.get_columns("tracked_items")}
    cols_to_drop = [col.name for col in _NEW_TRACKED_COLUMNS if col.name in existing]
    if not cols_to_drop:
        return
    if dialect == "sqlite":
        # Avoid batch_alter_table FK reflection against missing media_items.
        # Rebuild tracked_items without the additive columns using raw SQL.
        keep = [c["name"] for c in insp.get_columns("tracked_items") if c["name"] not in cols_to_drop]
        if not keep:
            return
        cols_csv = ", ".join(f'"{c}"' for c in keep)
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
        bind.exec_driver_sql('ALTER TABLE "tracked_items" RENAME TO "_tracked_items_old"')
        # Recreate from model-ish minimal schema by copying remaining columns via CREATE AS
        bind.exec_driver_sql(
            f'CREATE TABLE "tracked_items" AS SELECT {cols_csv} FROM "_tracked_items_old"'
        )
        bind.exec_driver_sql('DROP TABLE "_tracked_items_old"')
        bind.exec_driver_sql("PRAGMA foreign_keys=ON")
        return
    with op.batch_alter_table("tracked_items") as batch:
        for name in cols_to_drop:
            batch.drop_column(name)
