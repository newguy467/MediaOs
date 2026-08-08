#!/usr/bin/env python3
"""Run offline unit smoke without pytest (CI fallback)."""
from __future__ import annotations

import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
# Prefer sqlite so importing app.database does not require psycopg2
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:////tmp/mediaos-smoke.db")

failures = 0


def check(name, fn):
    global failures
    try:
        fn()
        print(f"  PASS  {name}")
    except Exception as e:
        failures += 1
        print(f"  FAIL  {name}: {e}")
        traceback.print_exc()


def main() -> int:
    print("== unit smoke ==")

    def usenet():
        from app.services.usenet_stream import yenc_decode, parse_nzb, map_range_to_segments, status
        raw = b"=ybegin name=x\r\n" + bytes([0x41 + 42]) + b"\r\n=yend\r\n"
        assert yenc_decode(raw) == b"A"
        nzb = """<?xml version='1.0'?><nzb xmlns='http://www.newzbin.com/DTD/2003/nzb'>
          <file subject='f'><segments>
            <segment number='1' bytes='10'>a@x</segment>
            <segment number='2' bytes='10'>b@x</segment>
          </segments></file></nzb>"""
        files = parse_nzb(nzb)
        assert files[0].total_est() == 20
        assert status()["seekable"] is True
        assert len(map_range_to_segments(files[0], 5, 15)) == 2

    def cardigann():
        from pathlib import Path
        import app.services.cardigann as c
        c.definitions_dir = lambda: Path(ROOT) / "definitions"
        defs = c.list_definitions()
        assert any(d["id"] == "yts" for d in defs)
        assert c.render_template("{{ .Keywords }}", {"Keywords": "x", "Query": {}, "Config": {}}) == "x"

    def imports():
        import importlib
        for m in (
            "app.config",
            "app.services.cardigann",
            "app.services.usenet_stream",
            "app.services.builtin_indexers",
        ):
            importlib.import_module(m)
        # models pulls DB engine — works with sqlite URL above
        importlib.import_module("app.models")

    check("usenet_stream", usenet)
    check("cardigann", cardigann)
    check("imports", imports)

    if failures:
        print(f"FAILED ({failures})")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
