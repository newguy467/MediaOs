"""Plugin marketplace + runtime registry API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_permission
from app.services import plugins as pluginsvc

router = APIRouter(prefix="/plugins", tags=["plugins"])


class GithubInstall(BaseModel):
    repo: str = Field(..., description="owner/repo or https://github.com/owner/repo")
    ref: str = "main"
    plugin_id: str | None = None
    force: bool = False  # bypass plugin_trusted_owners allowlist


@router.get("")
def list_runtime():
    """Currently registered plugins (core + installed)."""
    return {"plugins": pluginsvc.list_plugins()}


@router.get("/marketplace")
def marketplace():
    """GitHub-backed / bundled catalog with install state."""
    return pluginsvc.marketplace_status()


@router.post("/marketplace/refresh")
def marketplace_refresh(_=Depends(require_permission("settings"))):
    """Re-fetch remote catalog (if plugin_registry_url set) and return status."""
    # fetch_catalog always hits remote when configured; status rebuilds view
    return pluginsvc.marketplace_status()


@router.post("/marketplace/{plugin_id}/install")
def marketplace_install(
    plugin_id: str,
    _=Depends(require_permission("settings")),
):
    try:
        return pluginsvc.install_from_catalog(plugin_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Install failed: {e}") from e


@router.post("/install/github")
def install_github(
    body: GithubInstall,
    _=Depends(require_permission("settings")),
):
    try:
        return pluginsvc.install_from_github(body.repo, body.ref or "main", body.plugin_id, force=body.force)
    except Exception as e:
        raise HTTPException(502, f"GitHub install failed: {e}") from e


@router.delete("/{plugin_id}")
def uninstall(
    plugin_id: str,
    _=Depends(require_permission("settings")),
):
    if plugin_id.startswith("core."):
        raise HTTPException(400, "Cannot uninstall core plugins")
    return pluginsvc.uninstall_plugin(plugin_id)


@router.post("/marketplace/{plugin_id}/reinstall")
def marketplace_reinstall(
    plugin_id: str,
    _=Depends(require_permission("settings")),
):
    try:
        return pluginsvc.reinstall_plugin(plugin_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Reinstall failed: {e}") from e


class PluginEnabledBody(BaseModel):
    enabled: bool = True


@router.post("/{plugin_id}/enable")
def plugin_enable(
    plugin_id: str,
    _=Depends(require_permission("settings")),
):
    try:
        return pluginsvc.set_plugin_enabled(plugin_id, True)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/{plugin_id}/disable")
def plugin_disable(
    plugin_id: str,
    _=Depends(require_permission("settings")),
):
    try:
        return pluginsvc.set_plugin_enabled(plugin_id, False)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
