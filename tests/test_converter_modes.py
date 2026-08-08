"""Converter output modes + schedule helpers."""
from pathlib import Path
from unittest.mock import MagicMock

from app.services.converter import (
    _finalize_output,
    _fmt_bytes,
    within_convert_schedule,
)


class _Preset:
    def __init__(self, mode="new_file", container="mp4", suffix=".converted", backup=".original"):
        self.output_mode = mode
        self.container = container
        self.output_suffix = suffix
        self.backup_suffix = backup


def test_fmt_bytes():
    assert "B" in _fmt_bytes(100)
    assert "KB" in _fmt_bytes(2048) or "MB" in _fmt_bytes(2_000_000)


def test_finalize_new_file(tmp_path):
    src = tmp_path / "movie.mkv"
    src.write_bytes(b"x" * 10)
    staged = tmp_path / "movie.converted.mp4"
    staged.write_bytes(b"y" * 5)
    job = MagicMock(source_path=str(src))
    final = _finalize_output(job, _Preset("new_file"), staged)
    assert Path(final).exists()
    assert src.exists()


def test_finalize_replace(tmp_path):
    src = tmp_path / "movie.mkv"
    src.write_bytes(b"x" * 10)
    staged = tmp_path / "movie.mediaos-tmp.mp4"
    staged.write_bytes(b"y" * 5)
    job = MagicMock(source_path=str(src))
    final = _finalize_output(job, _Preset("replace", container="mp4"), staged)
    assert Path(final).exists()
    assert not src.exists() or Path(final) == src.with_suffix(".mp4")


def test_finalize_rename_old(tmp_path):
    src = tmp_path / "movie.mkv"
    src.write_bytes(b"x" * 10)
    staged = tmp_path / "movie.mediaos-tmp.mp4"
    staged.write_bytes(b"y" * 5)
    job = MagicMock(source_path=str(src))
    final = _finalize_output(job, _Preset("rename_old", container="mp4"), staged)
    assert Path(final).exists()
    # original renamed
    bak = list(tmp_path.glob("movie.original*"))
    assert bak or not src.exists()


def test_schedule_always_when_unset(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "converter_schedule_start_hour", None, raising=False)
    monkeypatch.setattr(settings, "converter_schedule_end_hour", None, raising=False)
    assert within_convert_schedule() is True
