"""Quality package smoke."""
from __future__ import annotations
import importlib


def test_quality_package_importable():
    for name in (
        "app.services.quality",
        "app.services.quality.parser",
        "app.services.quality.profiles",
        "app.services.quality.store",
    ):
        importlib.import_module(name)


def test_parser_has_callable():
    mod = importlib.import_module("app.services.quality.parser")
    assert any(callable(getattr(mod, n, None)) for n in dir(mod) if not n.startswith("_"))
