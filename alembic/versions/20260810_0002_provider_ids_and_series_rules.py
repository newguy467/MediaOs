"""Provider IDs, series rules, downloads.media_type — idempotent.

Revision ID: 20260810_0002
Revises: 20260810_0001
Create Date: 2026-08-10

Runtime uses schema_migrate soft path. This revision mirrors columns for CI
and is safe to run after soft-migrate (column presence checked).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260810_0002"
down_revision: Union[str, None] = "20260810_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cols(table: str) -> set[str]:
    bind = op.get_bind()
    try:
        return {c["name"] for c in inspect(bind).get_columns(table)}
    except Exception:
        return set()


def _tables() -> set[str]:
    bind = op.get_bind()
    try:
        return set(inspect(bind).get_table_names())
    except Exception:
        return set()


def upgrade() -> None:
    cols_mi = _cols("media_items")
    if "media_items" in _tables():
        with op.batch_alter_table("media_items") as batch:
            if "imdb_id" not in cols_mi:
                batch.add_column(sa.Column("imdb_id", sa.String(), nullable=True))
            if "tvdb_id" not in cols_mi:
                batch.add_column(sa.Column("tvdb_id", sa.Integer(), nullable=True))
            if "external_ids" not in cols_mi:
                batch.add_column(sa.Column("external_ids", sa.Text(), nullable=True))

    cols_dl = _cols("downloads")
    if "downloads" in _tables() and "media_type" not in cols_dl:
        with op.batch_alter_table("downloads") as batch:
            batch.add_column(sa.Column("media_type", sa.String(), nullable=True))

    if "livetv_series_rules" not in _tables():
        op.create_table(
            "livetv_series_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title_match", sa.String(), nullable=False),
            sa.Column("match_mode", sa.String(), server_default="contains"),
            sa.Column("channel_id", sa.Integer(), nullable=True),
            sa.Column("enabled", sa.Boolean(), server_default=sa.text("1")),
            sa.Column("keep_episodes", sa.Integer(), server_default="0"),
            sa.Column("priority", sa.Integer(), server_default="50"),
            sa.Column("only_new", sa.Boolean(), server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    cols_rec = _cols("livetv_recordings")
    if "livetv_recordings" in _tables() and "series_rule_id" not in cols_rec:
        with op.batch_alter_table("livetv_recordings") as batch:
            batch.add_column(sa.Column("series_rule_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    cols_rec = _cols("livetv_recordings")
    if "series_rule_id" in cols_rec:
        with op.batch_alter_table("livetv_recordings") as batch:
            batch.drop_column("series_rule_id")
    if "livetv_series_rules" in _tables():
        op.drop_table("livetv_series_rules")
    cols_dl = _cols("downloads")
    if "media_type" in cols_dl:
        with op.batch_alter_table("downloads") as batch:
            batch.drop_column("media_type")
    cols_mi = _cols("media_items")
    if "media_items" in _tables():
        with op.batch_alter_table("media_items") as batch:
            if "external_ids" in cols_mi:
                batch.drop_column("external_ids")
            if "tvdb_id" in cols_mi:
                batch.drop_column("tvdb_id")
            if "imdb_id" in cols_mi:
                batch.drop_column("imdb_id")
