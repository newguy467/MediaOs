"""Server-Sent Events bus for live queue/activity/worker updates."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from typing import Any, AsyncIterator


_lock = threading.Lock()
_buffer: deque[dict[str, Any]] = deque(maxlen=200)
_subscribers: list[asyncio.Queue] = []
_seq = 0


def publish(event: str, data: dict[str, Any] | None = None) -> None:
    global _seq
    with _lock:
        _seq += 1
        payload = {
            "id": _seq,
            "event": event,
            "data": data or {},
            "ts": time.time(),
        }
        _buffer.append(payload)
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
        for q in dead:
            try:
                _subscribers.remove(q)
            except ValueError:
                pass


def recent(limit: int = 50) -> list[dict]:
    with _lock:
        return list(_buffer)[-limit:]


async def stream(last_id: int = 0) -> AsyncIterator[str]:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    with _lock:
        _subscribers.append(q)
        backlog = [p for p in _buffer if p["id"] > last_id]
    try:
        for p in backlog:
            yield _format(p)
        while True:
            try:
                p = await asyncio.wait_for(q.get(), timeout=15.0)
                yield _format(p)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        with _lock:
            try:
                _subscribers.remove(q)
            except ValueError:
                pass


def _format(p: dict) -> str:
    return f"id: {p['id']}\nevent: {p['event']}\ndata: {json.dumps(p['data'], default=str)}\n\n"
