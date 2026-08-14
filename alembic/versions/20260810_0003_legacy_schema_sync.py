"""Import the legacy v2 soft-migration columns into Alembic.

Revision ID: 20260810_0003
Revises: 20260810_0002
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260810_0003"
down_revision: Union[str, None] = "20260810_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _add(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return
    if column.name not in {c["name"] for c in insp.get_columns(table)}:
        op.add_column(table, column)

def upgrade() -> None:
    specs = [
        ("episodes", sa.Column("absolute_episode_number", sa.Integer(), nullable=True)),
        ("media_items", sa.Column("series_type", sa.String(), nullable=True)),
        ("media_items", sa.Column("series_status", sa.String(), nullable=True)),
        ("media_items", sa.Column("desired_qualities", sa.String(), nullable=True)),
        ("media_items", sa.Column("series_name", sa.String(), nullable=True)),
        ("indexers", sa.Column("credentials_json", sa.Text(), nullable=True)),
        ("users", sa.Column("permissions_json", sa.Text(), nullable=True)),
        ("livetv_channels", sa.Column("sort_order", sa.Integer(), server_default="0", nullable=True)),
        ("livetv_channels", sa.Column("epg_tvg_id", sa.String(), nullable=True)),
        ("livetv_channels", sa.Column("fail_count", sa.Integer(), server_default="0", nullable=True)),
        ("livetv_channels", sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True)),
        ("quality_profiles", sa.Column("retention_policy", sa.String(), server_default="best_only", nullable=True)),
        ("quality_profiles", sa.Column("keep_n", sa.Integer(), server_default="2", nullable=True)),
        ("downloads", sa.Column("game_id", sa.Integer(), nullable=True)),
        ("downloads", sa.Column("strikes", sa.Integer(), server_default="0", nullable=True)),
        ("downloads", sa.Column("last_error", sa.String(), nullable=True)),
    ]
    for table, column in specs:
        _add(table, column)

def downgrade() -> None:
    # These columns may have existed before this revision, so a destructive
    # downgrade would risk deleting user data. Leave them in place.
    pass
