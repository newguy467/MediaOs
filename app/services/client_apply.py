"""One-shot download client Apply — categories + paths (Hubstarr-inspired)."""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings

log = logging.getLogger("mediaos.client_apply")

DEFAULT_CATEGORIES = {
    "movies": "radarr",
    "tv": "tv-sonarr",
    "music": "lidarr",
    "books": "books",
    "general": "mediaos",
}


def planned_categories(overrides: dict[str, str] | None = None) -> dict[str, str]:
    cats = dict(DEFAULT_CATEGORIES)
    if overrides:
        cats.update({k: str(v) for k, v in overrides.items() if v})
    return cats


def apply_clients(
    *,
    qbit_url: str | None = None,
    qbit_user: str | None = None,
    qbit_pass: str | None = None,
    sab_url: str | None = None,
    sab_api_key: str | None = None,
    categories: dict[str, str] | None = None,
    push_qb_categories: bool = True,
) -> dict[str, Any]:
    """
    Persist preferred categories into process settings where possible and
    optionally create qBittorrent categories via API.
    """
    cats = planned_categories(categories)
    report: dict[str, Any] = {"categories": cats, "qb": None, "sab": None, "settings_touched": []}

    # Touch in-memory settings (env-backed deployments still need .env for restart persistence)
    try:
        if qbit_url:
            settings.qbit_url = qbit_url
            report["settings_touched"].append("qbit_url")
        if sab_url:
            settings.sabnzbd_url = sab_url
            report["settings_touched"].append("sabnzbd_url")
        if sab_api_key:
            settings.sabnzbd_api_key = sab_api_key
            report["settings_touched"].append("sabnzbd_api_key")
        if cats.get("general"):
            settings.sabnzbd_category = cats["general"]
            report["settings_touched"].append("sabnzbd_category")
    except Exception as e:
        report["settings_error"] = str(e)

    if push_qb_categories:
        report["qb"] = _push_qb_categories(
            url=(qbit_url or settings.qbit_url or "").rstrip("/"),
            user=qbit_user or getattr(settings, "qbit_username", "") or getattr(settings, "qbit_user", "") or "",
            password=qbit_pass or getattr(settings, "qbit_password", "") or "",
            categories=cats,
        )
    if (sab_url or settings.sabnzbd_url) and (sab_api_key or settings.sabnzbd_api_key):
        report["sab"] = {
            "ok": True,
            "note": "SABnzbd categories are usually created on first use; API key retained in settings.",
            "category": cats.get("general") or settings.sabnzbd_category,
        }
    report["ok"] = True
    return report


def _push_qb_categories(url: str, user: str, password: str, categories: dict[str, str]) -> dict[str, Any]:
    if not url:
        return {"ok": False, "error": "qbit_url empty"}
    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx missing"}
    created = []
    errors = []
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            # login
            r = client.post(f"{url}/api/v2/auth/login", data={"username": user, "password": password})
            if r.status_code >= 400 and user:
                return {"ok": False, "error": f"qB login HTTP {r.status_code}"}
            for name in sorted(set(categories.values())):
                if not name:
                    continue
                rr = client.post(f"{url}/api/v2/torrents/createCategory", data={"category": name, "savePath": ""})
                # 409-ish / already exists is fine
                if rr.status_code < 400 or "already" in (rr.text or "").lower():
                    created.append(name)
                else:
                    errors.append({"category": name, "status": rr.status_code, "body": (rr.text or "")[:200]})
        return {"ok": not errors, "created": created, "errors": errors}
    except Exception as e:
        log.warning("qB category push failed: %s", e)
        return {"ok": False, "error": str(e), "created": created}
