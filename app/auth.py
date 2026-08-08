"""Authentication: Basic, API key, bearer token, and DB multi-user accounts.

Priority when credentials are configured:
1. X-API-Key header matching AUTH_API_KEY
2. Authorization: Bearer <token> from POST /api/auth/login
3. HTTP Basic (env AUTH_USERNAME/PASSWORD or DB user)

Auth is enabled if any of: AUTH_USERNAME, AUTH_API_KEY, or at least one DB user.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
)

from app.config import settings

_security_basic = HTTPBasic(auto_error=False)
_security_bearer = HTTPBearer(auto_error=False)

# token -> (username, expires_at, role)
_tokens: dict[str, tuple[str, float, str]] = {}
_TOKEN_TTL_SEC = 60 * 60 * 24 * 7  # 7 days

# Prefer sessions service when available
def _issue_token(username: str, role: str = "user", **kw):
    try:
        from app.services.sessions import create_session
        return create_session(username, role, **kw)
    except Exception:
        tok = secrets.token_urlsafe(32)
        _tokens[tok] = (username, time.time() + _TOKEN_TTL_SEC, role)
        return {"access_token": tok, "token_type": "Bearer", "expires_in": _TOKEN_TTL_SEC, "username": username, "role": role}


_PBKDF2_ITER = 120_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _PBKDF2_ITER
    ).hex()
    return f"pbkdf2_sha256${_PBKDF2_ITER}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters_s, salt, digest = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        check = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), iters
        ).hex()
        return hmac.compare_digest(check, digest)
    except Exception:
        return False


def _db_user_count() -> int:
    try:
        from app.database import SessionLocal
        from app.models import User

        db = SessionLocal()
        try:
            return db.query(User).filter(User.is_active.is_(True)).count()
        finally:
            db.close()
    except Exception:
        return 0


def _auth_enabled() -> bool:
    return bool(
        (settings.auth_username or "").strip()
        or (settings.auth_api_key or "").strip()
        or _db_user_count() > 0
    )


def create_token(username: str, role: str = "admin") -> str:
    token = secrets.token_urlsafe(32)
    _tokens[token] = (username, time.time() + _TOKEN_TTL_SEC, role)
    if len(_tokens) > 500:
        now = time.time()
        for k, (_, exp, _) in list(_tokens.items()):
            if exp < now:
                _tokens.pop(k, None)
    return token


def revoke_token(token: str) -> None:
    _tokens.pop(token, None)


def _valid_token(token: str):
    try:
        from app.services.sessions import resolve_access
        s = resolve_access(token)
        if s:
            return s["username"], s["role"]
    except Exception:
        pass
    return _valid_token_legacy(token)


def _valid_token_legacy(token: str) -> tuple[str, str] | None:
    row = _tokens.get(token)
    if not row:
        return None
    user, exp, role = row
    if exp < time.time():
        _tokens.pop(token, None)
        return None
    return user, role


def _check_env_basic(credentials: HTTPBasicCredentials | None) -> str | None:
    user = (settings.auth_username or "").strip()
    pw = (settings.auth_password or "").strip()
    if not user or credentials is None:
        return None
    if secrets.compare_digest(credentials.username, user) and secrets.compare_digest(
        credentials.password, pw
    ):
        return credentials.username
    return None


def _check_db_user(username: str, password: str) -> tuple[str, str] | None:
    """Return (username, role) if valid DB user."""
    try:
        from datetime import datetime, timezone

        from app.database import SessionLocal
        from app.models import User

        db = SessionLocal()
        try:
            row = (
                db.query(User)
                .filter(User.username == username, User.is_active.is_(True))
                .first()
            )
            if not row or not verify_password(password, row.password_hash):
                return None
            row.last_login_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            return row.username, row.role
        finally:
            db.close()
    except Exception:
        return None


def _check_api_key(api_key: str | None) -> str | None:
    expected = (settings.auth_api_key or "").strip()
    if not expected or not api_key:
        return None
    if hmac.compare_digest(api_key.strip(), expected):
        return "api-key"
    return None


def require_auth(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_security_basic)] = None,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(_security_bearer)] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str | None:
    if not _auth_enabled():
        return None

    who = _check_api_key(x_api_key)
    if who:
        return who

    if bearer and bearer.credentials:
        got = _valid_token(bearer.credentials)
        if got:
            return got[0]

    if credentials is not None:
        env = _check_env_basic(credentials)
        if env:
            return env
        db = _check_db_user(credentials.username, credentials.password)
        if db:
            return db[0]

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Basic"},
    )


def try_login(username: str, password: str) -> tuple[str, str] | None:
    """Return (token, role) or None."""
    # env admin
    env_user = (settings.auth_username or "").strip()
    env_pw = (settings.auth_password or "").strip()
    if env_user and secrets.compare_digest(username, env_user) and secrets.compare_digest(
        password, env_pw
    ):
        return create_token(username, "admin"), "admin"

    db = _check_db_user(username, password)
    if db:
        return create_token(db[0], db[1]), db[1]
    return None



def get_current_role(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_security_basic)] = None,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(_security_bearer)] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str | None:
    """Return role string or None when auth disabled."""
    if not _auth_enabled():
        return "admin"  # open mode → treat as admin

    if _check_api_key(x_api_key):
        return "admin"

    if bearer and bearer.credentials:
        got = _valid_token(bearer.credentials)
        if got:
            return got[1]

    if credentials is not None:
        if _check_env_basic(credentials):
            return "admin"
        db = _check_db_user(credentials.username, credentials.password)
        if db:
            return db[1]

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Basic"},
    )


def require_admin(role: Annotated[str | None, Depends(get_current_role)] = None) -> str:
    if role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return role or "admin"


# Permission keys (must match app.routers.users.PERMISSION_CATALOG ids)
def get_current_permissions(
    role: Annotated[str | None, Depends(get_current_role)] = None,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(_security_bearer)] = None,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_security_basic)] = None,
) -> list[str]:
    """Resolve permission list for the current principal."""
    if not _auth_enabled():
        return ["*"]  # open install
    if role == "admin":
        return ["*"]
    # Load from DB user when possible
    username = None
    if bearer and bearer.credentials:
        got = _valid_token(bearer.credentials)
        if got:
            username = got[0]
    if not username and credentials is not None:
        username = credentials.username
    if username:
        try:
            from app.database import SessionLocal
            from app.models import User
            import json
            db = SessionLocal()
            try:
                u = db.query(User).filter(User.username == username).first()
                if u and u.permissions_json:
                    data = json.loads(u.permissions_json)
                    if isinstance(data, list):
                        return [str(x) for x in data]
                if u and u.role == "admin":
                    return ["*"]
            finally:
                db.close()
        except Exception:
            pass
    # Default user grants
    return ["library.view", "discover.view", "player.view", "calendar.view", "download", "queue", "requests"]


def require_permission(*needed: str):
    """FastAPI dependency factory: require any of the listed permission keys (or admin *)."""

    def _dep(perms: Annotated[list[str], Depends(get_current_permissions)] = None) -> list[str]:
        perms = perms or []
        if "*" in perms:
            return perms
        if not needed:
            return perms
        if any(p in perms for p in needed):
            return perms
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission (need one of: {', '.join(needed)})",
        )

    return _dep
