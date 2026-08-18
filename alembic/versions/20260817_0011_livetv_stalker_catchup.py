"""Live TV Stalker MAC on sources + catch-up/timeshift fields on channels — idempotent.

Revision ID: 20260817_0011
Revises: 20260815_0010
Create Date: 2026-08-17

Runtime uses the schema_migrate soft path (version "2.0.31") for these
additive columns; this revision mirrors it for CI.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260817_0011"
down_revision: Union[str, None] = "20260815_0010"
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
    tables = _tables()
    if "livetv_sources" in tables:
        cols = _cols("livetv_sources")
        if "stalker_mac" not in cols:
            op.add_column("livetv_sources", sa.Column("stalker_mac", sa.String(), nullable=True))
    if "livetv_channels" in tables:
        cols = _cols("livetv_channels")
        if "catchup" not in cols:
            op.add_column("livetv_channels", sa.Column("catchup", sa.Boolean(), server_default=sa.false(), nullable=True))
        if "catchup_days" not in cols:
            op.add_column("livetv_channels", sa.Column("catchup_days", sa.Integer(), server_default="0", nullable=True))
        if "external_id" not in cols:
            op.add_column("livetv_channels", sa.Column("external_id", sa.String(), nullable=True))


def downgrade() -> None:
    if "livetv_sources" in _tables():
        cols = _cols("livetv_sources")
        if "stalker_mac" in cols:
            op.drop_column("livetv_sources", "stalker_mac")
    if "livetv_channels" in _tables():
        cols = _cols("livetv_channels")
        for c in ("catchup", "catchup_days", "external_id"):
            if c in cols:
                op.drop_column("livetv_channels", c)
