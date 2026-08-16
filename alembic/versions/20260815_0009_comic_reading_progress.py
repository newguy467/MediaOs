"""Comics reading progress: is_read/last_page_read on comic_issues — idempotent.

Revision ID: 20260815_0009
Revises: 20260815_0008
Create Date: 2026-08-15

Runtime uses the schema_migrate soft path (version "2.0.29") for these two
additive columns; this revision mirrors them for CI. Same shape as music's
play_count from the prior revision — powers a future "Continue Reading" row
the way play_count powers music's "most played" smart-playlist source.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260815_0009"
down_revision: Union[str, None] = "20260815_0008"
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
    if "comic_issues" not in _tables():
        return
    cols = _cols("comic_issues")
    with op.batch_alter_table("comic_issues") as batch:
        if "is_read" not in cols:
            batch.add_column(sa.Column("is_read", sa.Boolean(), server_default=sa.false()))
        if "last_page_read" not in cols:
            batch.add_column(sa.Column("last_page_read", sa.Integer(), nullable=True))


def downgrade() -> None:
    if "comic_issues" not in _tables():
        return
    cols = _cols("comic_issues")
    with op.batch_alter_table("comic_issues") as batch:
        if "last_page_read" in cols:
            batch.drop_column("last_page_read")
        if "is_read" in cols:
            batch.drop_column("is_read")
