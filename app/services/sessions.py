"""DB-backed multi-user sessions (survive restarts / multi-worker).

Falls back to in-memory if DB is unavailable so auth never hard-breaks.
"""
from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

ACCESS_TTL = 60 * 60 * 4  # 4h
REFRESH_TTL = 60 * 60 * 24 * 7  # 7d

# process-local cache (optional speed; DB is source of truth)
_sessions: dict[str, dict] = {}
_refresh: dict[str, str] = {}

_REDIS_SESS = "mediaos:sess:access:"
_REDIS_REFRESH = "mediaos:sess:refresh:"


def _redis():
    try:
        from app.services.redis_client import get_redis
        return get_redis()
    except Exception:
        return None


def _cache_put_access(token: str, row: dict, ttl: int) -> None:
    r = _redis()
    if r is None:
        return
    try:
        import json
        payload = json.dumps({k: v for k, v in row.items() if k != "refresh_token"})
        r.setex(_REDIS_SESS + token, max(1, int(ttl)), payload)
        refresh = row.get("refresh_token")
        if refresh:
            r.setex(_REDIS_REFRESH + refresh, max(1, int(row.get("refresh_expires_at", time.time()) - time.time())), token)
    except Exception as e:
        log.debug("redis session cache put: %s", e)


def _cache_get_access(token: str) -> dict | None:
    r = _redis()
    if r is None:
        return None
    try:
        import json
        raw = r.get(_REDIS_SESS + token)
        if not raw:
            return None
        data = json.loads(raw)
        if float(data.get("expires_at") or 0) < time.time():
            r.delete(_REDIS_SESS + token)
            return None
        return data
    except Exception as e:
        log.debug("redis session cache get: %s", e)
        return None


def _cache_delete_access(token: str) -> None:
    r = _redis()
    if r is None:
        return
    try:
        r.delete(_REDIS_SESS + token)
    except Exception:
        pass



def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_ts(dt: datetime | None) -> float:
    if dt is None:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _db():
    try:
        from app.database import SessionLocal
        return SessionLocal()
    except Exception as e:
        log.debug("sessions db unavailable: %s", e)
        return None


def create_session(
    username: str,
    role: str,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
) -> dict:
    access = secrets.token_urlsafe(32)
    refresh = secrets.token_urlsafe(32)
    now = time.time()
    exp = now + ACCESS_TTL
    rexp = now + REFRESH_TTL
    ua = (user_agent or "")[:200]
    ip_s = (ip or "")[:64]

    row = {
        "username": username,
        "role": role,
        "created_at": now,
        "expires_at": exp,
        "refresh_expires_at": rexp,
        "user_agent": ua,
        "ip": ip_s,
        "refresh_token": refresh,
    }
    _sessions[access] = row
    _refresh[refresh] = access
    _cache_put_access(access, row, ACCESS_TTL)

    db = _db()
    if db is not None:
        try:
            from app.models import AuthSession
            db.add(
                AuthSession(
                    access_token=access,
                    refresh_token=refresh,
                    username=username,
                    role=role,
                    user_agent=ua or None,
                    ip=ip_s or None,
                    created_at=_utcnow(),
                    expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
                    refresh_expires_at=datetime.fromtimestamp(rexp, tz=timezone.utc),
                    revoked=False,
                )
            )
            db.commit()
        except Exception as e:
            log.warning("persist session failed: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()

    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_in": ACCESS_TTL,
        "username": username,
        "role": role,
    }


