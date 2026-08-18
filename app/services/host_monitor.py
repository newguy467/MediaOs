"""System Monitor page backend: CPU/memory, disk mounts, SMART, and library
counts (movies/series/episodes/albums/songs/collections).

Honesty notes (read before "fixing" a null field):
- CPU/memory/temperature reflect MediaOS's own container/cgroup view by
  default, not the bare-metal host. If the host's /proc and /sys are bind
  mounted read-only at /host/proc and /host/sys (see the commented block in
  docker-compose.yml), this module switches to reading real host-level
  numbers instead — psutil.PROCFS_PATH for CPU/memory, and a small hwmon
  reader below for temperature (psutil has no override for sysfs). The
  `source` field in the response tells the UI which one it's looking at.
- SMART data requires raw block-device access this container does not have
  by default (see the commented `devices:`/`cap_add:` block). It degrades
  to "unavailable" rather than fabricating a reading.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings

log = logging.getLogger("mediaos.host_monitor")

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is a hard requirement, but degrade gracefully
    psutil = None

HOST_PROC = "/host/proc"
HOST_SYS = "/host/sys"

_host_proc_available = bool(psutil) and os.path.isdir(HOST_PROC)
if _host_proc_available:
    try:
        psutil.PROCFS_PATH = HOST_PROC  # type: ignore[attr-defined]
        log.info("host_monitor: using %s for host-level CPU/memory stats", HOST_PROC)
    except Exception:
        _host_proc_available = False


def library_counts(db: Session) -> dict:
    from app.models import MediaItem, Episode, MusicTrack, Collection, MediaType

    def count(media_type: MediaType) -> int:
        return db.query(func.count(MediaItem.id)).filter(MediaItem.media_type == media_type).scalar() or 0

    return {
        "movies": count(MediaType.movie),
        "series": count(MediaType.tv),
        "episodes": db.query(func.count(Episode.id)).scalar() or 0,
        "albums": count(MediaType.music),
        "songs": db.query(func.count(MusicTrack.id)).scalar() or 0,
        "collections": db.query(func.count(Collection.id)).scalar() or 0,
    }


def _hwmon_temp_c(sys_root: str) -> float | None:
    """Read CPU temp straight from sysfs hwmon, bypassing psutil (which has
    no PROCFS_PATH-style override and always looks at the container's own
    /sys). Works against either the container's own /sys or a bind-mounted
    /host/sys — same file layout either way.
    """
    hwmon_dir = Path(sys_root) / "class" / "hwmon"
    if not hwmon_dir.is_dir():
        return None
    preferred = ("coretemp", "k10temp", "cpu_thermal", "zenpower")
    candidates: list[tuple[int, float]] = []  # (priority, temp)
    try:
        for hwmon in sorted(hwmon_dir.iterdir()):
            name_file = hwmon / "name"
            name = name_file.read_text().strip() if name_file.exists() else ""
            for temp_input in sorted(hwmon.glob("temp*_input")):
                try:
                    millideg = int(temp_input.read_text().strip())
                except (OSError, ValueError):
                    continue
                prio = 0 if name in preferred else 1
                candidates.append((prio, millideg / 1000.0))
    except Exception as exc:
        log.debug("hwmon read failed: %s", exc)
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    return candidates[0][1]


def _cpu_temp_c() -> float | None:
    sys_root = HOST_SYS if os.path.isdir(HOST_SYS) else "/sys"
    temp = _hwmon_temp_c(sys_root)
    if temp is not None:
        return temp
    # Fall back to psutil's own (container-view) reader in case hwmon
    # wasn't found by the direct scan but psutil's platform-specific logic
    # (which also checks /sys/class/thermal) turns something up.
    if not psutil or not hasattr(psutil, "sensors_temperatures"):
        return None
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None
    if not temps:
        return None
    for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
        entries = temps.get(key)
        if entries:
            return entries[0].current
    for entries in temps.values():
        if entries:
            return entries[0].current
    return None


def _cpu_mem() -> dict:
    source = "host" if _host_proc_available else "container"
    if not psutil:
        return {"available": False, "source": source, "cpu_percent": None, "memory_percent": None,
                "memory_used": None, "memory_total": None, "cpu_temp_c": None,
                "last_boot": None}
    try:
        cpu_pct = psutil.cpu_percent(interval=0.2)
        vm = psutil.virtual_memory()
        boot = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc).isoformat()
        return {
            "available": True,
            "source": source,
            "cpu_percent": cpu_pct,
            "memory_percent": vm.percent,
            "memory_used": vm.used,
            "memory_total": vm.total,
            "cpu_temp_c": _cpu_temp_c(),
            "last_boot": boot,
        }
    except Exception as exc:
        log.debug("cpu/mem read failed: %s", exc)
        return {"available": False, "source": source, "cpu_percent": None, "memory_percent": None,
                "memory_used": None, "memory_total": None, "cpu_temp_c": None,
                "last_boot": None}


def _mount_usage() -> list[dict]:
    """Usage for the container's own mounts (root + volume mounts we know about)."""
    rows = []
    seen: dict[tuple[int, int], str] = {}
    candidates = [
        ("/", "/"),
        ("Config", "/config"),
        ("App data", "/app/data"),
    ]
    for label, path in candidates:
        try:
            du = shutil.disk_usage(path)
        except Exception:
            continue
        key = (du.total, du.free)
        if key in seen:
            continue
        seen[key] = label
        rows.append({
            "label": label,
            "path": path,
            "total": du.total,
            "used": du.used,
            "free": du.free,
            "percent": round((du.used / du.total) * 100, 1) if du.total else 0,
        })
    return rows


