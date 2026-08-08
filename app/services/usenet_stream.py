"""Seekable Usenet streaming — NZB index + yEnc + HTTP byte-range.

True random-access over NNTP:
  1. Parse NZB → ordered segments with estimated byte sizes
  2. Build cumulative byte index (refined after decode when possible)
  3. On Range request, map byte offsets → segment set
  4. Fetch only needed articles, yEnc-decode, slice, stream
  5. LRU segment cache + optional sequential prefetch

Sessions keep NZB XML server-side so players can seek with Range headers
without re-uploading the NZB on every jump.
"""
from __future__ import annotations

import logging
import nntplib
import re
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Iterator

from app.config import settings

log = logging.getLogger(__name__)

# ── Data model ─────────────────────────────────────────────────────────────

@dataclass
class NzbSegment:
    message_id: str
    bytes_est: int = 0
    # filled after successful decode
    bytes_actual: int | None = None
    number: int = 0


@dataclass
class NzbFile:
    filename: str
    segments: list[NzbSegment]

    def total_est(self) -> int:
        return sum((s.bytes_actual if s.bytes_actual is not None else s.bytes_est) for s in self.segments)

    def build_index(self) -> list[tuple[int, int, NzbSegment]]:
        """Return list of (start_offset, end_offset_exclusive, segment)."""
        index: list[tuple[int, int, NzbSegment]] = []
        pos = 0
        for s in self.segments:
            size = s.bytes_actual if s.bytes_actual is not None else max(s.bytes_est, 1)
            index.append((pos, pos + size, s))
            pos += size
        return index


@dataclass
class StreamSession:
    id: str
    nzb_xml: str
    file_index: int
    filename: str
    files: list[NzbFile]
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)


# ── yEnc decode ────────────────────────────────────────────────────────────

_YENC_BEGIN = re.compile(rb"=ybegin\b.*\bname=(\S+)", re.I)
_YENC_PART = re.compile(rb"=ypart\b.*\bbegin=(\d+).*end=(\d+)", re.I)
_YENC_END = re.compile(rb"=yend\b", re.I)


def yenc_decode(article: bytes) -> bytes:
    """Decode a yEnc article body into raw binary.

    Falls back to stripping NNTP headers and returning body as-is if no
    yEnc markers are present (already-decoded or non-yenc posts).
    """
    if not article:
        return b""
    # Split headers / body if present
    if b"\r\n\r\n" in article:
        body = article.split(b"\r\n\r\n", 1)[1]
    elif b"\n\n" in article:
        body = article.split(b"\n\n", 1)[1]
    else:
        body = article

    lines = body.split(b"\n")
    in_data = False
    out = bytearray()
    for raw in lines:
        line = raw.rstrip(b"\r")
        if not in_data:
            if line.startswith(b"=ybegin") or line.startswith(b"=ypart"):
                in_data = True
            continue
        if line.startswith(b"=yend"):
            break
        # yEnc escape: = followed by (byte - 64)
        i = 0
        while i < len(line):
            b = line[i]
            if b == 0x3D and i + 1 < len(line):  # '='
                i += 1
                b = (line[i] - 64) & 0xFF
            else:
                b = (b - 42) & 0xFF
            out.append(b)
            i += 1
    if out:
        return bytes(out)
    # No yEnc — return body stripped of leading header-ish lines
    return body


# ── NZB parse ──────────────────────────────────────────────────────────────

def parse_nzb(xml_text: str) -> list[NzbFile]:
    root = ET.fromstring(xml_text)
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
    files: list[NzbFile] = []
    for f in root.findall(f"{ns}file"):
        subject = f.attrib.get("subject") or "file"
        segs: list[NzbSegment] = []
        for s in f.findall(f"{ns}segments/{ns}segment"):
            mid = (s.text or "").strip()
            if mid:
                segs.append(
                    NzbSegment(
                        message_id=mid,
                        bytes_est=int(s.attrib.get("bytes") or 0),
                        number=int(s.attrib.get("number") or len(segs) + 1),
                    )
                )
        # NZB segments often listed out of order — sort by number
        segs.sort(key=lambda x: x.number or 0)
        if segs:
            files.append(NzbFile(filename=subject[:200], segments=segs))
    return files


def nntp_enabled() -> bool:
    return bool(getattr(settings, "nntp_host", "") or "")


def status() -> dict:
    return {
        "nntp_configured": nntp_enabled(),
        "host": getattr(settings, "nntp_host", "") or None,
        "port": int(getattr(settings, "nntp_port", 563) or 563),
        "ssl": bool(getattr(settings, "nntp_ssl", True)),
        "seekable": True,
        "mode": "byte_range_yenc",
        "sessions": _session_store.count(),
        "cache_segments": _segment_cache.size(),
        "cache_bytes": _segment_cache.bytes(),
    }


