"""Versioned soft schema migrations for MediaOS v2.

AUTHORITATIVE at runtime (main.py). Alembic mirrors these columns for CI and is idempotent.

Replaces growing ad-hoc ALTER lists in on_startup with a tracked, idempotent
migration runner. create_all still handles brand-new tables; these statements
cover additive column changes for upgrades from older DBs.
"""
from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Engine

log = logging.getLogger("mediaos.schema_migrate")

# (version, description, statements)
# Statements must be safe to re-run (IF NOT EXISTS where possible, or ignore errors).
MIGRATIONS: list[tuple[str, str, list[str]]] = [
    (
        "2.0.0",
        "Core v2 additive columns (episodes, media_items, indexers, users, livetv, quality, downloads)",
        [
            "ALTER TABLE episodes ADD COLUMN absolute_episode_number INTEGER",
            "ALTER TABLE media_items ADD COLUMN series_type VARCHAR",
            "ALTER TABLE indexers ADD COLUMN credentials_json TEXT",
            "ALTER TABLE users ADD COLUMN permissions_json TEXT",
            "ALTER TABLE media_items ADD COLUMN series_status VARCHAR",
            "ALTER TABLE media_items ADD COLUMN desired_qualities VARCHAR",
            "ALTER TABLE media_items ADD COLUMN series_name VARCHAR",
            "ALTER TABLE livetv_channels ADD COLUMN sort_order INTEGER DEFAULT 0",
            "ALTER TABLE livetv_channels ADD COLUMN epg_tvg_id VARCHAR",
            "ALTER TABLE livetv_channels ADD COLUMN fail_count INTEGER DEFAULT 0",
            "ALTER TABLE livetv_channels ADD COLUMN last_check_at TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE quality_profiles ADD COLUMN retention_policy VARCHAR DEFAULT 'best_only'",
            "ALTER TABLE quality_profiles ADD COLUMN keep_n INTEGER DEFAULT 2",
            "ALTER TABLE downloads ADD COLUMN game_id INTEGER",
            "ALTER TABLE downloads ADD COLUMN strikes INTEGER DEFAULT 0",
            "ALTER TABLE downloads ADD COLUMN last_error VARCHAR",
        ],
    ),
    (
        "2.0.3",
        "Queue + scrobble consistency: media_type on downloads, progress keys",
        [
            "ALTER TABLE downloads ADD COLUMN media_type VARCHAR",
        ],
    ),
    (
        "2.0.4",
        "Provider IDs + series-record rules + download media_type",
        [
            "ALTER TABLE media_items ADD COLUMN imdb_id VARCHAR",
            "ALTER TABLE media_items ADD COLUMN tvdb_id INTEGER",
            "ALTER TABLE media_items ADD COLUMN external_ids TEXT",
            "ALTER TABLE downloads ADD COLUMN media_type VARCHAR",
            "ALTER TABLE livetv_recordings ADD COLUMN series_rule_id INTEGER",
        ],
    ),
    (
        "2.0.5",
        "Polish: provider IDs backfill-ready, series rules table via create_all",
        [
            "ALTER TABLE media_items ADD COLUMN imdb_id VARCHAR",
            "ALTER TABLE media_items ADD COLUMN tvdb_id INTEGER",
            "ALTER TABLE media_items ADD COLUMN external_ids TEXT",
            "ALTER TABLE livetv_recordings ADD COLUMN series_rule_id INTEGER",
        ],
    ),
    (
        "2.0.6",
        "LiveTV health cycle: last_ok_at/last_error/created_at on livetv_channels "
        "(fixes auto-delete-after-offline-hours crashing with AttributeError)",
        [
            "ALTER TABLE livetv_channels ADD COLUMN last_ok_at TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE livetv_channels ADD COLUMN last_error TEXT",
            "ALTER TABLE livetv_channels ADD COLUMN created_at TIMESTAMP WITH TIME ZONE",
        ],
    ),
    (
        "2.0.20",
        "Tdarr-class converter: attempts + health_ok on convert_jobs",
        [
            "ALTER TABLE convert_jobs ADD COLUMN attempts INTEGER DEFAULT 0",
            "ALTER TABLE convert_jobs ADD COLUMN health_ok BOOLEAN",
            "ALTER TABLE convert_jobs ADD COLUMN health_message VARCHAR",
        ],
    ),
    (
        "2.0.28",
        "Music smart playlists: genre/mood on media_items, play_count on "
        "music_tracks (music_smartlists table itself is new — created via "
        "create_all, no ALTER needed)",
        [
            "ALTER TABLE media_items ADD COLUMN genre VARCHAR",
            "ALTER TABLE media_items ADD COLUMN mood VARCHAR",
            "ALTER TABLE music_tracks ADD COLUMN play_count INTEGER DEFAULT 0",
        ],
    ),
    (
        "2.0.29",
        "Comics reading progress: is_read/last_page_read on comic_issues "
        "(powers a future Continue Reading row, same shape as music's "
        "play_count)",
        [
            "ALTER TABLE comic_issues ADD COLUMN is_read BOOLEAN DEFAULT FALSE",
            "ALTER TABLE comic_issues ADD COLUMN last_page_read INTEGER",
        ],
    ),
    (
        "2.0.30",
        "Comics last_read_at timestamp so Continue Reading can sort by "
        "most recently read issue",
        [
            "ALTER TABLE comic_issues ADD COLUMN last_read_at TIMESTAMP",
        ],
    ),
]


def _ensure_migrations_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR PRIMARY KEY,
                description VARCHAR,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def _applied_versions(conn) -> set[str]:
    try:
        rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def _run_statements(conn, statements: Iterable[str], dialect: str) -> int:
    applied = 0
    for stmt in statements:
        s = stmt.strip()
        if not s:
            continue
        # Postgres prefers IF NOT EXISTS for ADD COLUMN
        if dialect == "postgresql" and "ADD COLUMN" in s.upper() and "IF NOT EXISTS" not in s.upper():
            s = s.replace("ADD COLUMN", "ADD COLUMN IF NOT EXISTS", 1)
        try:
            conn.execute(text(s))
            applied += 1
        except Exception as e:
            # Column already exists or table missing on fresh DB — ignore
            msg = str(e).lower()
            if any(x in msg for x in ("already exists", "duplicate column", "no such table")):
                continue
            log.debug("soft-migrate skip %s: %s", s[:60], e)
    return applied


def run_schema_migrations(engine: Engine) -> dict:
    """Apply pending soft migrations. Safe to call on every startup."""
    result = {"applied": [], "skipped": [], "errors": []}
    dialect = engine.dialect.name
    with engine.begin() as conn:
        _ensure_migrations_table(conn)
        done = _applied_versions(conn)
        for version, description, statements in MIGRATIONS:
            if version in done:
                result["skipped"].append(version)
                continue
            try:
                n = _run_statements(conn, statements, dialect)
                conn.execute(
                    text(
                        "INSERT INTO schema_migrations (version, description) VALUES (:v, :d)"
                    ),
                    {"v": version, "d": description},
                )
                result["applied"].append({"version": version, "statements": n, "description": description})
                log.info("schema migrate %s: %s (%d stmts)", version, description, n)
            except Exception as e:
                result["errors"].append({"version": version, "error": str(e)})
                log.warning("schema migrate %s failed: %s", version, e)
    return result
