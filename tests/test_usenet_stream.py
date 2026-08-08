"""Unit tests for seekable Usenet stream helpers (no NNTP required)."""
from __future__ import annotations

from app.services.usenet_stream import (
    map_range_to_segments,
    parse_nzb,
    yenc_decode,
)


SAMPLE_NZB = """<?xml version="1.0" encoding="utf-8"?>
<nzb xmlns="http://www.newzbin.com/DTD/2003/nzb">
  <file subject="Sample.Movie.2024.mkv">
    <groups><group>alt.binaries.test</group></groups>
    <segments>
      <segment number="1" bytes="100">seg1@example.com</segment>
      <segment number="2" bytes="100">seg2@example.com</segment>
      <segment number="3" bytes="50">seg3@example.com</segment>
    </segments>
  </file>
</nzb>
"""


def test_yenc_decode_simple():
    payload = bytes([0x41 + 42, 0x42 + 42, 0x43 + 42])  # ABC
    raw = b"Subject: x\r\n\r\n=ybegin line=128 size=3 name=x.bin\r\n" + payload + b"\r\n=yend\r\n"
    assert yenc_decode(raw) == b"ABC"


def test_yenc_escape():
    # '=' escaped as =N where N = byte+64 after the -42 rule inversion
    # encoded byte for 0x10: (0x10+42)=0x3a, but if result is '=' (0x3d) it gets escaped
    # Just ensure escaped path runs without crash
    raw = b"=ybegin name=x\r\n=J\r\n=yend\r\n"  # =J → (0x4a-64)=0x0a after unescape, then -42
    out = yenc_decode(raw)
    assert isinstance(out, bytes)


def test_parse_nzb_orders_segments():
    files = parse_nzb(SAMPLE_NZB)
    assert len(files) == 1
    assert files[0].filename.startswith("Sample")
    assert len(files[0].segments) == 3
    assert files[0].total_est() == 250
    assert [s.number for s in files[0].segments] == [1, 2, 3]


def test_map_range_spans_segments():
    nf = parse_nzb(SAMPLE_NZB)[0]
    hits = map_range_to_segments(nf, 50, 180)
    assert len(hits) == 2
    assert hits[0][0].message_id == "seg1@example.com"
    assert hits[0][1:] == (50, 100)
    assert hits[1][0].message_id == "seg2@example.com"
    assert hits[1][1:] == (0, 80)


def test_map_range_empty():
    nf = parse_nzb(SAMPLE_NZB)[0]
    assert map_range_to_segments(nf, 10, 10) == []
    assert map_range_to_segments(nf, 300, 400) == []


def test_status_seekable_flag():
    from app.services.usenet_stream import status
    st = status()
    assert st["seekable"] is True
    assert st["mode"] == "byte_range_yenc"
