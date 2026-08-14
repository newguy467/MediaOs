"""Add LiveTv virtual channel tables for library-as-TV feature.

Revision ID: 20260810_0004
Revises: 20260810_0003
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260810_0004"
down_revision: Union[str, None] = "20260810_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    # Health fields required by fixed livetv.run_channel_health_cycle
    if "livetv_channels" in tables:
        cols = {c["name"] for c in insp.get_columns("livetv_channels")}
        if "last_ok_at" not in cols:
            op.add_column("livetv_channels", sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True))
        if "last_error" not in cols:
            op.add_column("livetv_channels", sa.Column("last_error", sa.Text(), nullable=True))
        if "created_at" not in cols:
            op.add_column("livetv_channels", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))


    if "livetv_virtual_channels" not in tables:
        op.create_table(
            "livetv_virtual_channels",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("number", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("group_title", sa.String(), nullable=True),
            sa.Column("logo", sa.String(), nullable=True),
            sa.Column("enabled", sa.Boolean(), server_default=sa.text("true")),
            sa.Column("media_types", sa.String(), server_default='["movie"]'),
            sa.Column("media_item_ids", sa.Text(), nullable=True),
            sa.Column("genre_filter", sa.String(), nullable=True),
            sa.Column("title_filter", sa.String(), nullable=True),
            sa.Column("year_min", sa.Integer(), nullable=True),
            sa.Column("year_max", sa.Integer(), nullable=True),
            sa.Column("randomize", sa.Boolean(), server_default=sa.text("true")),
            sa.Column("repeat_protection_days", sa.Integer(), server_default="7"),
            sa.Column("prime_time_movies", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("schedule_filled_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("stream_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("stream_pid", sa.Integer(), nullable=True),
            sa.Column("stream_status", sa.String(), server_default="stopped"),
            sa.Column("stream_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_livetv_virtual_channels_number", "livetv_virtual_channels", ["number"], unique=True)

    if "livetv_virtual_schedule_items" not in tables:
        op.create_table(
            "livetv_virtual_schedule_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("virtual_channel_id", sa.Integer(), sa.ForeignKey("livetv_virtual_channels.id"), nullable=False),
            sa.Column("media_item_id", sa.Integer(), sa.ForeignKey("media_items.id"), nullable=True),
            sa.Column("episode_id", sa.Integer(), sa.ForeignKey("episodes.id"), nullable=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("file_path", sa.Text(), nullable=False),
            sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("duration_seconds", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_livetv_virtual_schedule_items_virtual_channel_id", "livetv_virtual_schedule_items", ["virtual_channel_id"])
        op.create_index("ix_livetv_virtual_schedule_items_start_time", "livetv_virtual_schedule_items", ["start_time"])


def downgrade() -> None:
    op.drop_table("livetv_virtual_schedule_items")
    op.drop_table("livetv_virtual_channels")
