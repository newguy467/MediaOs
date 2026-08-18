"""Test defaults that keep import/smoke tests independent of a live Postgres service."""
from __future__ import annotations

import os
from pathlib import Path

# Use /tmp to avoid sandbox disk I/O quirks on the workspace volume.
_db = Path(f"/tmp/mediaos-test-{os.getpid()}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ.setdefault("AUTH_REQUIRE", "false")

import pytest


@pytest.fixture(scope="session")
def app():
    """FastAPI app with SQLite schema created (no scheduler noise)."""
    if _db.exists():
        try:
            _db.unlink()
        except OSError:
            pass
    from app.database import Base, engine
    from app import main as main_mod

    Base.metadata.create_all(bind=engine)
    from app.services.schema_migrate import run_schema_migrations
    # Migration failures must fail the test session instead of being silently
    # swallowed and producing misleading "no such table" errors later.
    run_schema_migrations(engine)
    return main_mod.app


@pytest.fixture()
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def db():
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def make_item(db):
    """Factory: create a MediaItem row and return it (committed)."""
    from app.models import MediaItem, MediaType, ItemStatus

    created = []

    def _make(
        media_type: str = "movie",
        title: str = "Test Item",
        external_id: int | None = None,
        monitored: bool = True,
        **kw,
    ):
        mt = MediaType(media_type) if not isinstance(media_type, MediaType) else media_type
        if external_id is None:
            external_id = 900000 + len(created) + abs(hash(title)) % 100000
        item = MediaItem(
            media_type=mt,
            external_id=int(external_id) % 2000000000,
            title=title,
            monitored=monitored,
            status=kw.pop("status", ItemStatus.wanted),
            **kw,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        created.append(item)
        return item

    yield _make

    for item in created:
        try:
            db.delete(item)
            db.commit()
        except Exception:
            db.rollback()
