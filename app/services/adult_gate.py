"""Passcode gate for the Adult (Whisparr-style) module.

Flow:
1. Admin sets a passcode via Settings → Adult (stored as PBKDF2 hash).
2. Client POSTs /api/adult/unlock with the passcode → receives a short-lived unlock token.
3. Subsequent /api/adult/* calls must send header X-Adult-Unlock: <token>.
4. Token expires after adult_unlock_ttl_minutes (default 60).
"""
from __future__ import annotations

import secrets
import time
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.auth import hash_password, verify_password
from app.config import settings

# token -> expires_at (unix)
_unlock_tokens: dict[str, float] = {}


def passcode_is_set() -> bool:
    return bool((settings.adult_passcode_hash or "").strip())


def set_passcode(raw: str) -> str:
    """Hash and store passcode into settings object (caller persists to DB/env as needed)."""
    h = hash_password(raw)
    settings.adult_passcode_hash = h
    return h


def verify_passcode(raw: str) -> bool:
    stored = (settings.adult_passcode_hash or "").strip()
    if not stored:
        return False
    return verify_password(raw, stored)


def issue_unlock_token() -> dict:
    ttl = max(5, int(getattr(settings, "adult_unlock_ttl_minutes", 60) or 60)) * 60
    tok = secrets.token_urlsafe(24)
    _unlock_tokens[tok] = time.time() + ttl
    # prune expired
    now = time.time()
    for k, exp in list(_unlock_tokens.items()):
        if exp < now:
            _unlock_tokens.pop(k, None)
    return {
        "unlock_token": tok,
        "expires_in": ttl,
        "token_type": "adult-unlock",
    }


def unlock_valid(token: str | None) -> bool:
    if not token:
        return False
    exp = _unlock_tokens.get(token)
    if not exp:
        return False
    if exp < time.time():
        _unlock_tokens.pop(token, None)
        return False
    return True


def require_adult_unlock(
    x_adult_unlock: Annotated[str | None, Header(alias="X-Adult-Unlock")] = None,
):
    """FastAPI dependency — enforce passcode unlock when enabled."""
    if not getattr(settings, "adult_passcode_enabled", True):
        return True
    if not passcode_is_set():
        # No passcode configured yet — allow access but UI should prompt to set one
        return True
    if unlock_valid(x_adult_unlock):
        return True
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Adult module locked. POST /api/adult/unlock with passcode.",
        headers={"X-Adult-Locked": "1"},
    )
