"""Centralized logging for mediaos — console + rotating files + request IDs."""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import time
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any

# Request-scoped correlation id
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_CONFIGURED = False


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()  # type: ignore[attr-defined]
        return True


class SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = "-"  # type: ignore[attr-defined]
        return super().format(record)


def log_dir() -> Path:
    for candidate in (
        os.environ.get("MEDIAOS_LOG_DIR"),
        "/config/logs",
        "/var/log/mediaos",
        str(Path.cwd() / "logs"),
    ):
        if not candidate:
            continue
        p = Path(candidate)
        try:
            p.mkdir(parents=True, exist_ok=True)
            # write test
            t = p / ".write_test"
            t.write_text("ok")
            t.unlink(missing_ok=True)
            return p
        except Exception:
            continue
    p = Path("/tmp/mediaos-logs")
    p.mkdir(parents=True, exist_ok=True)
    return p


def configure_logging(level: str | None = None) -> Path:
    """Configure root + mediaos loggers. Safe to call once at startup."""
    global _CONFIGURED
    level_name = (level or os.environ.get("LOG_LEVEL") or os.environ.get("MEDIAOS_LOG_LEVEL") or "INFO").upper()
    log_level = getattr(logging, level_name, logging.INFO)
    directory = log_dir()

    if _CONFIGURED:
        return directory

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(log_level)

    fmt = SafeFormatter(
        fmt="%(asctime)s | %(levelname)-7s | %(request_id)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    rid_filter = RequestIdFilter()

    # Console
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(fmt)
    console.addFilter(rid_filter)
    root.addHandler(console)

    # Main rotating app log
    app_path = directory / "mediaos.log"
    app_handler = logging.handlers.RotatingFileHandler(
        app_path, maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8"
    )
    app_handler.setLevel(log_level)
    app_handler.setFormatter(fmt)
    app_handler.addFilter(rid_filter)
    root.addHandler(app_handler)

    # Error-only file
    err_path = directory / "mediaos-error.log"
    err_handler = logging.handlers.RotatingFileHandler(
        err_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    err_handler.setLevel(logging.WARNING)
    err_handler.setFormatter(fmt)
    err_handler.addFilter(rid_filter)
    root.addHandler(err_handler)

    # Access / HTTP log (written by middleware)
    access_path = directory / "mediaos-access.log"
    access_logger = logging.getLogger("mediaos.access")
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False
    access_handler = logging.handlers.RotatingFileHandler(
        access_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    access_handler.setFormatter(SafeFormatter(
        fmt="%(asctime)s | %(levelname)-7s | %(request_id)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    access_handler.addFilter(rid_filter)
    access_logger.handlers.clear()
    access_logger.addHandler(access_handler)
    # also echo access to console at INFO when debug
    if log_level <= logging.DEBUG:
        access_logger.addHandler(console)

    # Quiet noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)

    _CONFIGURED = True
    logging.getLogger("mediaos").info(
        "Logging configured level=%s dir=%s files=mediaos.log,mediaos-error.log,mediaos-access.log",
        level_name,
        directory,
    )
    return directory


def list_log_files() -> list[dict[str, Any]]:
    directory = log_dir()
    out = []
    for p in sorted(directory.glob("mediaos*.log*")):
        try:
            st = p.stat()
            out.append({
                "name": p.name,
                "path": str(p),
                "size": st.st_size,
                "mtime": st.st_mtime,
            })
        except Exception:
            continue
    return out


def tail_log(name: str = "mediaos.log", *, lines: int = 200, level: str | None = None) -> dict[str, Any]:
    """Return last N lines of a log file, optional level filter."""
    directory = log_dir()
    # prevent path traversal
    safe = Path(name).name
    path = directory / safe
    if not path.is_file():
        return {"file": safe, "lines": [], "error": "not found"}
    try:
        # efficient-ish tail
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            block = 8192
            data = b""
            while size > 0 and data.count(b"\n") <= lines:
                step = min(block, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
        text = data.decode("utf-8", errors="replace")
        rows = text.splitlines()[-lines:]
        if level:
            lv = level.upper()
            rows = [r for r in rows if f"| {lv}" in r or f"| {lv:<7}" in r]
        return {"file": safe, "path": str(path), "lines": rows, "count": len(rows)}
    except Exception as e:
        return {"file": safe, "lines": [], "error": str(e)}


def search_log(name: str = "mediaos.log", *, query: str, limit: int = 100) -> dict[str, Any]:
    directory = log_dir()
    safe = Path(name).name
    path = directory / safe
    if not path.is_file():
        return {"file": safe, "matches": [], "error": "not found"}
    q = query.lower()
    matches: list[str] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if q in line.lower():
                    matches.append(line.rstrip("\n"))
                    if len(matches) >= limit:
                        break
        return {"file": safe, "matches": matches[-limit:], "count": len(matches)}
    except Exception as e:
        return {"file": safe, "matches": [], "error": str(e)}
