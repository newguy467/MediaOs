"""Games emulator launch: Platform.emulator_command template + GameInstallJob(kind="launch").

Unit-level tests exercise app.services.emulator directly (real subprocesses,
no mocks). Route-level tests go through the FastAPI test client to cover
PATCH /platforms/{id}, POST /launch, and POST /launch/emulator end to end.
"""
from __future__ import annotations

import time

import pytest

from app.services.emulator import (
    EmulatorConfigError,
    get_emulator_target,
    launch_via_emulator,
    resolve_emulator_command,
)


# --------------------------------------------------------------------------
# resolve_emulator_command — pure function, no DB
# --------------------------------------------------------------------------

def test_resolve_emulator_command_happy_path():
    cmd = resolve_emulator_command(
        "retroarch -L /cores/snes9x_libretro.so {rom}",
        rom_path="/games/roms/Chrono Trigger.sfc",
        title="Chrono Trigger",
        game_id=42,
    )
    assert cmd == "retroarch -L /cores/snes9x_libretro.so '/games/roms/Chrono Trigger.sfc'"


def test_resolve_emulator_command_all_placeholders():
    cmd = resolve_emulator_command(
        "launcher --title={title} --id={id} --rom={rom}",
        rom_path="/games/a.rom",
        title="Some Game",
        game_id=7,
    )
    assert cmd == "launcher --title=Some Game --id=7 --rom=/games/a.rom"


def test_resolve_emulator_command_shell_metachars_are_quoted():
    """A rom path with shell metacharacters must come out shlex-quoted, not raw."""
    cmd = resolve_emulator_command(
        "run {rom}", rom_path="/games/a;rm -rf b", title="x", game_id=1
    )
    assert "'/games/a;rm -rf b'" in cmd
    assert "; rm -rf b" not in cmd.replace("'", "")  # only inside the quoted literal


def test_resolve_emulator_command_blank_template_raises():
    with pytest.raises(EmulatorConfigError):
        resolve_emulator_command("   ", rom_path="/x", title="x", game_id=1)


def test_resolve_emulator_command_bad_placeholder_raises():
    with pytest.raises(EmulatorConfigError):
        resolve_emulator_command("run {nonexistent}", rom_path="/x", title="x", game_id=1)


# --------------------------------------------------------------------------
# get_emulator_target — never raises, just returns None when not applicable
# --------------------------------------------------------------------------

def test_get_emulator_target_none_without_platform():
    from app.models import Game

    g = Game(title="No Platform", install_path="/games/x")
    assert get_emulator_target(g, None) is None


def test_get_emulator_target_none_without_template():
    from app.models import Game, Platform

    g = Game(title="No Template", install_path="/games/x")
    p = Platform(name="PC", slug="pc-no-tmpl")
    assert get_emulator_target(g, p) is None


def test_get_emulator_target_none_without_rom_path():
    from app.models import Game, Platform

    g = Game(title="No Path")
    p = Platform(name="SNES", slug="snes-no-path", emulator_command="retroarch {rom}")
    assert get_emulator_target(g, p) is None


def test_get_emulator_target_present_when_configured():
    from app.models import Game, Platform

    g = Game(id=99, title="Configured", install_path="/games/x.sfc")
    p = Platform(name="SNES", slug="snes-ok", emulator_command="retroarch {rom}")
    target = get_emulator_target(g, p)
    assert target is not None
    assert target["kind"] == "emulator"
    assert "/games/x.sfc" in target["command"]


# --------------------------------------------------------------------------
# launch_via_emulator — real subprocess execution via a background thread
# --------------------------------------------------------------------------

def _wait_for_status(db, job_id, timeout=5.0):
    from app.models import GameInstallJob

    deadline = time.time() + timeout
    while time.time() < deadline:
        db.expire_all()
        job = db.get(GameInstallJob, job_id)
        if job and job.status in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


def test_launch_via_emulator_happy_path(db):
    from app.models import Game, Platform

    platform = Platform(name="Echo Test", slug=f"echo-{int(time.time() * 1000)}", emulator_command="echo launching {title}")
    db.add(platform)
    db.commit()
    db.refresh(platform)

    game = Game(title="Real Subprocess Game", platform_id=platform.id, install_path="/tmp/does-not-need-to-exist")
    db.add(game)
    db.commit()
    db.refresh(game)

    job = launch_via_emulator(db, game, platform)
    assert job.status == "running"
    assert job.kind == "launch"

    finished = _wait_for_status(db, job.id)
    assert finished.status == "done"
    assert finished.returncode == 0
    assert "launching Real Subprocess Game" in (finished.log_text or "")


def test_launch_via_emulator_missing_binary(db):
    from app.models import Game, Platform

    platform = Platform(
        name="Bad Binary",
        slug=f"bad-binary-{int(time.time() * 1000)}",
        emulator_command="this-binary-does-not-exist-xyz {rom}",
    )
    db.add(platform)
    db.commit()
    db.refresh(platform)

    game = Game(title="Bad Binary Game", platform_id=platform.id, install_path="/tmp/rom.bin")
    db.add(game)
    db.commit()
    db.refresh(game)

    job = launch_via_emulator(db, game, platform)
    finished = _wait_for_status(db, job.id)
    assert finished.status == "failed"
    assert "not found" in (finished.log_text or "")


