"""Post-wizard / first-run bootstrap — zero manual sync for new users.

Runs after the setup wizard completes (and on startup when setup is already
done) so Cardigann defs, Jackett/Prowlarr indexers, quality profiles, and
built-in public indexers are ready without clicking extra buttons.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

log = logging.getLogger(__name__)

_lock = threading.Lock()
_running = False
_last_result: dict[str, Any] = {}


def last_bootstrap_result() -> dict[str, Any]:
    return dict(_last_result)


def bootstrap_after_setup(*, background: bool = True, force_defs: bool = True) -> dict[str, Any]:
    """
    Full "add and go" bootstrap.

    If background=True, returns immediately and runs work in a daemon thread
    (wizard API stays fast). Poll GET /api/setup/bootstrap for status.
    """
    global _running, _last_result
    if background:
        with _lock:
            if _running:
                return {"ok": True, "status": "already_running", **_last_result}
            _running = True
            _last_result = {"status": "running", "steps": {}}

        def _run():
            global _running, _last_result
            try:
                _last_result = _bootstrap_sync(force_defs=force_defs)
            finally:
                with _lock:
                    _running = False

        threading.Thread(target=_run, name="mediaos-bootstrap", daemon=True).start()
        return {"ok": True, "status": "started", "background": True}

    return _bootstrap_sync(force_defs=force_defs)


def _bootstrap_sync(*, force_defs: bool = True) -> dict[str, Any]:
    from app.config import settings
    from app.database import SessionLocal

    steps: dict[str, Any] = {}
    overall_ok = True

    # 1) Cardigann definitions (Jackett YAML pack)
    try:
        from app.services.definition_sync import ensure_seed_definitions, sync_definitions

        if getattr(settings, "cardigann_auto_sync", True):
            seed = ensure_seed_definitions()
            steps["cardigann_seed"] = seed
            # After seed, pull a wider pack (capped lightly so first-run stays quick)
            max_files = int(getattr(settings, "cardigann_sync_max_files", 0) or 0) or 120
            full = sync_definitions(max_files=max_files, force=force_defs)
            steps["cardigann_sync"] = full
        else:
            steps["cardigann_sync"] = {"ok": True, "skipped": True, "reason": "disabled"}
    except Exception as e:
        overall_ok = False
        steps["cardigann_sync"] = {"ok": False, "error": str(e)}
        log.warning("bootstrap cardigann: %s", e)

    # 2) Jackett → local Torznab indexer rows
    try:
        jackett_url = (getattr(settings, "jackett_url", None) or "").strip()
        if jackett_url:
            from app.services.jackett_sync import sync_jackett_indexers

            db = SessionLocal()
            try:
                steps["jackett_sync"] = sync_jackett_indexers(db, enable_new=True)
            finally:
                db.close()
        else:
            steps["jackett_sync"] = {"ok": True, "skipped": True, "reason": "Jackett not configured"}
    except Exception as e:
        overall_ok = False
        steps["jackett_sync"] = {"ok": False, "error": str(e)}
        log.warning("bootstrap jackett: %s", e)

    # 3) Prowlarr indexers (if URL+key set) — import as Torznab rows
    try:
        prow_url = (getattr(settings, "prowlarr_url", None) or "").strip()
        prow_key = (getattr(settings, "prowlarr_api_key", None) or "").strip()
        if prow_url and prow_key:
            from app.services.arr_migrator import sync_prowlarr_indexers

            db = SessionLocal()
            try:
                steps["prowlarr_sync"] = sync_prowlarr_indexers(db, url=prow_url, api_key=prow_key)
            finally:
                db.close()
        else:
            steps["prowlarr_sync"] = {"ok": True, "skipped": True, "reason": "Prowlarr not configured"}
    except Exception as e:
        # Non-fatal — Prowlarr is optional when using Cardigann/builtins
        steps["prowlarr_sync"] = {"ok": False, "error": str(e)}
        log.info("bootstrap prowlarr: %s", e)

    # 4) Quality profiles + converter presets (idempotent)
    try:
        from app.services.quality.store import seed_default_profiles
        from app.services.converter import seed_default_presets

        db = SessionLocal()
        try:
            seed_default_profiles(db)
            try:
                seed_default_presets(db)
            except Exception:
                pass
            steps["profiles"] = {"ok": True}
        finally:
            db.close()
    except Exception as e:
        steps["profiles"] = {"ok": False, "error": str(e)}
        log.warning("bootstrap profiles: %s", e)

    # 5) Ensure Cardigann enabled when defs exist
    try:
        from app.services.cardigann import list_definition_files
        from app.services.app_settings import update_group

        n = len(list_definition_files())
        steps["cardigann_defs_count"] = n
        if n > 0:
            db = SessionLocal()
            try:
                update_group(db, "indexers", {"cardigann_enabled": True})
                steps["cardigann_enabled"] = True
            except Exception as e:
                # group name may differ — force in-process at least
                settings.cardigann_enabled = True
                steps["cardigann_enabled"] = f"runtime:{e}"
            finally:
                db.close()
    except Exception as e:
        log.debug("bootstrap cardigann enable: %s", e)

    # 6) Built-in public indexers are code-backed — just report readiness
    try:
        from app.services.builtin_indexers import list_indexers

        steps["builtin_indexers"] = {
            "ok": True,
            "count": len(list_indexers()),
            "ids": [i.get("id") for i in list_indexers()],
        }
    except Exception as e:
        steps["builtin_indexers"] = {"ok": False, "error": str(e)}


    # 7) TV series_status backfill (continuing/ended) — automatic
    try:
        from app.models import MediaItem, MediaType
        from app.clients.tvdb import tvdb_client

        db2 = SessionLocal()
        try:
            rows = (
                db2.query(MediaItem)
                .filter(MediaItem.media_type == MediaType.tv)
                .limit(200)
                .all()
            )
            updated = 0
            for item in rows:
                try:
                    details = tvdb_client.get_series(int(item.external_id))
                    stv = details.get("series_status")
                    if stv and item.series_status != stv:
                        item.series_status = stv
                        db2.add(item)
                        updated += 1
                except Exception:
                    continue
            if updated:
                db2.commit()
            steps["series_status"] = {"ok": True, "updated": updated, "scanned": len(rows)}
        finally:
            db2.close()
    except Exception as exc:
        steps["series_status"] = {"ok": False, "error": str(exc)}
        log.debug("bootstrap series_status: %s", exc)

    result = {
        "ok": overall_ok,
        "status": "done",
        "steps": steps,
        "message": (
            "Bootstrap complete — search is ready. "
            "Built-in public indexers work immediately; "
            "Jackett/Prowlarr/Cardigann fill in when configured."
        ),
    }
    log.info(
        "bootstrap done ok=%s cardigann=%s jackett=%s prowlarr=%s builtins=%s",
        overall_ok,
        (steps.get("cardigann_sync") or {}).get("ok"),
        (steps.get("jackett_sync") or {}).get("ok"),
        (steps.get("prowlarr_sync") or {}).get("ok"),
        (steps.get("builtin_indexers") or {}).get("count"),
    )
    return result