def _smart_status() -> dict:
    devices = [d.strip() for d in (settings.smart_devices or "").split(",") if d.strip()]
    if not devices:
        return {"configured": False, "reason": "SMART_DEVICES not set", "disks": []}
    smartctl = shutil.which("smartctl")
    if not smartctl:
        return {"configured": True, "reason": "smartctl not installed in this image", "disks": []}
    disks = []
    for dev in devices:
        entry = {"device": dev, "status": "unavailable", "bad_sectors": None, "temp_c": None, "reason": None}
        try:
            out = subprocess.run(
                [smartctl, "-H", "-A", dev],
                capture_output=True, text=True, timeout=10,
            )
            text = out.stdout or ""
            if out.returncode not in (0, 4):  # smartctl returns bitmask; 0/4 are typically fine to parse
                stderr = (out.stderr or "").strip()
                if "permission denied" in stderr.lower() or "operation not permitted" in stderr.lower():
                    entry["reason"] = "permission denied — add `cap_add: [SYS_RAWIO]` to the mediaos service"
                else:
                    entry["reason"] = (stderr or "smartctl error")[:200]
                disks.append(entry)
                continue
            if "PASSED" in text:
                entry["status"] = "OK"
            elif "FAILED" in text:
                entry["status"] = "Problem"
            for line in text.splitlines():
                low = line.lower()
                if "reallocated_sector" in low or "bad sector" in low:
                    parts = line.split()
                    if parts and parts[-1].isdigit():
                        entry["bad_sectors"] = int(parts[-1])
                if "temperature_celsius" in low or "airflow_temperature" in low:
                    parts = line.split()
                    for p in parts:
                        if p.isdigit():
                            entry["temp_c"] = float(p)
                            break
        except FileNotFoundError:
            entry["reason"] = "smartctl not found"
        except PermissionError:
            entry["reason"] = "no permission to read device — add `cap_add: [SYS_RAWIO]` to the mediaos service"
        except Exception as exc:
            entry["reason"] = str(exc)[:200]
        disks.append(entry)
    return {"configured": True, "reason": None, "disks": disks}


def host_monitor() -> dict:
    return {
        "cpu_mem": _cpu_mem(),
        "mounts": _mount_usage(),
        "smart": _smart_status(),
    }
