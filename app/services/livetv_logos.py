"""Live TV channel logo pack import and matching."""
from __future__ import annotations

import logging
import re
import shutil
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import LiveTvChannel
from app.services.activity import log_activity
from app.services.sse import publish as sse_publish

log = logging.getLogger(__name__)

_LOGO_ROOTS = (
    Path("/app/data/channel-logos"),
    Path("data/channel-logos"),
    Path("/tmp/mediaos-channel-logos"),
)


def logo_root() -> Path:
    for p in _LOGO_ROOTS:
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            continue
    p = Path("/tmp/mediaos-channel-logos")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s


def index_logos() -> list[dict]:
    root = logo_root()
    out = []
    for p in root.rglob("*"):
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}:
            continue
        out.append({
            "path": str(p),
            "rel": str(p.relative_to(root)),
            "stem": p.stem.lower(),
            "slug": _slug(p.stem),
        })
    return out


def import_logo_pack(source: Path | str) -> dict:
    """
    Import a logo pack from:
      - a .zip of images (optionally nested by country)
      - a directory of images
    Files land under logo_root().
    """
    src = Path(source)
    root = logo_root()
    imported = 0
    if src.is_file() and src.suffix.lower() == ".zip":
        with zipfile.ZipFile(src, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = Path(info.filename).name
                if Path(name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}:
                    continue
                # preserve one parent folder if present (country)
                parts = Path(info.filename).parts
                rel = Path(parts[-2]) / name if len(parts) >= 2 else Path(name)
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src_f, open(dest, "wb") as out_f:
                    shutil.copyfileobj(src_f, out_f)
                imported += 1
    elif src.is_dir():
        for p in src.rglob("*"):
            if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}:
                continue
            rel = p.relative_to(src)
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
            imported += 1
    else:
        return {"ok": False, "error": f"Not a zip or directory: {src}", "imported": 0}

    return {"ok": True, "imported": imported, "root": str(root), "indexed": len(index_logos())}


def match_logos_to_channels(db: Session, *, overwrite: bool = False) -> dict:
    """Assign logo paths to LiveTvChannel rows by fuzzy name/slug match."""
    logos = index_logos()
    if not logos:
        return {"ok": True, "matched": 0, "channels": 0, "logos": 0}

    by_slug = {L["slug"]: L for L in logos}
    by_stem = {L["stem"]: L for L in logos}

    channels = db.query(LiveTvChannel).all()
    matched = 0
    for ch in channels:
        if ch.logo and not overwrite:
            continue
        name = ch.name or ""
        slug = _slug(name)
        hit = by_slug.get(slug) or by_stem.get(name.lower())
        if not hit:
            # partial: logo slug contained in channel slug or vice versa
            for L in logos:
                if L["slug"] and (L["slug"] in slug or slug in L["slug"]):
                    hit = L
                    break
        if hit:
            # Store path usable by UI; prefer /api/livetv/logos/... later
            ch.logo = f"/api/livetv/logos/{hit['rel']}"
            db.add(ch)
            matched += 1
    db.commit()
    log_activity(db, "livetv_logos", f"Matched {matched}/{len(channels)} channel logos")
    try:
        sse_publish("livetv", {"matched": matched, "channels": len(channels)})
    except Exception:
        pass
    return {"ok": True, "matched": matched, "channels": len(channels), "logos": len(logos)}


def install_remote_logos(db: Session, *, limit: int = 500, timeout: float = 12.0) -> dict:
    """Download http(s) tvg-logo URLs already stored on channels into logo_root and rewrite paths.

    Many M3U playlists (iptv-org, Samsung FAST packs) already include tvg-logo.
    This caches them locally so the UI does not depend on third-party hosts at play time.
    """
    import httpx
    from urllib.parse import urlparse

    root = logo_root()
    channels = db.query(LiveTvChannel).limit(limit * 2).all()
    downloaded = 0
    skipped = 0
    failed = 0
    for ch in channels:
        logo = (ch.logo or "").strip()
        if not logo:
            skipped += 1
            continue
        if logo.startswith("/api/livetv/logos/"):
            skipped += 1
            continue
        if not logo.startswith("http://") and not logo.startswith("https://"):
            skipped += 1
            continue
        if downloaded >= limit:
            break
        try:
            path = urlparse(logo).path or ""
            ext = Path(path).suffix.lower()
            if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
                ext = ".png"
            fname = f"{_slug(ch.name or ch.tvg_id or str(ch.id)) or 'ch-'+str(ch.id)}{ext}"
            dest = root / "remote" / fname
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.stat().st_size > 0:
                ch.logo = f"/api/livetv/logos/remote/{fname}"
                db.add(ch)
                downloaded += 1
                continue
            with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "MediaOs/4.7.2"}) as client:
                r = client.get(logo)
                if r.status_code >= 400 or not r.content:
                    failed += 1
                    continue
                dest.write_bytes(r.content)
            ch.logo = f"/api/livetv/logos/remote/{fname}"
            db.add(ch)
            downloaded += 1
        except Exception as e:
            log.debug("logo download failed %s: %s", ch.name, e)
            failed += 1
    db.commit()
    try:
        log_activity(db, "livetv_logos", f"Installed {downloaded} remote logos")
    except Exception:
        pass
    return {
        "ok": True,
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "root": str(root),
    }
