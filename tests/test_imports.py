"""Import smoke — catch syntax/circular errors early."""
from __future__ import annotations

import importlib
import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:////tmp/mediaos-pytest.db")

MODULES = [
    "app.config",
    "app.services.usenet_stream",
    "app.services.cardigann",
    "app.services.builtin_indexers",
    "app.services.streaming",
    "app.services.quality.parser",
    "app.clients.torznab",
    "app.clients.youtube",
]


def test_import_core_modules():
    errors = []
    for name in MODULES:
        try:
            importlib.import_module(name)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    assert not errors, "Import failures:\n" + "\n".join(errors)


def test_import_models_with_sqlite():
    importlib.import_module("app.models")
