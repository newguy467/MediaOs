"""Multi-user account management (admin sets roles + permissions)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import hash_password, require_admin, verify_password
from app.database import get_db
from app.models import User, UserRole

router = APIRouter(prefix="/users", tags=["users"])

# Permission keys an admin can grant
PERMISSION_CATALOG = [
    {"id": "discover.view", "label": "Browse Discover", "group": "Library"},
    {"id": "player.view", "label": "Stream / play media", "group": "Library"},
    {"id": "calendar.view", "label": "View calendar", "group": "Library"},
    {"id": "library.view", "label": "View library", "group": "Library"},
    {"id": "library.manage", "label": "Add / edit / delete library items", "group": "Library"},
    # library.edit and bare "library" are additional aliases some routers
    # check for (games, trakt/mal/anilist/steam import, scrobbling,
    # tracking, quality-file overrides) — granted alongside library.manage
    # so those features are actually reachable by non-admin users.
    {"id": "library.edit", "label": "Edit extended library metadata (games, tracking, imports)", "group": "Library"},
    {"id": "library", "label": "Extended library features (games, tracking, imports)", "group": "Library"},
    {"id": "download", "label": "Search & grab releases", "group": "Downloads"},
    {"id": "queue", "label": "Manage download queue", "group": "Downloads"},
    {"id": "queue.view", "label": "View download queue", "group": "Downloads"},
    {"id": "queue.manage", "label": "Manage download queue (extended)", "group": "Downloads"},
    {"id": "requests", "label": "Submit media requests", "group": "Requests"},
    {"id": "requests.approve", "label": "Approve requests", "group": "Requests"},
    {"id": "converter", "label": "File converter", "group": "Tools"},
    {"id": "converter.view", "label": "View file converter", "group": "Tools"},
    {"id": "converter.manage", "label": "Manage file converter", "group": "Tools"},
    {"id": "settings", "label": "Change settings", "group": "Admin"},
    {"id": "users", "label": "Manage users", "group": "Admin"},
    {"id": "indexers", "label": "Manage indexers", "group": "Admin"},
    {"id": "system.view", "label": "View system dashboard", "group": "Admin"},
]

ROLE_DEFAULTS = {
    "admin": [p["id"] for p in PERMISSION_CATALOG],
    "user": ["library.view", "discover.view", "player.view", "calendar.view", "download", "queue", "requests"],
}


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: str = UserRole.user.value
    permissions: list[str] | None = None


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role: str | None = None
    is_active: bool | None = None
    permissions: list[str] | None = None


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    permissions: list[str]
    created_at: datetime
    last_login_at: datetime | None

    class Config:
        from_attributes = True


def _perms_for(user: User) -> list[str]:
    if user.permissions_json:
        try:
            data = json.loads(user.permissions_json)
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception:
            pass
    return list(ROLE_DEFAULTS.get(user.role, ROLE_DEFAULTS["user"]))


def _to_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
        "permissions": _perms_for(user),
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


@router.get("/permissions/catalog")
def permission_catalog(_: str = Depends(require_admin)):
    return {"permissions": PERMISSION_CATALOG, "role_defaults": ROLE_DEFAULTS}


@router.get("")
def list_users(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    rows = db.query(User).order_by(User.username).all()
    return [_to_out(u) for u in rows]


@router.post("")
def create_user(payload: UserCreate, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    if payload.role not in (UserRole.admin.value, UserRole.user.value):
        raise HTTPException(400, "role must be admin or user")
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(409, "Username taken")
    perms = payload.permissions
    if perms is None:
        perms = ROLE_DEFAULTS.get(payload.role, ROLE_DEFAULTS["user"])
    user = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        permissions_json=json.dumps(perms),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_out(user)


@router.patch("/{user_id}")
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Not found")
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.role is not None:
        if payload.role not in (UserRole.admin.value, UserRole.user.value):
            raise HTTPException(400, "invalid role")
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.permissions is not None:
        user.permissions_json = json.dumps(payload.permissions)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_out(user)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Not found")
    db.delete(user)
    db.commit()
