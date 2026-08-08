"""Session auth API: login, refresh, logout, me, sessions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import try_login, hash_password, require_admin
from app.services.sessions import create_session, list_sessions, refresh_session, resolve_access, revoke, revoke_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/login")
def login(body: LoginIn, request: Request):
    """Issue access + refresh session tokens."""
    result = try_login(body.username, body.password)
    if not result:
        raise HTTPException(401, "Invalid credentials")
    # try_login returns (legacy_token, role)
    _legacy, role = result
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    session = create_session(body.username, role, user_agent=ua, ip=ip)
    # also expose legacy `token` field for older UI
    session["token"] = session["access_token"]
    return session


@router.post("/refresh")
def refresh(body: RefreshIn):
    s = refresh_session(body.refresh_token)
    if not s:
        raise HTTPException(401, "Invalid refresh token")
    return s


@router.post("/logout")
def logout(request: Request):
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        revoke(auth.split(" ", 1)[1].strip())
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    tok = auth.split(" ", 1)[1].strip()
    s = resolve_access(tok)
    if not s:
        raise HTTPException(401, "Session expired")
    return {"username": s["username"], "role": s["role"], "expires_at": s["expires_at"]}


@router.get("/sessions")
def sessions(request: Request):
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    tok = auth.split(" ", 1)[1].strip()
    s = resolve_access(tok)
    if not s:
        raise HTTPException(401, "Session expired")
    # admin sees all
    if s.get("role") == "admin":
        return list_sessions()
    return list_sessions(s["username"])


@router.delete("/sessions/{token_prefix}")
def revoke_session(token_prefix: str, request: Request, _: str = Depends(require_admin)):
    """Revoke a session by access-token prefix (admin or own sessions)."""
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    tok = auth.split(" ", 1)[1].strip()
    s = resolve_access(tok)
    if not s:
        raise HTTPException(401, "Session expired")
    from app.services.sessions import revoke_by_prefix
    ok = revoke_by_prefix(token_prefix, actor=s)
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"ok": True, "revoked_prefix": token_prefix}


@router.post("/sessions/revoke-others")
def revoke_others(request: Request, _: str = Depends(require_admin)):
    """Revoke all sessions for the current user except the active one."""
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    tok = auth.split(" ", 1)[1].strip()
    s = resolve_access(tok)
    if not s:
        raise HTTPException(401, "Session expired")
    from app.services.sessions import revoke_others_for_user
    n = revoke_others_for_user(s["username"], keep_access=tok)
    return {"ok": True, "revoked": n}