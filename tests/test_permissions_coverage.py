"""Ensure critical routers declare permission dependencies."""
from __future__ import annotations

import ast
from pathlib import Path

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"

# Routers that must not be wide-open (must reference require_permission or require_admin / require_arr_key)
MUST_PROTECT = {
    "movies.py",
    "tv.py",
    "music.py",
    "books.py",
    "audiobooks.py",
    "comics.py",
    "queue.py",
    "converter.py",
    "users.py",
    "settings.py",
    "indexers.py",
}


def test_critical_routers_reference_permissions():
    missing = []
    for name in sorted(MUST_PROTECT):
        path = ROUTERS / name
        assert path.exists(), f"missing router {name}"
        text = path.read_text()
        if not any(
            s in text
            for s in (
                "require_permission",
                "require_admin",
                "require_arr_key",
                "require_auth",
            )
        ):
            missing.append(name)
    assert not missing, f"routers without permission deps: {missing}"


def test_comics_router_has_route_level_perms():
    text = (ROUTERS / "comics.py").read_text()
    # key mutating endpoints should mention require_permission near definition
    for needle in ("delete_comic", "grab_issue", "sync_issues", "add_comic"):
        assert needle in text
    assert text.count("require_permission") >= 5


def test_organize_helpers_exported():
    from app.services import organize
    assert hasattr(organize, "_extract_comic_issue_number")
    assert hasattr(organize, "_comic_dest_dir")
    assert hasattr(organize, "_comic_issue_lookup_keys")