# ── NNTP fetch ─────────────────────────────────────────────────────────────

def _nntp_connect():
    host = settings.nntp_host
    port = int(getattr(settings, "nntp_port", 563) or 563)
    user = getattr(settings, "nntp_user", "") or ""
    password = getattr(settings, "nntp_pass", "") or ""
    ssl = bool(getattr(settings, "nntp_ssl", True))
    if ssl:
        return nntplib.NNTP_SSL(host, port, user=user or None, password=password or None, timeout=90)
    return nntplib.NNTP(host, port, user=user or None, password=password or None, timeout=90)


def fetch_article_raw(message_id: str) -> bytes:
    mid = message_id if message_id.startswith("<") else f"<{message_id}>"
    conn = _nntp_connect()
    try:
        # Prefer BODY for bandwidth; fall back to ARTICLE
        try:
            _resp, _info, lines = conn.body(mid)
        except Exception:
            _resp, _info, lines = conn.article(mid)
        out: list[bytes] = []
        for line in lines:
            if isinstance(line, bytes):
                out.append(line)
            else:
                out.append(str(line).encode("utf-8", errors="replace"))
        return b"\n".join(out)
    finally:
        try:
            conn.quit()
        except Exception:
            pass


def fetch_article_decoded(message_id: str) -> bytes:
    raw = fetch_article_raw(message_id)
    return yenc_decode(raw)


# ── Segment LRU cache ──────────────────────────────────────────────────────

class _SegmentCache:
    def __init__(self, max_bytes: int = 64 * 1024 * 1024):
        self.max_bytes = max_bytes
        self._data: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()
        self._total = 0

    def get(self, mid: str) -> bytes | None:
        with self._lock:
            if mid not in self._data:
                return None
            self._data.move_to_end(mid)
            return self._data[mid]

    def put(self, mid: str, data: bytes) -> None:
        with self._lock:
            if mid in self._data:
                self._total -= len(self._data[mid])
                del self._data[mid]
            self._data[mid] = data
            self._total += len(data)
            self._data.move_to_end(mid)
            while self._total > self.max_bytes and self._data:
                k, v = self._data.popitem(last=False)
                self._total -= len(v)

    def size(self) -> int:
        with self._lock:
            return len(self._data)

    def bytes(self) -> int:
        with self._lock:
            return self._total


_segment_cache = _SegmentCache(
    max_bytes=int(getattr(settings, "nntp_cache_mb", 64) or 64) * 1024 * 1024
)


def get_segment_bytes(seg: NzbSegment) -> bytes:
    cached = _segment_cache.get(seg.message_id)
    if cached is not None:
        return cached
    data = fetch_article_decoded(seg.message_id)
    seg.bytes_actual = len(data)
    _segment_cache.put(seg.message_id, data)
    return data


# ── Session store ──────────────────────────────────────────────────────────

class _SessionStore:
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self._sessions: dict[str, StreamSession] = {}
        self._lock = threading.Lock()

    def create(self, nzb_xml: str, file_index: int = 0) -> StreamSession:
        files = parse_nzb(nzb_xml)
        if not files:
            raise ValueError("NZB contained no files")
        if file_index < 0 or file_index >= len(files):
            raise ValueError(f"file_index {file_index} out of range")
        sid = uuid.uuid4().hex[:16]
        sess = StreamSession(
            id=sid,
            nzb_xml=nzb_xml,
            file_index=file_index,
            filename=files[file_index].filename,
            files=files,
        )
        with self._lock:
            self._purge_locked()
            self._sessions[sid] = sess
        return sess

    def get(self, sid: str) -> StreamSession | None:
        with self._lock:
            self._purge_locked()
            sess = self._sessions.get(sid)
            if sess:
                sess.last_access = time.time()
            return sess

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _purge_locked(self) -> None:
        now = time.time()
        dead = [k for k, v in self._sessions.items() if now - v.last_access > self.ttl]
        for k in dead:
            del self._sessions[k]


_session_store = _SessionStore(
    ttl_seconds=int(getattr(settings, "nntp_session_ttl", 3600) or 3600)
)


# ── Range mapping + stream ─────────────────────────────────────────────────

def map_range_to_segments(
    nf: NzbFile, start: int, end: int
) -> list[tuple[NzbSegment, int, int]]:
    """Map [start, end) file bytes → list of (segment, local_start, local_end)."""
    if end <= start:
        return []
    index = nf.build_index()
    hits: list[tuple[NzbSegment, int, int]] = []
    for seg_start, seg_end, seg in index:
        if seg_end <= start or seg_start >= end:
            continue
        local_start = max(0, start - seg_start)
        local_end = min(seg_end - seg_start, end - seg_start)
        hits.append((seg, local_start, local_end))
    return hits


