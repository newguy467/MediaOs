"""Music smart playlists: genre/mood on media_items, play_count on
music_tracks, new music_smartlists table — idempotent.

Revision ID: 20260815_0008
Revises: 20260811_0007
Create Date: 2026-08-15

Runtime uses the schema_migrate soft path (version "2.0.28") for the two
additive columns; this revision mirrors those plus the new table for CI.
music_smartlists is a saved *filter* over the existing library (see
app/models.py MusicSmartlist / app/services/music_smartlists.py) — distinct
from SmartList, which discovers+adds new items from external APIs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260815_0008"
down_revision: Union[str, None] = "20260811_0007"
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
            if "genre" not in cols_mi:
                batch.add_column(sa.Column("genre", sa.String(), nullable=True))
            if "mood" not in cols_mi:
                batch.add_column(sa.Column("mood", sa.String(), nullable=True))

    cols_mt = _cols("music_tracks")
    if "music_tracks" in _tables() and "play_count" not in cols_mt:
        with op.batch_alter_table("music_tracks") as batch:
            batch.add_column(sa.Column("play_count", sa.Integer(), server_default="0"))

    if "music_smartlists" not in _tables():
        op.create_table(
            "music_smartlists",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("source", sa.String(), server_default="library_genre"),
            sa.Column("genre_filter", sa.String(), nullable=True),
            sa.Column("mood_filter", sa.String(), nullable=True),
            sa.Column("added_within_days", sa.Integer(), nullable=True),
            sa.Column("min_play_count", sa.Integer(), nullable=True),
            sa.Column("result_limit", sa.Integer(), server_default="50"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    if "music_smartlists" in _tables():
        op.drop_table("music_smartlists")

    cols_mt = _cols("music_tracks")
    if "play_count" in cols_mt:
        with op.batch_alter_table("music_tracks") as batch:
            batch.drop_column("play_count")

    cols_mi = _cols("media_items")
    if "media_items" in _tables():
        with op.batch_alter_table("media_items") as batch:
            if "mood" in cols_mi:
                batch.drop_column("mood")
            if "genre" in cols_mi:
                batch.drop_column("genre")
