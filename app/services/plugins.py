"""
Plugin / extension registry + GitHub-backed marketplace for MediaOS.

Built-in core plugins register at startup.
Community plugins install into the data dir (default: /config/plugins or data/plugins),
each with mediaos.plugin.json + entry module.

Catalog sources (first that works):
  1. settings.plugin_registry_url (remote JSON)
  2. bundled data/plugin_catalog/catalog.json
"""
from __future__ import annotations

import importlib
import importlib.util
import io
import json
import logging
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Callable

import httpx

log = logging.getLogger("mediaos.plugins")

_REGISTRY: dict[str, dict[str, Any]] = {}
_HOOKS: dict[str, list[Callable]] = {}
_INSTALLED_META_KEY = "installed_plugins"  # AppSetting JSON list


def register(
    plugin_id: str,
    *,
    name: str,
    version: str = "0.0.0",
    hooks: dict[str, Callable] | None = None,
    source: str = "core",
    path: str | None = None,
) -> None:
    _REGISTRY[plugin_id] = {
        "id": plugin_id,
        "name": name,
        "version": version,
        "hooks": list((hooks or {}).keys()),
        "enabled": True,
        "source": source,  # core | installed | env
        "path": path,
    }
    for hname, fn in (hooks or {}).items():
        _HOOKS.setdefault(hname, []).append(fn)
    log.info("Registered plugin %s (%s) source=%s", plugin_id, name, source)


def list_plugins() -> list[dict[str, Any]]:
    return list(_REGISTRY.values())


def get_plugin(plugin_id: str) -> dict[str, Any] | None:
    return _REGISTRY.get(plugin_id)


def run_hook(name: str, *args, **kwargs) -> list[Any]:
    out = []
    for fn in _HOOKS.get(name, []):
        try:
            out.append(fn(*args, **kwargs))
        except Exception as e:
            log.warning("hook %s failed: %s", name, e)
    return out


def plugins_root() -> Path:
    """Writable install directory for community plugins."""
    from app.config import settings

    candidates = []
    custom = getattr(settings, "plugins_path", "") or ""
    if custom:
        candidates.append(Path(custom))
    candidates.extend(
        [
            Path(os.environ.get("MEDIAOS_DATA", "/config")) / "plugins",
            Path("data/plugins"),
            Path("/tmp/mediaos-plugins"),
        ]
    )
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".write_test"
            probe.write_text("ok")
            probe.unlink(missing_ok=True)
            return p
        except Exception:
            continue
    return candidates[-1]


def _bundled_catalog_path() -> Path:
    # repo-relative
    here = Path(__file__).resolve().parents[2]
    return here / "data" / "plugin_catalog" / "catalog.json"


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MediaOS-PluginStore/2.0",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_catalog() -> dict[str, Any]:
    """Load remote or bundled plugin catalog."""
    from app.config import settings

    url = (getattr(settings, "plugin_registry_url", "") or "").strip()
    if url:
        try:
            with httpx.Client(timeout=30.0, headers=_github_headers(), follow_redirects=True) as client:
                r = client.get(url)
                r.raise_for_status()
                data = r.json()
                if isinstance(data, dict) and "plugins" in data:
                    data["_source"] = url
                    return data
        except Exception as e:
            log.warning("plugin registry fetch failed (%s): %s", url, e)

    path = _bundled_catalog_path()
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_source"] = str(path)
        return data
    return {"schema_version": 1, "name": "empty", "plugins": [], "_source": "none"}


def _installed_ids_from_disk() -> list[dict[str, Any]]:
    root = plugins_root()
    out = []
    if not root.is_dir():
        return out
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        manifest = child / "mediaos.plugin.json"
        if not manifest.is_file():
            continue
        try:
            meta = json.loads(manifest.read_text(encoding="utf-8"))
            meta["_install_path"] = str(child)
            out.append(meta)
        except Exception as e:
            log.debug("bad manifest %s: %s", manifest, e)
    return out