def resolve_access(token: str) -> dict | None:
    if not token:
        return None
    # memory first
    s = _sessions.get(token)
    if s and s["expires_at"] >= time.time():
        return s
    if s and s["expires_at"] < time.time():
        _sessions.pop(token, None)

    # shared redis cache (multi-worker)
    cached = _cache_get_access(token)
    if cached:
        _sessions[token] = cached
        return cached

    db = _db()
    if db is None:
        return None
    try:
        from app.models import AuthSession
        row = (
            db.query(AuthSession)
            .filter(
                AuthSession.access_token == token,
                AuthSession.revoked.is_(False),
            )
            .first()
        )
        if not row:
            return None
        if _to_ts(row.expires_at) < time.time():
            return None
        data = {
            "username": row.username,
            "role": row.role,
            "created_at": _to_ts(row.created_at),
            "expires_at": _to_ts(row.expires_at),
            "refresh_expires_at": _to_ts(row.refresh_expires_at),
            "user_agent": row.user_agent or "",
            "ip": row.ip or "",
            "refresh_token": row.refresh_token,
        }
        _sessions[token] = data
        _refresh[row.refresh_token] = token
        ttl = max(1, int(_to_ts(row.expires_at) - time.time()))
        _cache_put_access(token, data, ttl)
        return data
    except Exception as e:
        log.debug("resolve_access db: %s", e)
        return None
    finally:
        db.close()


def refresh_session(refresh_token: str) -> dict | None:
    if not refresh_token:
        return None
    access = _refresh.get(refresh_token)
    old = _sessions.get(access) if access else None

    if not old:
        db = _db()
        if db is not None:
            try:
                from app.models import AuthSession
                row = (
                    db.query(AuthSession)
                    .filter(
                        AuthSession.refresh_token == refresh_token,
                        AuthSession.revoked.is_(False),
                    )
                    .first()
                )
                if row and _to_ts(row.refresh_expires_at) >= time.time():
                    old = {
                        "username": row.username,
                        "role": row.role,
                        "user_agent": row.user_agent or "",
                        "ip": row.ip or "",
                    }
                    # revoke old
                    row.revoked = True
                    db.add(row)
                    db.commit()
                    access = row.access_token
            except Exception as e:
                log.debug("refresh db lookup: %s", e)
            finally:
                db.close()
    if not old:
        return None
    if access:
        revoke(access)
    return create_session(
        old["username"],
        old["role"],
        user_agent=old.get("user_agent"),
        ip=old.get("ip"),
    )


def revoke(access_token: str) -> bool:
    s = _sessions.pop(access_token, None)
    if s:
        rt = s.get("refresh_token")
        if rt:
            _refresh.pop(rt, None)
    db = _db()
    if db is None:
        return bool(s)
    try:
        from app.models import AuthSession
        row = db.query(AuthSession).filter(AuthSession.access_token == access_token).first()
        if row:
            row.revoked = True
            db.add(row)
            db.commit()
            return True
        return bool(s)
    except Exception as e:
        log.debug("revoke db: %s", e)
        return bool(s)
    finally:
        db.close()


def revoke_user(username: str) -> int:
    n = 0
    for tok in list(_sessions.keys()):
        if _sessions[tok].get("username") == username:
            revoke(tok)
            n += 1
    db = _db()
    if db is not None:
        try:
            from app.models import AuthSession
            rows = (
                db.query(AuthSession)
                .filter(AuthSession.username == username, AuthSession.revoked.is_(False))
                .all()
            )
            for r in rows:
                r.revoked = True
                db.add(r)
                n += 1
            db.commit()
        except Exception as e:
            log.debug("revoke_user db: %s", e)
        finally:
            db.close()
    return n


def list_sessions(username: str | None = None) -> list[dict]:
    out = []
    seen = set()
    for tok, s in _sessions.items():
        if username and s.get("username") != username:
            continue
        seen.add(tok)
        out.append(
            {
                "token_prefix": tok[:8] + "…",
                "username": s["username"],
                "role": s["role"],
                "created_at": s.get("created_at"),
                "expires_at": s.get("expires_at"),
                "user_agent": s.get("user_agent"),
                "ip": s.get("ip"),
                "source": "memory",
            }
        )
    db = _db()
    if db is not None:
        try:
            from app.models import AuthSession
            q = db.query(AuthSession).filter(AuthSession.revoked.is_(False))
            if username:
                q = q.filter(AuthSession.username == username)
            for row in q.order_by(AuthSession.created_at.desc()).limit(100).all():
                if row.access_token in seen:
                    continue
                if _to_ts(row.expires_at) < time.time():
                    continue
                out.append(
                    {
                        "token_prefix": row.access_token[:8] + "…",
                        "username": row.username,
                        "role": row.role,
                        "created_at": _to_ts(row.created_at),
                        "expires_at": _to_ts(row.expires_at),
                        "user_agent": row.user_agent,
                        "ip": row.ip,
                        "source": "db",
                    }
                )
        except Exception as e:
            log.debug("list_sessions db: %s", e)
        finally:
            db.close()
    return out


