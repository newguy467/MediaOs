"""Add Games, Scrobbling, and Tracking tables (MediaOS v2).

Revision ID: 20260810_0005
Revises: 20260810_0004
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260810_0005"
down_revision: Union[str, None] = "20260810_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "platforms" not in tables:
        op.create_table(
            "platforms",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False, unique=True),
            sa.Column("icon_url", sa.String(), nullable=True),
            sa.Column("metadata_provider", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    if "games" not in tables:
        op.create_table(
            "games",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("sort_title", sa.String(), nullable=True),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("overview", sa.Text(), nullable=True),
            sa.Column("poster_path", sa.String(), nullable=True),
            sa.Column("fanart_path", sa.String(), nullable=True),
            sa.Column("external_ids", sa.Text(), nullable=True),
            sa.Column("genres", sa.String(), nullable=True),
            sa.Column("platform_id", sa.Integer(), sa.ForeignKey("platforms.id"), nullable=True),
            sa.Column("monitored", sa.Boolean(), server_default=sa.text("true")),
            sa.Column("status", sa.String(), server_default="wanted"),
            sa.Column("path", sa.String(), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("playtime_minutes", sa.Integer(), server_default="0"),
            sa.Column("completion_percent", sa.Float(), server_default="0"),
            sa.Column("last_played_at", sa.DateTime(), nullable=True),
            sa.Column("quality_profile", sa.String(), nullable=True),
            sa.Column("install_path", sa.String(), nullable=True),
            sa.Column("launcher", sa.String(), nullable=True),
            sa.Column("added_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if "game_releases" not in tables:
        op.create_table(
            "game_releases",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("indexer", sa.String(), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("seeders", sa.Integer(), nullable=True),
            sa.Column("download_url", sa.String(), nullable=True),
            sa.Column("info_url", sa.String(), nullable=True),
            sa.Column("protocol", sa.String(), nullable=True),
            sa.Column("quality", sa.String(), nullable=True),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("grabbed", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    if "watch_progress" not in tables:
        op.create_table(
            "watch_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("media_item_id", sa.Integer(), sa.ForeignKey("media_items.id"), nullable=True),
            sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=True),
            sa.Column("episode_id", sa.Integer(), nullable=True),
            sa.Column("season_number", sa.Integer(), nullable=True),
            sa.Column("episode_number", sa.Integer(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("progress_percent", sa.Float(), server_default="0"),
            sa.Column("position_seconds", sa.Integer(), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column("play_count", sa.Integer(), server_default="0"),
            sa.Column("completed", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("last_watched_at", sa.DateTime(), nullable=True),
            sa.Column("source", sa.String(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if "scrobble_events" not in tables:
        op.create_table(
            "scrobble_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("media_item_id", sa.Integer(), sa.ForeignKey("media_items.id"), nullable=True),
            sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=True),
            sa.Column("episode_id", sa.Integer(), nullable=True),
            sa.Column("season_number", sa.Integer(), nullable=True),
            sa.Column("episode_number", sa.Integer(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("progress_percent", sa.Float(), server_default="0"),
            sa.Column("position_seconds", sa.Integer(), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(), nullable=True),
            sa.Column("raw_payload", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    if "tracked_items" not in tables:
        op.create_table(
            "tracked_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("media_type", sa.String(), nullable=False),
            sa.Column("media_item_id", sa.Integer(), sa.ForeignKey("media_items.id"), nullable=True),
            sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=True),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("status", sa.String(), server_default="planned"),
            sa.Column("rating", sa.Float(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("tags", sa.String(), nullable=True),
            sa.Column("progress_percent", sa.Float(), server_default="0"),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for t in ("tracked_items", "scrobble_events", "watch_progress", "game_releases", "games", "platforms"):
        if t in tables:
            op.drop_table(t)