def marketplace_status() -> dict[str, Any]:
    """Catalog entries + installed state + runtime registry."""
    catalog = fetch_catalog()
    installed = {m.get("id"): m for m in _installed_ids_from_disk() if m.get("id")}
    runtime = {p["id"]: p for p in list_plugins()}

    items = []
    for entry in catalog.get("plugins") or []:
        pid = entry.get("id")
        install = entry.get("install") or {}
        itype = (install.get("type") or "github_archive").lower()
        online_required = itype not in ("bundled", "local")
        inst_meta = installed.get(pid) or {}
        inst_ver = inst_meta.get("version")
        cat_ver = entry.get("version")
        repo = install.get("repo") or entry.get("github") or ""
        enabled_flag = inst_meta.get("enabled")
        if enabled_flag is None:
            enabled_flag = True
        items.append(
            {
                **entry,
                "installed": pid in installed,
                "loaded": pid in runtime,
                "enabled": bool(enabled_flag) if pid in installed else None,
                "installed_version": inst_ver,
                "runtime": runtime.get(pid),
                "install_type": itype,
                "online_required": online_required,
                "installable": True,
                "update_available": bool(pid in installed and version_newer(cat_ver, inst_ver)),
                "trusted": is_repo_trusted(repo if isinstance(repo, str) else None),
                "trust_allowlist_active": bool(trusted_owners()),
            }
        )

    # Installed but not in catalog
    catalog_ids = {e.get("id") for e in catalog.get("plugins") or []}
    for pid, meta in installed.items():
        if pid not in catalog_ids:
            items.append(
                {
                    "id": pid,
                    "name": meta.get("name") or pid,
                    "description": meta.get("description") or "Locally installed plugin",
                    "version": meta.get("version"),
                    "author": meta.get("author"),
                    "category": meta.get("category") or "local",
                    "installed": True,
                    "loaded": pid in runtime,
                    "installed_version": meta.get("version"),
                    "runtime": runtime.get(pid),
                    "official": False,
                    "local_only": True,
                }
            )

    categories = sorted({(i.get("category") or "other") for i in items})
    return {
        "catalog_source": catalog.get("_source"),
        "catalog_name": catalog.get("name"),
        "catalog_updated": catalog.get("updated"),
        "plugins_path": str(plugins_root()),
        "items": items,
        "categories": categories,
        "runtime": list_plugins(),
        "installed_count": len(installed),
        "registry_url": (getattr(__import__("app.config", fromlist=["settings"]).settings, "plugin_registry_url", "") or "") or None,
    }


