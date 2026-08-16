"""Comics last_read_at for Continue Reading sort order — idempotent.

Revision ID: 20260815_0010
Revises: 20260815_0009
Create Date: 2026-08-15

Runtime uses the schema_migrate soft path (version "2.0.30") for this
additive column; this revision mirrors it for CI.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260815_0010"
down_revision: Union[str, None] = "20260815_0009"
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
    if "last_read_at" not in cols:
        op.add_column("comic_issues", sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    if "comic_issues" not in _tables():
        return
    cols = _cols("comic_issues")
    if "last_read_at" in cols:
        op.drop_column("comic_issues", "last_read_at")
