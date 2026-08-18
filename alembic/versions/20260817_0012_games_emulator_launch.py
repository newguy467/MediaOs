"""Games emulator launch: Platform.emulator_command + GameInstallJob.kind — idempotent.

Revision ID: 20260817_0012
Revises: 20260817_0011
Create Date: 2026-08-17

Runtime uses the schema_migrate soft path (version "2.0.33") for these two
additive columns; this revision mirrors them for CI.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260817_0012"
down_revision: Union[str, None] = "20260817_0011"
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
    if "platforms" in tables:
        cols = _cols("platforms")
        if "emulator_command" not in cols:
            op.add_column("platforms", sa.Column("emulator_command", sa.String(), nullable=True))
    if "game_install_jobs" in tables:
        cols = _cols("game_install_jobs")
        if "kind" not in cols:
            op.add_column(
                "game_install_jobs",
                sa.Column("kind", sa.String(), server_default="install", nullable=True),
            )


def downgrade() -> None:
    if "platforms" in _tables():
        cols = _cols("platforms")
        if "emulator_command" in cols:
            op.drop_column("platforms", "emulator_command")
    if "game_install_jobs" in _tables():
        cols = _cols("game_install_jobs")
        if "kind" in cols:
            op.drop_column("game_install_jobs", "kind")
