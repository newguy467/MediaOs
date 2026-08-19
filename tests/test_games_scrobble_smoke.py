"""Smoke tests for Games, Scrobbling, and Tracking modules."""
import pytest


def test_games_router_importable():
    from app.routers import games
    assert games.router is not None


def test_scrobbling_router_importable():
    from app.routers import scrobbling
    assert scrobbling.router is not None


def test_tracking_router_importable():
    from app.routers import tracking
    assert tracking.router is not None


def test_game_models_importable():
    from app.models import Game, Platform, ScrobbleEvent, TrackedItem, WatchProgress
    assert Game.__tablename__ == "games"
    assert Platform.__tablename__ == "platforms"
    assert ScrobbleEvent.__tablename__ == "scrobble_events"
    assert TrackedItem.__tablename__ == "tracked_items"


def test_version_consistent():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    ver = (root / "VERSION").read_text().strip()
    assert ver, "VERSION file must not be empty"
    # Dockerfile ARG must match the VERSION file (single source of truth)
    docker = (root / "Dockerfile").read_text()
    assert f"APP_VERSION={ver}" in docker