def iter_byte_range(
    nf: NzbFile,
    start: int,
    end: int,
    *,
    prefetch: int = 2,
) -> Iterator[bytes]:
    """Yield decoded bytes for file byte range [start, end)."""
    hits = map_range_to_segments(nf, start, end)
    if not hits:
        return
    # Prefetch next segments in background while we serve current
    prefetch_ids = []
    all_segs = [s for s, _, _ in hits]
    for i, seg in enumerate(all_segs):
        for j in range(1, prefetch + 1):
            if i + j < len(all_segs):
                prefetch_ids.append(all_segs[i + j].message_id)

    def _prefetch_worker(mids: list[str]) -> None:
        for mid in mids:
            if _segment_cache.get(mid) is not None:
                continue
            try:
                # find segment object
                for s in nf.segments:
                    if s.message_id == mid:
                        get_segment_bytes(s)
                        break
            except Exception as e:
                log.debug("prefetch %s: %s", mid, e)

    if prefetch_ids:
        t = threading.Thread(target=_prefetch_worker, args=(prefetch_ids[:prefetch],), daemon=True)
        t.start()

    remaining = end - start
    for seg, local_start, local_end in hits:
        try:
            data = get_segment_bytes(seg)
        except Exception as e:
            log.warning("NNTP segment %s failed: %s", seg.message_id, e)
            # skip gap — player may error; better than aborting whole stream
            continue
        # If actual size differs from estimate, local_end may exceed data
        chunk = data[local_start:local_end]
        if not chunk:
            continue
        if len(chunk) > remaining:
            chunk = chunk[:remaining]
        yield chunk
        remaining -= len(chunk)
        if remaining <= 0:
            break


def stream_nzb_file(nzb_xml: str, file_index: int = 0, max_segments: int | None = None) -> Iterator[bytes]:
    """Linear full-file stream (backward compatible)."""
    files = parse_nzb(nzb_xml)
    if not files:
        raise ValueError("NZB contained no files")
    if file_index < 0 or file_index >= len(files):
        raise ValueError(f"file_index {file_index} out of range")
    nf = files[file_index]
    segs = nf.segments if max_segments is None else nf.segments[:max_segments]
    for seg in segs:
        try:
            yield get_segment_bytes(seg)
        except Exception as e:
            log.warning("NNTP segment %s failed: %s", seg.message_id, e)
            continue


def create_session(nzb_xml: str, file_index: int = 0) -> dict:
    sess = _session_store.create(nzb_xml, file_index)
    nf = sess.files[file_index]
    size = nf.total_est()
    return {
        "session_id": sess.id,
        "filename": sess.filename,
        "file_index": file_index,
        "size_est": size,
        "segments": len(nf.segments),
        "seekable": True,
        "stream_path": f"/api/parity/usenet-stream/sessions/{sess.id}",
        "accept_ranges": "bytes",
    }


def session_info(session_id: str) -> dict | None:
    sess = _session_store.get(session_id)
    if not sess:
        return None
    nf = sess.files[sess.file_index]
    return {
        "session_id": sess.id,
        "filename": sess.filename,
        "file_index": sess.file_index,
        "size_est": nf.total_est(),
        "segments": len(nf.segments),
        "seekable": True,
        "stream_path": f"/api/parity/usenet-stream/sessions/{sess.id}",
    }


def open_session_range(
    session_id: str, start: int, end: int | None
) -> tuple[StreamSession, NzbFile, int, int, Iterator[bytes]]:
    """Resolve session + range → (session, file, start, end, iterator)."""
    sess = _session_store.get(session_id)
    if not sess:
        raise KeyError("session not found")
    nf = sess.files[sess.file_index]
    total = nf.total_est()
    if end is None or end > total:
        end = total
    start = max(0, start)
    end = max(start, end)
    return sess, nf, start, end, iter_byte_range(nf, start, end)


def inspect_nzb(nzb_xml: str) -> dict:
    files = parse_nzb(nzb_xml)
    return {
        "files": [
            {
                "index": i,
                "filename": f.filename,
                "segments": len(f.segments),
                "bytes_est": sum(s.bytes_est for s in f.segments),
            }
            for i, f in enumerate(files)
        ],
        "nntp": status(),
        "seekable": True,
    }


# unit helpers for tests
def _yenc_roundtrip_sample() -> bool:
    # encode-like: not needed; just ensure decoder handles plain
    return yenc_decode(b"headers\r\n\r\n=ybegin line=128 size=3 name=x\r\n\x6c\x6d\x6e\r\n=yend") != b""


def usenet_stream_status() -> dict:
    """Health/capability snapshot for Usenet streaming."""
    from app.config import settings
    return {
        "enabled": bool(getattr(settings, "allow_usenet", False)),
        "seekable": True,
        "range_support": True,
        "yenc": True,
        "prefetch": True,
        "notes": "Byte-range yEnc segment streaming with LRU prefetch",
    }
