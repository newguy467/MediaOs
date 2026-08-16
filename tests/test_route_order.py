"""Regression: FastAPI matches routes in registration order.

When a path param route is registered before a same-prefix literal, the
literal can be absorbed (str params) or 422 (int params) instead of matching
the intended handler. Real bugs were fixed in music, games, livetv, parity,
and movies/books/adult bulk endpoints.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"


def _routes_in_order(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: list[tuple[str, str]] = []
    for m in re.finditer(
        r'@router\.(get|post|put|patch|delete)\(\s*["\']([^"\']+)["\']',
        text,
        re.I,
    ):
        out.append((m.group(1).lower(), m.group(2)))
    return out


def find_same_method_shadows(routes: list[tuple[str, str]]) -> list[str]:
    """Literal path registered after a same-method `{param}` sibling.

    Only flags cases where the param route is exactly `prefix/{param}` or
    `prefix/{param}/...` and a later route is `prefix/literal` with the same
    HTTP method — the classic FastAPI ordering bug.
    """
    problems = []
    for i, (method, path) in enumerate(routes):
        # Match /foo/{id} or /{id} at end of a segment
        m = re.match(r"^(?P<prefix>.*?/)\{(?P<param>[^}/]+)\}$", path)
        if not m:
            continue
        prefix = m.group("prefix")  # includes trailing slash
        for method2, path2 in routes[i + 1 :]:
            if method2 != method:
                continue
            if not path2.startswith(prefix):
                continue
            rest = path2[len(prefix) :]
            # single-segment literal (no further slash, no param)
            if rest and "/" not in rest and not rest.startswith("{"):
                problems.append(
                    f"{method.upper()} {path} before {method2.upper()} {path2}"
                )
    return problems


def test_no_same_method_param_shadowing():
    errors = []
    for p in sorted(ROUTERS.glob("*.py")):
        if p.name.startswith("_"):
            continue
        for msg in find_same_method_shadows(_routes_in_order(p)):
            errors.append(f"{p.name}: {msg}")
    assert not errors, "Route ordering problems:\n" + "\n".join(errors)


def test_parity_search_all_before_job_id():
    routes = _routes_in_order(ROUTERS / "parity.py")
    paths = [r[1] for r in routes]
    assert paths.index("/workers/search-all") < paths.index("/workers/{job_id}")


def test_movies_bulk_before_item_id():
    routes = _routes_in_order(ROUTERS / "movies.py")
    paths = [r[1] for r in routes]
    assert paths.index("/bulk") < paths.index("/{item_id}")


def test_books_bulk_before_item_id():
    routes = _routes_in_order(ROUTERS / "books.py")
    paths = [r[1] for r in routes]
    assert "/bulk" in paths
    item_idxs = [i for i, p in enumerate(paths) if p == "/{item_id}"]
    assert item_idxs, "expected /{item_id}"
    assert paths.index("/bulk") < min(item_idxs)


def test_audiobooks_bulk_before_item_id():
    routes = _routes_in_order(ROUTERS / "audiobooks.py")
    paths = [r[1] for r in routes]
    item_idxs = [i for i, p in enumerate(paths) if p == "/{item_id}"]
    assert paths.index("/bulk") < min(item_idxs)


def test_all_router_files_parse():
    for p in ROUTERS.glob("*.py"):
        ast.parse(p.read_text(encoding="utf-8", errors="replace"))

def test_music_bulk_before_item_id():
    routes = _routes_in_order(ROUTERS / "music.py")
    paths = [p for m, p in routes if m == "post"]
    assert "/bulk" in paths
    bi = paths.index("/bulk")
    # any /{item_id} or /{id} after should be fine; bulk must not come after a param-only post
    for j, path in enumerate(paths):
        if path in ("/{item_id}", "/{id}", "/{music_id}", "/{album_id}"):
            assert j > bi or path.startswith("/bulk"), f"{path} registered before /bulk"


def test_comics_bulk_before_item_id():
    routes = _routes_in_order(ROUTERS / "comics.py")
    paths = [p for m, p in routes if m == "post"]
    assert "/bulk" in paths
    bi = paths.index("/bulk")
    for j, path in enumerate(paths):
        if path == "/{item_id}":
            assert j > bi, "/{item_id} must not precede POST /bulk"


def test_games_and_podcasts_bulk_order():
    for name in ("games.py", "podcasts.py"):
        routes = _routes_in_order(ROUTERS / name)
        posts = [p for m, p in routes if m == "post"]
        if "/bulk" not in posts:
            continue
        bi = posts.index("/bulk")
        for j, path in enumerate(posts):
            if path.startswith("/{") and path.count("/") == 1:
                assert j > bi, f"{name}: {path} before /bulk"



def test_converter_retry_after_param_is_ok():
    """/{job_id}/retry is a subpath of /{job_id} — both POST; ensure cancel/retry exist."""
    routes = _routes_in_order(ROUTERS / "converter.py")
    posts = [p for m, p in routes if m == "post"]
    assert any(p.endswith("/retry") or p == "/jobs/{job_id}/retry" for p in posts), posts
    assert any("cancel" in p for p in posts)
