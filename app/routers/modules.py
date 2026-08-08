"""Module Store + enabled-modules API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database import get_db
from app.services import modules as modsvc

router = APIRouter(prefix="/modules", tags=["modules"])


class ModulesUpdate(BaseModel):
    enabled: list[str] = Field(default_factory=list)


class ModuleToggle(BaseModel):
    enabled: bool = True


@router.get("")
def list_modules(db: Session = Depends(get_db)):
    """Catalog + current enabled state (for Module Store and sidebar)."""
    return modsvc.status(db)


@router.get("/enabled")
def enabled_only(db: Session = Depends(get_db)):
    return {"enabled": modsvc.get_enabled(db)}


@router.put("")
def replace_enabled(
    body: ModulesUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("settings")),
):
    enabled = modsvc.set_enabled(db, body.enabled)
    return {"ok": True, "enabled": enabled}


@router.post("/{module_id}/enable")
def enable_one(
    module_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("settings")),
):
    enabled = modsvc.enable_module(db, module_id)
    return {"ok": True, "enabled": enabled}


@router.post("/{module_id}/disable")
def disable_one(
    module_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("settings")),
):
    enabled = modsvc.disable_module(db, module_id)
    return {"ok": True, "enabled": enabled}
