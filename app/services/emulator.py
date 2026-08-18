"""Emulator launch: resolve a per-platform command template and run it in the background.

A Platform can carry an `emulator_command` template (e.g.
"retroarch -L /cores/snes9x_libretro.so {rom}") using {rom}/{title}/{id}
placeholders. Launching queues a GameInstallJob(kind="launch") immediately
and runs the resolved command as a real subprocess on a background thread,
mirroring the existing install-job pattern (see games.install_game) but
without blocking the request on however long the emulated session runs.
"""
from __future__ import annotations

import logging
import shlex
import subprocess
import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import Game, GameInstallJob, Platform

log = logging.getLogger("mediaos.emulator")

# Emulator sessions can run for hours — this only bounds a runaway/hung
# process, it isn't a "how long can you play" limit in practice.
_LAUNCH_TIMEOUT_SECONDS = 6 * 60 * 60


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmulatorConfigError(ValueError):
    """Raised when a platform's emulator_command can't be resolved into a runnable command."""


def resolve_emulator_command(template: str, *, rom_path: str, title: str, game_id: int) -> str:
    """Fill a platform's emulator_command template.

    Supported placeholders: {rom} (shlex-quoted rom/install path), {title},
    {id}. Raises EmulatorConfigError on a blank template or an unknown
    placeholder — this never returns a partially-resolved command.
    """
    tmpl = (template or "").strip()
    if not tmpl:
        raise EmulatorConfigError("Platform has no emulator_command configured")
    try:
        return tmpl.format(rom=shlex.quote(rom_path or ""), title=title or "", id=game_id)
    except (KeyError, IndexError) as e:
        raise EmulatorConfigError(f"emulator_command has an unsupported placeholder: {e}") from e


def get_emulator_target(game: Game, platform: Platform | None) -> dict[str, Any] | None:
    """Best-effort emulator launch target for a game, or None if not applicable.

    Used to surface an "emulator" option alongside Steam/install-path/library
    targets — never raises, since an unconfigured or unresolvable template
    just means the target isn't offered.
    """
    if not platform or not (platform.emulator_command or "").strip():
        return None
    rom_path = game.install_path or game.path
    if not rom_path:
        return None
    try:
        command = resolve_emulator_command(
            platform.emulator_command, rom_path=rom_path, title=game.title, game_id=game.id
        )
    except EmulatorConfigError as e:
        log.warning("emulator command unresolvable for game %s: %s", game.id, e)
        return None
    return {"kind": "emulator", "label": f"Launch via {platform.name} emulator", "command": command}


def launch_via_emulator(db: Session, game: Game, platform: Platform) -> GameInstallJob:
    """Queue a background emulator launch, logged as a GameInstallJob(kind="launch").

    Returns the job row (status="running") right away; a background thread
    with its own DB session updates it to done/failed once the process exits
    or fails to start. Raises EmulatorConfigError (no job row created) for
    "no rom path" / "no template" cases — those are caller-fixable, not
    launch failures worth logging as a job.
    """
    rom_path = game.install_path or game.path
    if not rom_path:
        raise EmulatorConfigError("Game has no install_path or path to launch")
    command = resolve_emulator_command(
        platform.emulator_command, rom_path=rom_path, title=game.title, game_id=game.id
    )

    job = GameInstallJob(game_id=game.id, status="running", command=command, kind="launch")
    db.add(job)
    db.commit()
    db.refresh(job)

    threading.Thread(
        target=_run_launch, args=(job.id, command), name=f"emulator-launch-{job.id}", daemon=True
    ).start()
    return job


def _run_launch(job_id: int, command: str) -> None:
    """Background thread body — opens its own DB session, per the livetv_dvr pattern."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(GameInstallJob, job_id)
        if not job:
            return
        try:
            argv = shlex.split(command)
            proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                stdout, stderr = proc.communicate(timeout=_LAUNCH_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
            job.log_text = ((stdout or "") + "\n" + (stderr or ""))[:8000]
            job.returncode = proc.returncode
            job.status = "done" if proc.returncode == 0 else "failed"
        except FileNotFoundError as e:
            job.log_text = f"emulator binary not found: {e}"[:8000]
            job.returncode = None
            job.status = "failed"
        except Exception as e:
            job.log_text = str(e)[:8000]
            job.returncode = None
            job.status = "failed"
        job.finished_at = _utcnow()
        db.add(job)
        db.commit()
    except Exception:
        log.exception("emulator launch job %s crashed updating its own status", job_id)
    finally:
        db.close()