def test_launch_via_emulator_no_rom_path_is_noop(db):
    """No install_path/path — this must not create a job row at all."""
    from app.models import Game, GameInstallJob, Platform

    platform = Platform(name="No Rom", slug=f"no-rom-{int(time.time() * 1000)}", emulator_command="echo {rom}")
    db.add(platform)
    db.commit()
    db.refresh(platform)

    game = Game(title="No Rom Path", platform_id=platform.id)
    db.add(game)
    db.commit()
    db.refresh(game)

    before = db.query(GameInstallJob).filter(GameInstallJob.game_id == game.id).count()
    with pytest.raises(EmulatorConfigError):
        launch_via_emulator(db, game, platform)
    after = db.query(GameInstallJob).filter(GameInstallJob.game_id == game.id).count()
    assert after == before


# --------------------------------------------------------------------------
# Route-level: PATCH /platforms/{id}, POST /launch, POST /launch/emulator
# --------------------------------------------------------------------------

def test_patch_platform_sets_emulator_command(client, db):
    from app.models import Platform

    p = Platform(name="Route Platform", slug=f"route-plat-{int(time.time() * 1000)}")
    db.add(p)
    db.commit()
    db.refresh(p)

    r = client.patch(f"/api/games/platforms/{p.id}", json={"emulator_command": "retroarch {rom}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["emulator_command"] == "retroarch {rom}"

    db.expire_all()
    refreshed = db.get(Platform, p.id)
    assert refreshed.emulator_command == "retroarch {rom}"


def test_patch_platform_404_for_missing_platform(client):
    r = client.patch("/api/games/platforms/999999999", json={"emulator_command": "x"})
    assert r.status_code == 404


def test_list_platforms_includes_emulator_command(client, db):
    from app.models import Platform

    p = Platform(
        name="Listed Platform",
        slug=f"listed-plat-{int(time.time() * 1000)}",
        emulator_command="mame {rom}",
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    r = client.get("/api/games/platforms/list")
    assert r.status_code == 200
    rows = r.json()
    match = next((row for row in rows if row["id"] == p.id), None)
    assert match is not None
    assert match["emulator_command"] == "mame {rom}"


def test_launch_endpoint_surfaces_emulator_target(client, db):
    from app.models import Game, Platform

    p = Platform(
        name="Surfacing Platform",
        slug=f"surf-plat-{int(time.time() * 1000)}",
        emulator_command="echo {rom}",
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    g = Game(title="Surfaced Game", platform_id=p.id, install_path="/tmp/surface.rom")
    db.add(g)
    db.commit()
    db.refresh(g)

    r = client.post(f"/api/games/{g.id}/launch")
    assert r.status_code == 200, r.text
    body = r.json()
    kinds = [t["kind"] for t in body["targets"]]
    assert "emulator" in kinds


def test_launch_emulator_endpoint_runs_job(client, db):
    from app.models import Game, Platform

    p = Platform(
        name="Execute Platform",
        slug=f"exec-plat-{int(time.time() * 1000)}",
        emulator_command="echo running {title}",
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    g = Game(title="Execute Game", platform_id=p.id, install_path="/tmp/execute.rom")
    db.add(g)
    db.commit()
    db.refresh(g)

    r = client.post(f"/api/games/{g.id}/launch/emulator")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    job_id = body["job_id"]

    finished = _wait_for_status(db, job_id)
    assert finished.status == "done"
    assert finished.kind == "launch"


def test_launch_emulator_endpoint_400_when_unconfigured(client, db):
    from app.models import Game, Platform

    p = Platform(name="Unconfigured Platform", slug=f"unconf-plat-{int(time.time() * 1000)}")
    db.add(p)
    db.commit()
    db.refresh(p)

    g = Game(title="Unconfigured Game", platform_id=p.id, install_path="/tmp/x.rom")
    db.add(g)
    db.commit()
    db.refresh(g)

    r = client.post(f"/api/games/{g.id}/launch/emulator")
    assert r.status_code == 400


def test_install_job_serialization_includes_kind(client, db):
    from app.models import Game, GameInstallJob, Platform

    p = Platform(name="Serialize Platform", slug=f"ser-plat-{int(time.time() * 1000)}")
    db.add(p)
    db.commit()
    db.refresh(p)

    g = Game(title="Serialize Game", platform_id=p.id)
    db.add(g)
    db.commit()
    db.refresh(g)

    job = GameInstallJob(game_id=g.id, status="done", command="echo x", kind="launch")
    db.add(job)
    db.commit()
    db.refresh(job)

    r = client.get(f"/api/games/install-jobs/{job.id}")
    assert r.status_code == 200
    assert r.json()["kind"] == "launch"

    r2 = client.get("/api/games/install-jobs")
    assert r2.status_code == 200
    match = next((row for row in r2.json()["items"] if row["id"] == job.id), None)
    assert match is not None
    assert match["kind"] == "launch"