def purge_expired() -> int:
    """Revoke expired rows. Safe to call from scheduler."""
    n = 0
    now = time.time()
    for tok, s in list(_sessions.items()):
        if s.get("expires_at", 0) < now:
            _sessions.pop(tok, None)
            rt = s.get("refresh_token")
            if rt:
                _refresh.pop(rt, None)
            n += 1
    db = _db()
    if db is not None:
        try:
            from app.models import AuthSession
            rows = db.query(AuthSession).filter(AuthSession.revoked.is_(False)).all()
            for r in rows:
                if _to_ts(r.expires_at) < now and _to_ts(r.refresh_expires_at) < now:
                    r.revoked = True
                    db.add(r)
                    n += 1
            db.commit()
        except Exception as e:
            log.debug("purge_expired: %s", e)
        finally:
            db.close()
    return n



def revoke_by_prefix(prefix: str, *, actor: dict | None = None) -> bool:
    """Revoke session whose access token starts with prefix (strip ellipsis)."""
    prefix = (prefix or "").replace("…", "").replace("...", "").strip()
    if len(prefix) < 6:
        return False
    # memory
    for tok in list(_sessions.keys()):
        if tok.startswith(prefix):
            if actor and actor.get("role") != "admin" and _sessions[tok].get("username") != actor.get("username"):
                continue
            revoke(tok)
            return True
    db = _db()
    if db is None:
        return False
    try:
        from app.models import AuthSession
        q = db.query(AuthSession).filter(
            AuthSession.access_token.startswith(prefix),
            AuthSession.revoked.is_(False),
        )
        if actor and actor.get("role") != "admin":
            q = q.filter(AuthSession.username == actor.get("username"))
        row = q.first()
        if not row:
            return False
        row.revoked = True
        db.add(row)
        db.commit()
        _sessions.pop(row.access_token, None)
        return True
    except Exception as e:
        log.debug("revoke_by_prefix: %s", e)
        return False
    finally:
        db.close()


def revoke_others_for_user(username: str, keep_access: str) -> int:
    n = 0
    for tok in list(_sessions.keys()):
        if _sessions[tok].get("username") == username and tok != keep_access:
            revoke(tok)
            n += 1
    db = _db()
    if db is not None:
        try:
            from app.models import AuthSession
            rows = (
                db.query(AuthSession)
                .filter(
                    AuthSession.username == username,
                    AuthSession.revoked.is_(False),
                    AuthSession.access_token != keep_access,
                )
                .all()
            )
            for r in rows:
                r.revoked = True
                db.add(r)
                n += 1
            db.commit()
        except Exception as e:
            log.debug("revoke_others: %s", e)
        finally:
            db.close()
    return n


def revoke_access(token: str) -> bool:
    _cache_delete_access(token)
    """Revoke a single access token (memory + DB)."""
    if not token:
        return False
    row = _sessions.pop(token, None)
    if row and row.get("refresh_token"):
        _refresh.pop(row["refresh_token"], None)
    db = _db()
    if db is None:
        return bool(row)
    try:
        from app.models import AuthSession
        n = (
            db.query(AuthSession)
            .filter(AuthSession.access_token == token, AuthSession.revoked.is_(False))
            .update({"revoked": True})
        )
        db.commit()
        return bool(row) or n > 0
    except Exception as e:
        log.debug("revoke_access: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return bool(row)
    finally:
        db.close()
