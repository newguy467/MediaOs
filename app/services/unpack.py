"""Unpack archives in download folders (Unpackerr-style) before organize."""
from __future__ import annotations

import logging
import shutil
import subprocess
import zipfile
from pathlib import Path

from app.config import settings

log = logging.getLogger(__name__)

ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".tgz", ".tbz2"}


def _extract_zip(archive: Path, dest: Path) -> bool:
    try:
        dest_resolved = dest.resolve()
        with zipfile.ZipFile(archive, "r") as zf:
            for member in zf.infolist():
                # Zip-slip guard: archive content comes from torrent/usenet
                # downloads (fully untrusted / attacker-controlled), so a
                # crafted entry name like "../../../etc/cron.d/x" must not
                # be able to write outside dest. Resolve and confine each
                # member instead of trusting zf.extractall().
                target = (dest_resolved / member.filename).resolve()
                if target != dest_resolved and dest_resolved not in target.parents:
                    log.warning("Skipping unsafe zip entry in %s: %r", archive, member.filename)
                    continue
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
        return True
    except Exception as exc:
        log.warning("zip extract failed %s: %s", archive, exc)
        return False


def _extract_cmd(archive: Path, dest: Path) -> bool:
    dest.mkdir(parents=True, exist_ok=True)
    suffix = archive.suffix.lower()
    try:
        if suffix == ".rar":
            # unrar x -o+ archive dest/
            cmd = ["unrar", "x", "-o+", str(archive), str(dest) + "/"]
        elif suffix == ".7z":
            cmd = ["7z", "x", f"-o{dest}", "-y", str(archive)]
        elif suffix in {".tar", ".gz", ".tgz", ".bz2", ".tbz2"} or archive.name.endswith(".tar.gz"):
            cmd = ["tar", "-xf", str(archive), "-C", str(dest)]
        else:
            return False
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            log.warning("extract cmd failed %s: %s", archive, r.stderr[:300])
            return False
        return True
    except FileNotFoundError:
        log.debug("extractor binary missing for %s", archive)
        return False
    except Exception as exc:
        log.warning("extract failed %s: %s", archive, exc)
        return False


def unpack_path(content_path: Path) -> int:
    """Extract archives under content_path. Returns number extracted."""
    if not settings.unpack_enabled:
        return 0
    if not content_path.exists():
        return 0
    extracted = 0
    roots = [content_path] if content_path.is_dir() else [content_path.parent]
    archives: list[Path] = []
    for root in roots:
        if content_path.is_file() and content_path.suffix.lower() in ARCHIVE_EXTS:
            archives.append(content_path)
        if root.is_dir():
            for f in root.rglob("*"):
                if f.is_file() and f.suffix.lower() in ARCHIVE_EXTS:
                    archives.append(f)
    for archive in archives:
        dest = archive.parent
        ok = False
        if archive.suffix.lower() == ".zip":
            ok = _extract_zip(archive, dest)
        else:
            ok = _extract_cmd(archive, dest)
        if ok:
            extracted += 1
            log.info("Unpacked %s", archive)
            if settings.unpack_delete_archive:
                try:
                    archive.unlink()
                except OSError:
                    pass
    return extracted
