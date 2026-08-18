"""RBAC tests: 4-role model (admin/manager/member/guest), permission
defaults, and route-level gating (require_permission / require_manager /
require_admin).

Flagged as missing in todo.md Session 22 ("no tests written for the new
role/permission logic — no test_rbac*.py exists yet"). This fills that gap.

Auth is disabled by default in the test suite (tests/conftest.py sets
AUTH_REQUIRE=false so every request resolves to role="admin"), so the
route-gating tests below flip `app.config.settings.auth_require` on for
the duration of the test and create real DB users to authenticate as,
restoring the flag afterward so it doesn't leak into other test modules.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Pure unit tests — no DB, no auth, no network. Exercise the permission
# tables directly the way app/routers/users.py and app/auth.py define them.
# ---------------------------------------------------------------------------

def test_role_defaults_shape():
    from app.routers.users import ROLE_DEFAULTS, PERMISSION_CATALOG, VALID_ROLES

    all_ids = {p["id"] for p in PERMISSION_CATALOG}
    assert "users" in all_ids

    for role in VALID_ROLES:
        assert role in ROLE_DEFAULTS
        # every granted permission id must be a real catalog entry
        assert set(ROLE_DEFAULTS[role]) <= all_ids


def test_admin_has_every_permission():
    from app.routers.users import ROLE_DEFAULTS, PERMISSION_CATALOG

    all_ids = {p["id"] for p in PERMISSION_CATALOG}
    assert set(ROLE_DEFAULTS["admin"]) == all_ids


def test_manager_has_everything_except_users():
    from app.routers.users import ROLE_DEFAULTS, PERMISSION_CATALOG

    all_ids = {p["id"] for p in PERMISSION_CATALOG}
    assert "users" not in ROLE_DEFAULTS["manager"]
    assert set(ROLE_DEFAULTS["manager"]) == all_ids - {"users"}
    # settings/indexers are the operator-tier permissions manager needs
    assert "settings" in ROLE_DEFAULTS["manager"]
    assert "indexers" in ROLE_DEFAULTS["manager"]


def test_member_is_browse_play_request_download_only():
    from app.routers.users import ROLE_DEFAULTS

    member = set(ROLE_DEFAULTS["member"])
    assert member == {
        "library.view", "discover.view", "player.view",
        "calendar.view", "download", "queue", "requests",
    }
    assert "settings" not in member
    assert "users" not in member


def test_guest_is_view_only():
    from app.routers.users import ROLE_DEFAULTS

    guest = set(ROLE_DEFAULTS["guest"])
    assert guest == {"library.view", "discover.view", "player.view", "calendar.view"}
    # guest can browse/play but never grab, queue, or request
    assert "download" not in guest
    assert "queue" not in guest
    assert "requests" not in guest


def test_deprecated_user_alias_matches_member():
    from app.routers.users import ROLE_DEFAULTS

    assert ROLE_DEFAULTS["user"] == ROLE_DEFAULTS["member"]


def test_user_role_enum_has_deprecated_alias():
    from app.models import UserRole

    assert UserRole.user.value == "user"
    assert {r.value for r in UserRole} == {"admin", "manager", "member", "guest", "user"}


# ---------------------------------------------------------------------------
# Integration tests — real TestClient + real DB users, auth turned on for
# the duration of the test.
# ---------------------------------------------------------------------------

@pytest.fixture()
def auth_on():
    """Flip AUTH_REQUIRE on for one test, restore it afterward."""
    from app.config import settings

    prev = settings.auth_require
    settings.auth_require = True
    try:
        yield
    finally:
        settings.auth_require = prev


@pytest.fixture()
def make_user(db):
    """Create a DB user with role-default permissions (permissions_json=None)."""
    from app.auth import hash_password
    from app.models import User

    created = []

    def _make(username: str, password: str, role: str):
        u = User(username=username, password_hash=hash_password(password), role=role)
        db.add(u)
        db.commit()
        db.refresh(u)
        created.append(u)
        return u

    yield _make

    for u in created:
        try:
            db.delete(u)
            db.commit()
        except Exception:
            db.rollback()


def _basic(username: str, password: str) -> dict:
    import base64
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_member_forbidden_from_settings_permission_route(client, auth_on, make_user):
    make_user("rbac_member1", "memberpw1", "member")
    r = client.get("/api/logs", headers=_basic("rbac_member1", "memberpw1"))
    assert r.status_code == 403


def test_manager_allowed_on_settings_permission_route(client, auth_on, make_user):
    make_user("rbac_manager1", "managerpw1", "manager")
    r = client.get("/api/logs", headers=_basic("rbac_manager1", "managerpw1"))
    assert r.status_code != 403


def test_manager_forbidden_from_admin_only_user_management(client, auth_on, make_user):
    make_user("rbac_manager2", "managerpw2", "manager")
    r = client.get("/api/users", headers=_basic("rbac_manager2", "managerpw2"))
    assert r.status_code == 403


def test_admin_allowed_on_admin_only_user_management(client, auth_on, make_user):
    make_user("rbac_admin1", "adminpw1", "admin")
    r = client.get("/api/users", headers=_basic("rbac_admin1", "adminpw1"))
    assert r.status_code != 403


def test_guest_forbidden_from_settings_permission_route(client, auth_on, make_user):
    make_user("rbac_guest1", "guestpw1", "guest")
    r = client.get("/api/logs", headers=_basic("rbac_guest1", "guestpw1"))
    assert r.status_code == 403


def test_require_manager_allows_manager_and_admin_not_member(client, auth_on, make_user):
    """The dedicated require_manager dependency (used by requests approve/deny)
    should accept admin or manager and reject member/guest."""
    make_user("rbac_mgr3", "mgrpw3", "manager")
    make_user("rbac_mem3", "mempw3", "member")

    # A nonexistent request id still passes the auth/role check before the
    # 404 lookup, so a 404 (not 403) proves the manager got past require_manager.
    r_mgr = client.post(
        "/api/requests/999999/approve",
        headers=_basic("rbac_mgr3", "mgrpw3"),
    )
    assert r_mgr.status_code != 403

    r_mem = client.post(
        "/api/requests/999999/approve",
        headers=_basic("rbac_mem3", "mempw3"),
    )
    assert r_mem.status_code == 403


def test_permission_override_replaces_role_defaults(client, auth_on, make_user, db):
    """A user's stored permissions_json (when set) should be used instead of
    the role defaults — e.g. a member granted the 'settings' permission
    explicitly should pass a require_permission("settings") route."""
    import json
    from app.models import User

    u = make_user("rbac_override1", "overridepw1", "member")
    u.permissions_json = json.dumps(["settings"])
    db.add(u)
    db.commit()

    r = client.get("/api/logs", headers=_basic("rbac_override1", "overridepw1"))
    assert r.status_code != 403