def _safe_id(plugin_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", plugin_id)[:80]


def _extract_zip_to_plugin_dir(zbytes: bytes, plugin_id: str) -> Path:
    """Extract zip; prefer folder containing mediaos.plugin.json."""
    root = plugins_root()
    dest = root / _safe_id(plugin_id)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
        # Prevent path traversal
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in Path(name).parts:
                continue
            zf.extract(info, dest)

    # If single top-level folder, flatten when manifest is inside it
    children = [c for c in dest.iterdir()]
    if len(children) == 1 and children[0].is_dir():
        inner = children[0]
        if (inner / "mediaos.plugin.json").is_file() or (inner / "plugin.py").is_file():
            for item in inner.iterdir():
                target = dest / item.name
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                shutil.move(str(item), str(target))
            inner.rmdir()

    # Ensure manifest exists (synthesize minimal if only plugin.py)
    manifest = dest / "mediaos.plugin.json"
    if not manifest.is_file():
        meta = {
            "id": plugin_id,
            "name": plugin_id,
            "version": "0.0.0",
            "entry": "plugin.py",
        }
        manifest.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    else:
        try:
            meta = json.loads(manifest.read_text(encoding="utf-8"))
            if not meta.get("id"):
                meta["id"] = plugin_id
                manifest.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        except Exception:
            pass

    return dest


def _download_github_archive(repo: str, ref: str = "main") -> bytes:
    """Download repo zipball via codeload (no API rate limit on public)."""
    repo = repo.strip().strip("/")
    if repo.startswith("https://github.com/"):
        repo = repo.replace("https://github.com/", "")
    url = f"https://codeload.github.com/{repo}/zip/refs/heads/{ref}"
    headers = _github_headers()
    with httpx.Client(timeout=120.0, headers=headers, follow_redirects=True) as client:
        r = client.get(url)
        if r.status_code == 404:
            # try tags/main fallbacks
            for alt in (f"https://codeload.github.com/{repo}/zip/{ref}", f"https://codeload.github.com/{repo}/zip/refs/tags/{ref}"):
                r = client.get(alt)
                if r.status_code == 200:
                    break
        r.raise_for_status()
        return r.content


def _download_github_release_asset(repo: str, asset_glob: str = "*.zip") -> bytes:
    repo = repo.strip().strip("/")
    if repo.startswith("https://github.com/"):
        repo = repo.replace("https://github.com/", "")
    api = f"https://api.github.com/repos/{repo}/releases/latest"
    with httpx.Client(timeout=60.0, headers=_github_headers(), follow_redirects=True) as client:
        r = client.get(api)
        r.raise_for_status()
        rel = r.json()
        assets = rel.get("assets") or []
        import fnmatch

        chosen = None
        for a in assets:
            name = a.get("name") or ""
            if fnmatch.fnmatch(name, asset_glob):
                chosen = a
                break
        if not chosen and assets:
            # prefer any zip
            for a in assets:
                if (a.get("name") or "").endswith(".zip"):
                    chosen = a
                    break
        if not chosen:
            # fallback to source zipball
            zipball = rel.get("zipball_url")
            if zipball:
                r2 = client.get(zipball)
                r2.raise_for_status()
                return r2.content
            raise RuntimeError(f"No matching release asset for {repo} ({asset_glob})")
        r2 = client.get(chosen["browser_download_url"])
        r2.raise_for_status()
        return r2.content


def _load_plugin_from_dir(path: Path) -> str | None:
    """Import plugin entry and call register_plugin. Returns plugin id."""
    manifest_path = path / "mediaos.plugin.json"
    meta: dict[str, Any] = {}
    if manifest_path.is_file():
        meta = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = meta.get("entry") or "plugin.py"
    entry_path = path / entry
    if not entry_path.is_file():
        # try package
        if (path / "__init__.py").is_file():
            entry_path = path / "__init__.py"
        else:
            log.warning("No entry module in %s", path)
            return None

    plugin_id = meta.get("id") or path.name
    mod_name = f"mediaos_plugin_{_safe_id(plugin_id).replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(mod_name, entry_path)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    # Allow relative imports within plugin folder
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        log.warning("Failed executing plugin %s: %s", plugin_id, e)
        return None

    def _reg(pid, **kwargs):
        register(pid, source="installed", path=str(path), **kwargs)

    if hasattr(module, "register_plugin"):
        module.register_plugin(_reg)
    elif hasattr(module, "register"):
        module.register(_reg)
    else:
        # auto-register from manifest only
        register(
            plugin_id,
            name=meta.get("name") or plugin_id,
            version=str(meta.get("version") or "0.0.0"),
            source="installed",
            path=str(path),
        )
    return plugin_id



def _version_tuple(v: str | None) -> tuple:
    if not v:
        return (0,)
    parts = []
    for bit in str(v).replace("-", ".").split("."):
        try:
            parts.append(int("".join(ch for ch in bit if ch.isdigit()) or "0"))
        except ValueError:
            parts.append(0)
    return tuple(parts) or (0,)


def version_newer(catalog_ver: str | None, installed_ver: str | None) -> bool:
    """True if catalog_ver > installed_ver."""
    return _version_tuple(catalog_ver) > _version_tuple(installed_ver)


def trusted_owners() -> list[str]:
    """Comma-separated allowlist from settings.plugin_trusted_owners (empty = allow all with warning)."""
    from app.config import settings
    raw = (getattr(settings, "plugin_trusted_owners", "") or "").strip()
    if not raw:
        return []
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def is_repo_trusted(repo: str | None) -> bool:
    owners = trusted_owners()
    if not owners:
        return True  # no allowlist configured
    if not repo:
        return False
    repo = repo.strip().strip("/").replace("https://github.com/", "")
    owner = repo.split("/")[0].lower() if "/" in repo else repo.lower()
    return owner in owners


def _plugin_dir_for_id(plugin_id: str) -> Path | None:
    root = plugins_root()
    dest = root / _safe_id(plugin_id)
    if dest.is_dir() and (dest / "mediaos.plugin.json").is_file():
        return dest
    if not root.is_dir():
        return None
    for child in root.iterdir():
        if not child.is_dir():
            continue
        m = child / "mediaos.plugin.json"
        if not m.is_file():
            continue
        try:
            meta = json.loads(m.read_text(encoding="utf-8"))
            if meta.get("id") == plugin_id:
                return child
        except Exception:
            pass
    return None


def set_plugin_enabled(plugin_id: str, enabled: bool) -> dict[str, Any]:
    """Persist enabled flag in mediaos.plugin.json; unload from registry when disabled."""
    if plugin_id.startswith("core."):
        raise ValueError("Cannot disable core plugins")
    path = _plugin_dir_for_id(plugin_id)
    if not path:
        raise ValueError(f"Plugin {plugin_id} is not installed")
    manifest = path / "mediaos.plugin.json"
    meta: dict[str, Any] = {}
    if manifest.is_file():
        try:
            meta = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    meta["id"] = meta.get("id") or plugin_id
    meta["enabled"] = bool(enabled)
    manifest.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    if not enabled:
        _REGISTRY.pop(plugin_id, None)
        return {"ok": True, "id": plugin_id, "enabled": False, "loaded": False}

    loaded = _load_plugin_from_dir(path)
    return {"ok": True, "id": plugin_id, "enabled": True, "loaded": bool(loaded)}


def install_from_catalog(plugin_id: str) -> dict[str, Any]:
    catalog = fetch_catalog()
    entry = next((p for p in (catalog.get("plugins") or []) if p.get("id") == plugin_id), None)
    if not entry:
        raise ValueError(f"Plugin {plugin_id} not found in catalog")

    install = entry.get("install") or {}
    itype = (install.get("type") or "github_archive").lower()
    repo = install.get("repo") or ""
    if not repo and entry.get("github"):
        repo = entry["github"]

    if itype not in ("bundled", "local") and trusted_owners() and not is_repo_trusted(repo):
        raise ValueError(
            f"Plugin repo not in plugin_trusted_owners allowlist ({repo}). "
            f"Allowed: {', '.join(trusted_owners())}"
        )

    if itype in ("builtin", "none", "link"):
        raise ValueError(
            "This entry is built into MediaOS (e.g. Homelab → Announce Lab). Nothing to download."
        )
    if itype == "bundled":
        # Copy from repo-bundled example / path
        rel = install.get("path") or ""
        here = Path(__file__).resolve().parents[2]
        src = (here / rel).resolve()
        if not src.is_dir():
            raise ValueError(f"Bundled plugin path missing: {rel}")
        dest = plugins_root() / _safe_id(plugin_id)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    elif itype == "github_release":
        zbytes = _download_github_release_asset(repo, install.get("asset_glob") or "*.zip")
        dest = _extract_zip_to_plugin_dir(zbytes, plugin_id)
    elif itype in ("github_archive", "github_repo", "git"):
        zbytes = _download_github_archive(repo, install.get("ref") or "main")
        dest = _extract_zip_to_plugin_dir(zbytes, plugin_id)
    elif itype == "url":
        url = install.get("url") or ""
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            zbytes = r.content
        dest = _extract_zip_to_plugin_dir(zbytes, plugin_id)
    else:
        raise ValueError(f"Unsupported install type: {itype}")
    # Write/update manifest with catalog metadata
    manifest = dest / "mediaos.plugin.json"
    meta = {}
    if manifest.is_file():
        try:
            meta = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    meta.setdefault("id", plugin_id)
    meta.setdefault("name", entry.get("name") or plugin_id)
    meta.setdefault("version", entry.get("version") or "0.0.0")
    meta.setdefault("description", entry.get("description"))
    meta.setdefault("author", entry.get("author"))
    meta.setdefault("category", entry.get("category"))
    meta["github"] = entry.get("github")
    manifest.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    loaded = _load_plugin_from_dir(dest)
    return {
        "ok": True,
        "id": plugin_id,
        "path": str(dest),
        "loaded": bool(loaded),
        "version": meta.get("version"),
    }


def install_from_github(repo: str, ref: str = "main", plugin_id: str | None = None, *, force: bool = False) -> dict[str, Any]:
    repo_clean = repo.strip().strip("/").replace("https://github.com/", "")
    if not force and trusted_owners() and not is_repo_trusted(repo_clean):
        raise ValueError(
            f"Repository owner not in plugin_trusted_owners allowlist. "
            f"Allowed: {', '.join(trusted_owners())} (or clear allowlist / pass force)"
        )
    pid = plugin_id or f"github.{repo_clean.replace('/', '.')}"
    zbytes = _download_github_archive(repo_clean, ref)
    dest = _extract_zip_to_plugin_dir(zbytes, pid)
    loaded = _load_plugin_from_dir(dest)
    return {"ok": True, "id": pid, "path": str(dest), "loaded": bool(loaded), "repo": repo_clean, "ref": ref}


def uninstall_plugin(plugin_id: str) -> dict[str, Any]:
    """Remove installed plugin files and drop from runtime registry."""
    root = plugins_root()
    dest = root / _safe_id(plugin_id)
    # Also search by manifest id
    if not dest.is_dir():
        for child in root.iterdir() if root.is_dir() else []:
            if not child.is_dir():
                continue
            m = child / "mediaos.plugin.json"
            if m.is_file():
                try:
                    meta = json.loads(m.read_text(encoding="utf-8"))
                    if meta.get("id") == plugin_id:
                        dest = child
                        break
                except Exception:
                    pass
    removed = False
    if dest.is_dir():
        shutil.rmtree(dest)
        removed = True
    _REGISTRY.pop(plugin_id, None)
    return {"ok": True, "id": plugin_id, "removed": removed}


def load_installed_plugins() -> list[str]:
    loaded = []
    for meta in _installed_ids_from_disk():
        if meta.get("enabled") is False:
            log.info("Skipping disabled plugin %s", meta.get("id"))
            continue
        path = Path(meta.get("_install_path") or "")
        if path.is_dir():
            pid = _load_plugin_from_dir(path)
            if pid:
                loaded.append(pid)
    return loaded


def load_plugins() -> list[str]:
    """Load core + env + installed community plugins."""
    loaded: list[str] = []
    # Avoid double-register on reload
    if not any(k.startswith("core.") for k in _REGISTRY):
        register("core.games", name="Games Module", version="next", source="core")
        register("core.scrobbling", name="Scrobbling Layer", version="next", source="core")
        register("core.tracking", name="Unified Tracking", version="next", source="core")
        register("core.homelab", name="Homelab Links", version="next", source="core")
        register("core.converter", name="Tdarr-class Converter", version="next", source="core")
        loaded.extend(["core.games", "core.scrobbling", "core.tracking", "core.homelab"])

    raw = (
        os.environ.get("PLUGINS")
        or getattr(__import__("app.config", fromlist=["settings"]).settings, "plugins", "")
        or ""
    )
    for mod in [x.strip() for x in str(raw).split(",") if x.strip()]:
        try:
            m = importlib.import_module(mod)
            if hasattr(m, "register_plugin"):
                m.register_plugin(register)
            elif hasattr(m, "register"):
                m.register(register)
            loaded.append(mod)
            log.info("Loaded plugin module %s", mod)
        except Exception as e:
            log.warning("Failed to load plugin %s: %s", mod, e)

    try:
        loaded.extend(load_installed_plugins())
    except Exception as e:
        log.warning("installed plugins load: %s", e)

    return loaded


# Eager core registration on import
try:
    load_plugins()
except Exception as e:
    log.debug("plugins bootstrap: %s", e)


def reinstall_plugin(plugin_id: str) -> dict[str, Any]:
    """Uninstall then install from catalog again."""
    try:
        uninstall_plugin(plugin_id)
    except Exception:
        pass
    return install_from_catalog(plugin_id)
