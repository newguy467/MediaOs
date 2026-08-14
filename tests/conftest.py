"""Test defaults that keep import/smoke tests independent of a live Postgres service."""
import os

# CI/local smoke tests should not require a running database just to import the
# application. Production/Docker still supplies DATABASE_URL explicitly.
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test-mediaos.db")
