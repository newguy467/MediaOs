"""arr_compat expanded endpoints + path/preset smokes."""
from __future__ import annotations


def test_arr_compat_extra_routes_importable():
    from app.routers import arr_compat
    paths = {getattr(r, "path", "") for r in arr_compat.router.routes}
    for need in (
        "/api/v3/filesystem",
        "/api/v3/config/host",
        "/api/v3/qualitydefinition",
        "/api/v3/downloadclient",
        "/api/v3/episodefile",
    ):
        assert need in paths, f"missing {need}"


def test_path_conflicts_settings_scan():
    from app.services.path_conflicts import scan_settings_paths, detect_duplicate_paths
    paths = scan_settings_paths()
    assert isinstance(paths, list)
    assert all("key" in p for p in paths)
    # should not throw
    detect_duplicate_paths(paths)


def test_quality_presets_list():
    from app.services.quality.profiles import list_preset_packs, apply_preset_pack
    ids = {p["id"] for p in list_preset_packs()}
    assert {"hd", "uhd", "anime"} <= ids
    assert apply_preset_pack("hd")["ok"] is True
