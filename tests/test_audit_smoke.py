"""Smoke tests from production audit — imports, auth gate, migration present."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_all_app_python_parses():
    errors = []
    for p in (ROOT / "app").rglob("*.py"):
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as e:
            errors.append(f"{p}:{e.lineno}: {e.msg}")
    assert not errors, errors


def test_auth_require_disables_gate(monkeypatch):
    from app.config import settings
    from app import auth

    monkeypatch.setattr(settings, "auth_require", False)
    monkeypatch.setattr(settings, "auth_username", "admin")
    monkeypatch.setattr(settings, "auth_api_key", "secret")
    monkeypatch.setattr(auth, "_db_user_count", lambda: 1)
    assert auth._auth_enabled() is False


def test_auth_require_enables_when_credentials(monkeypatch):
    from app.config import settings
    from app import auth

    monkeypatch.setattr(settings, "auth_require", True)
    monkeypatch.setattr(settings, "auth_username", "admin")
    monkeypatch.setattr(settings, "auth_api_key", "")
    monkeypatch.setattr(auth, "_db_user_count", lambda: 0)
    assert auth._auth_enabled() is True


def test_limetorrents_disabled_by_default():
    from app.services.builtin_indexers import INDEXERS

    lime = next(i for i in INDEXERS if i["id"] == "limetorrents")
    assert lime["enabled"] is False


def test_combined_migration_file_exists():
    versions = list((ROOT / "alembic" / "versions").glob("*0006*"))
    assert versions, "missing 0006 migration"
    text = versions[0].read_text(encoding="utf-8")
    assert "tracked_items" in text
    assert "homelab_links" in text
    assert "tracking_history" in text


def test_notice_and_license_present():
    assert (ROOT / "NOTICE").is_file()
    assert (ROOT / "LICENSE").is_file()
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    assert "GPL-2.0" in notice or "GPL" in notice


def test_openapi_no_duplicate_operation_ids():
    from collections import Counter
    from app.main import app

    schema = app.openapi()
    ids = []
    for path, methods in schema.get("paths", {}).items():
        for method, op in methods.items():
            if method.startswith("x-"):
                continue
            oid = op.get("operationId")
            if oid:
                ids.append(oid)
    dups = [k for k, v in Counter(ids).items() if v > 1]
    assert not dups, dups
