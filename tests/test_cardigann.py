"""Cardigann template + definition loading (no network)."""
from __future__ import annotations

from pathlib import Path

from app.services.cardigann import (
    get_definition,
    list_definitions,
    load_definition,
    render_template,
)


def test_render_keywords():
    ctx = {"Keywords": "Inception 2010", "Query": {"Q": "Inception 2010"}, "Config": {"sitelink": "https://yts.mx/"}}
    assert render_template("q={{ .Keywords }}", ctx) == "q=Inception 2010"
    assert "yts" in render_template("{{ .Config.sitelink }}api", ctx)


def test_render_if_else():
    ctx = {"Keywords": "foo", "Query": {}, "Config": {}}
    assert render_template("{{ if .Keywords }}yes{{ else }}no{{ end }}", ctx) == "yes"
    ctx2 = {"Keywords": "", "Query": {}, "Config": {}}
    assert render_template("{{ if .Keywords }}yes{{ else }}no{{ end }}", ctx2) == "no"


def test_load_shipped_yts_definition(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1] / "definitions"
    if not (root / "yts.yml").exists():
        # copy minimal
        d = tmp_path / "defs"
        d.mkdir()
        (d / "yts.yml").write_text(
            "id: yts\nname: YTS\ntype: public\nlinks: [https://yts.mx/]\nsearch:\n  paths: [{path: api}]\n"
        )
        monkeypatch.setattr("app.services.cardigann.definitions_dir", lambda: d)
    else:
        monkeypatch.setattr("app.services.cardigann.definitions_dir", lambda: root)

    defs = list_definitions()
    assert any(d["id"] == "yts" for d in defs)
    d = get_definition("yts")
    assert d is not None
    assert d.get("name")
    assert d.get("search")


def test_load_definition_requires_id(tmp_path):
    bad = tmp_path / "bad.yml"
    bad.write_text("description: nope\n")
    try:
        load_definition(bad)
        assert False, "expected ValueError"
    except ValueError:
        pass
