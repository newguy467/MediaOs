"""Cardigann YAML tracker definitions — Jackett-compatible subset.

Load `.yml` defs from CARDIGANN_DEFINITIONS_PATH, run keyword search without
Prowlarr. Supports a practical subset of the Cardigann/Jackett schema:

  - Header: id, name, type, links, encoding
  - caps.modes / categorymappings (informational)
  - settings (username/password/cookie/apikey stored per-def in DB overrides)
  - login: form POST (path + inputs) with error/test selectors
  - search: paths[], inputs{}, rows.selector, fields.{title,download,magnet,
    size,seeders,leechers,details,date,infohash}
  - Response types: HTML (CSS selectors via BeautifulSoup) and JSON (dot paths)
  - Templates: {{ .Keywords }}, {{ .Query.Q }}, {{ .Config.<key> }},
    {{ if .Keywords }}...{{ else }}...{{ end }}

This is not a full Jackett clone — complex filters, imdb-id searches, and
download-page follow are intentionally limited. Prefer Prowlarr for exotic
private trackers; use Cardigann here for common public + simple private form logins.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import yaml

from app.services.rate_limit import wait as rate_limit_wait

log = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore


# ── Definition loading ─────────────────────────────────────────────────────

def definitions_dir() -> Path:
    """Resolve Cardigann definitions directory.

    Preference order:
      1. CARDIGANN_DEFINITIONS_PATH / settings override (if it exists)
      2. /app/definitions (Docker image layout)
      3. ./definitions relative to repo/CWD (dev)
      4. fallback to the configured path even if missing (empty list)
    """
    from app.config import settings
    configured = Path(
        getattr(settings, "cardigann_definitions_path", None) or "/app/definitions"
    )
    candidates = [
        configured,
        Path("/app/definitions"),
        Path(__file__).resolve().parents[2] / "definitions",  # repo root/definitions
        Path.cwd() / "definitions",
    ]
    for c in candidates:
        try:
            if c.is_dir() and (list(c.glob("*.yml")) or list(c.glob("*.yaml"))):
                return c
        except Exception:
            continue
    return configured


def list_definition_files() -> list[Path]:
    root = definitions_dir()
    if not root.is_dir():
        return []
    files = list(root.glob("*.yml")) + list(root.glob("*.yaml"))
    return sorted(files, key=lambda p: p.name.lower())


def load_definition(path: Path | str) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid definition: {path}")
    if not data.get("id") and not data.get("name"):
        raise ValueError(f"Definition missing id/name: {path}")
    data["_file"] = str(path)
    data.setdefault("id", Path(path).stem)
    data.setdefault("name", data["id"])
    data.setdefault("type", "public")
    data.setdefault("links", [])
    return data


def list_definitions() -> list[dict[str, Any]]:
    out = []
    for f in list_definition_files():
        try:
            d = load_definition(f)
            links = d.get("links") or []
            if isinstance(links, str):
                links = [links]
            settings_fields = []
            for s in (d.get("settings") or []):
                if not isinstance(s, dict):
                    continue
                settings_fields.append({
                    "name": s.get("name") or s.get("type"),
                    "type": s.get("type") or "text",
                    "label": s.get("label") or s.get("name") or "",
                    "default": s.get("default"),
                })
            # common login fields if login block exists but settings empty
            if d.get("login") and not settings_fields:
                method = ((d.get("login") or {}).get("method") or "form").lower()
                if method in ("form", "post"):
                    settings_fields = [
                        {"name": "username", "type": "text", "label": "Username"},
                        {"name": "password", "type": "password", "label": "Password"},
                    ]
                elif method == "cookie":
                    settings_fields = [{"name": "cookie", "type": "text", "label": "Cookie"}]
                elif method in ("apikey", "api"):
                    settings_fields = [{"name": "apikey", "type": "password", "label": "API Key"}]
            out.append({
                "id": d.get("id") or f.stem,
                "name": d.get("name") or f.stem,
                "type": d.get("type") or "public",
                "protocol": "torrent",
                "language": d.get("language"),
                "description": d.get("description") or "",
                "links": links,
                "url": (links[0] if links else ""),
                "urls": links,
                "file": f.name,
                "has_login": bool(d.get("login")),
                "has_search": bool(d.get("search")),
                "settings": settings_fields,
                "source": "cardigann",
            })
        except Exception as e:
            log.warning("Bad Cardigann def %s: %s", f, e)
    return out


def catalog_search(query: str = "", *, privacy: str | None = None) -> list[dict[str, Any]]:
    """Prowlarr-style searchable catalog of available indexers (defs + builtins)."""
    q = (query or "").strip().lower()
    items = list_definitions()
    # builtins as catalog entries too
    try:
        from app.services import builtin_indexers
        for ix in builtin_indexers.list_indexers():
            items.append({
                "id": f"builtin:{ix['id']}",
                "name": ix["name"],
                "type": "public",
                "protocol": "torrent",
                "language": "en",
                "description": f"Built-in public indexer ({', '.join(ix.get('media') or [])})",
                "links": [],
                "url": "",
                "urls": [],
                "file": None,
                "has_login": False,
                "has_search": True,
                "settings": [],
                "source": "builtin",
                "media": ix.get("media") or [],
            })
    except Exception as e:
        log.debug("builtin catalog: %s", e)
    if privacy:
        items = [i for i in items if (i.get("type") or "").lower() == privacy.lower()]
    if q:
        items = [
            i for i in items
            if q in (i.get("name") or "").lower()
            or q in (i.get("id") or "").lower()
            or q in (i.get("description") or "").lower()
        ]
    items.sort(key=lambda x: (x.get("name") or "").lower())
    return items


def get_definition(def_id: str) -> dict[str, Any] | None:
    for f in list_definition_files():
        try:
            d = load_definition(f)
            if d.get("id") == def_id or f.stem == def_id:
                return d
        except Exception:
            continue
    return None


# ── Template engine (minimal Handlebars-like) ──────────────────────────────

_IF_RE = re.compile(
    r"\{\{\s*if\s+\.([^\}]+)\s*\}\}(.*?)\{\{\s*else\s*\}\}(.*?)\{\{\s*end\s*\}\}",
    re.DOTALL,
)
_VAR_RE = re.compile(r"\{\{\s*\.([^\}]+?)\s*\}\}")


def _lookup(ctx: dict[str, Any], path: str) -> Any:
    path = path.strip()
    cur: Any = ctx
    for part in path.split("."):
        part = part.strip()
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return ""
    return cur if cur is not None else ""


def render_template(tpl: str, ctx: dict[str, Any]) -> str:
    if not tpl:
        return ""
    s = str(tpl)

    def _if_sub(m: re.Match) -> str:
        key, a, b = m.group(1), m.group(2), m.group(3)
        val = _lookup(ctx, key)
        return a if val else b

    s = _IF_RE.sub(_if_sub, s)

    def _var_sub(m: re.Match) -> str:
        val = _lookup(ctx, m.group(1))
        return "" if val is None else str(val)

    s = _VAR_RE.sub(_var_sub, s)
    return s


# ── HTTP session + optional login ──────────────────────────────────────────

def _cookie_cache_path(def_id: str) -> Path:
    """Persistent cookie jar under /config (or CWD) so private trackers stay logged in."""
    from app.config import settings
    base = Path(getattr(settings, "config_path", None) or "/config")
    if not base.is_dir():
        base = Path.cwd() / "config"
    base.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", def_id or "unknown")
    return base / f"cardigann_cookies_{safe}.json"


def _load_cookies(client: httpx.Client, def_id: str) -> bool:
    path = _cookie_cache_path(def_id)
    if not path.is_file():
        return False
    try:
        import json
        data = json.loads(path.read_text())
        for c in data:
            client.cookies.set(
                c.get("name", ""),
                c.get("value", ""),
                domain=c.get("domain") or None,
                path=c.get("path") or "/",
            )
        return bool(data)
    except Exception as e:
        log.debug("Cookie load %s: %s", def_id, e)
        return False


def _save_cookies(client: httpx.Client, def_id: str) -> None:
    path = _cookie_cache_path(def_id)
    try:
        import json
        jar = []
        for c in client.cookies.jar:
            jar.append({
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
            })
        path.write_text(json.dumps(jar))
    except Exception as e:
        log.debug("Cookie save %s: %s", def_id, e)


class CardigannSession:
    def __init__(self, definition: dict[str, Any], config: dict[str, str] | None = None):
        self.def_ = definition
        self.config = dict(config or {})
        # sitelink default from first link
        links = definition.get("links") or []
        if links and "sitelink" not in self.config:
            self.config["sitelink"] = links[0].rstrip("/") + "/"
        # Prefer cookie / apikey from config when present (private trackers)
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "mediaos-cardigann/2.11"},
        )
        self._logged_in = False
        def_id = str(definition.get("id") or definition.get("name") or "unknown")
        # Inject explicit cookie string if provided in credentials
        cookie_str = (self.config.get("cookie") or self.config.get("cookies") or "").strip()
        if cookie_str:
            for part in cookie_str.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    self.client.cookies.set(k.strip(), v.strip())
            self._logged_in = True
        elif _load_cookies(self.client, def_id):
            self._logged_in = True  # assume still valid; login_if_needed re-auth on error

    def close(self) -> None:
        try:
            def_id = str(self.def_.get("id") or self.def_.get("name") or "unknown")
            if self._logged_in:
                _save_cookies(self.client, def_id)
        except Exception:
            pass
        self.client.close()

    def base(self) -> str:
        return (self.config.get("sitelink") or (self.def_.get("links") or [""])[0] or "").rstrip("/") + "/"

    def login_if_needed(self) -> None:
        login = self.def_.get("login")
        if not login or self._logged_in:
            return
        method = (login.get("method") or "form").lower()
        # cookie method: credentials already applied in __init__
        if method == "cookie":
            if self.client.cookies.jar:
                self._logged_in = True
                return
            raise RuntimeError(f"Login requires cookie for {self.def_.get('id')}")
        if method in ("apikey", "api"):
            # API key trackers usually put key in search inputs via {{ .Config.apikey }}
            self._logged_in = True
            return
        path = login.get("path") or login.get("target") or ""
        url = urljoin(self.base(), path.lstrip("/"))
        inputs = {}
        for k, v in (login.get("inputs") or {}).items():
            inputs[k] = render_template(str(v), self._ctx(""))
        try:
            if method in ("post", "form"):
                r = self.client.post(url, data=inputs)
            else:
                r = self.client.get(url, params=inputs)
            r.raise_for_status()
            # optional error selector
            err = (login.get("error") or {})
            if err.get("selector") and BeautifulSoup:
                soup = BeautifulSoup(r.text, "lxml")
                if soup.select_one(err["selector"]):
                    raise RuntimeError(f"Login failed ({self.def_.get('id')}): error selector matched")
            self._logged_in = True
            _save_cookies(self.client, str(self.def_.get("id") or "unknown"))
        except Exception as e:
            log.warning("Cardigann login %s: %s", self.def_.get("id"), e)
            raise

    def _ctx(self, keywords: str, *, imdb_id: str | None = None, tmdb_id: str | None = None) -> dict[str, Any]:
        # Cardigann templates use {{ .Query.IMDBID }} / {{ .Query.TMDBID }} on some defs
        q = {
            "Q": keywords,
            "Keywords": keywords,
            "IMDBID": (imdb_id or "").replace("tt", ""),
            "IMDBID_FULL": imdb_id or "",
            "TMDBID": str(tmdb_id or ""),
        }
        return {
            "Keywords": keywords,
            "Query": q,
            "Config": self.config,
        }


    def _get_text(self, url: str) -> str:
        """GET text via CF bypass when available, else session httpx."""
        try:
            from app.clients.cf_bypass import cf_bypass_client
            return cf_bypass_client.get_text(url, timeout=20)
        except Exception:
            r = self.client.get(url, timeout=20, follow_redirects=True)
            r.raise_for_status()
            return r.text

    def search(self, keywords: str, *, limit: int = 40, imdb_id: str | None = None, tmdb_id: str | None = None) -> list[dict[str, Any]]:
        # Per-definition request delay (MediaOs requestdelay parity)
        try:
            delay = float(self.def_.get("requestdelay") or self.def_.get("requestDelay") or 1)
        except Exception:
            delay = 1.0
        rate_limit_wait(self.def_.get("id") or self.base() or "cardigann", delay)
        self.login_if_needed()
        search = self.def_.get("search") or {}
        paths = search.get("paths") or [{"path": "search"}]
        ctx = self._ctx(keywords, imdb_id=imdb_id, tmdb_id=tmdb_id)
        results: list[dict[str, Any]] = []
        for p in paths:
            path_tpl = p.get("path") if isinstance(p, dict) else str(p)
            path = render_template(path_tpl, ctx)
            url = urljoin(self.base(), path.lstrip("/")) if not path.startswith("http") else path
            inputs = {}
            for k, v in (search.get("inputs") or {}).items():
                inputs[k] = render_template(str(v), ctx)
            # merge path-level inputs
            if isinstance(p, dict) and p.get("inputs"):
                for k, v in p["inputs"].items():
                    inputs[k] = render_template(str(v), ctx)

            resp_type = "html"
            if isinstance(p, dict):
                resp_type = ((p.get("response") or {}).get("type") or "html").lower()

            try:
                method = (search.get("method") or "get").lower()
                if method == "post":
                    r = self.client.post(url, data=inputs)
                else:
                    r = self.client.get(url, params=inputs)
                r.raise_for_status()
            except Exception as e:
                log.warning("Cardigann search request failed %s: %s", url, e)
                continue

            if resp_type == "json":
                try:
                    data = r.json()
                except Exception:
                    continue
                results.extend(self._parse_json(data, search, keywords))
            else:
                results.extend(self._parse_html(r.text, search, keywords))
            if len(results) >= limit:
                break
        # normalize
        out = []
        seen = set()
        for row in results[:limit]:
            title = (row.get("title") or "").strip()
            dl = row.get("magnet") or row.get("download") or row.get("download_url") or ""
            details = row.get("details") or ""
            if not title:
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            if dl and (dl.startswith("/") or (not dl.startswith("http") and not dl.startswith("magnet:"))):
                dl = urljoin(self.base(), dl.lstrip("/"))
            if details and (details.startswith("/") or (not str(details).startswith("http"))):
                details = urljoin(self.base(), str(details).lstrip("/"))
            # Two-stage magnet: follow details/download page when result isn't a magnet yet
            if dl and not str(dl).startswith("magnet:") and (
                str(dl).startswith("http") or details
            ):
                follow = details if details else dl
                try:
                    rate_limit_wait((self.def_.get("id") or "cardigann") + ":detail", 0.5)
                    html = self._get_text(follow)
                    mm = re.search(r'href=["\'](magnet:\?xt=urn:btih:[^"\']+)["\']', html, re.I)
                    if not mm:
                        mm = re.search(r'(magnet:\?xt=urn:btih:[A-Za-z0-9]+[^\s"\']*)', html, re.I)
                    if mm:
                        dl = mm.group(1).replace("&amp;", "&")
                except Exception:
                    pass
            if not dl:
                continue
            out.append({
                "title": title[:300],
                "download_url": dl,
                "magnet": dl if str(dl).startswith("magnet:") else row.get("magnet"),
                "size": row.get("size"),
                "seeders": _to_int(row.get("seeders")),
                "peers": _to_int(row.get("leechers") or row.get("peers")),
                "info_hash": (row.get("infohash") or row.get("info_hash") or "").lower() or None,
                "protocol": "torrent",
                "indexer": self.def_.get("name") or self.def_.get("id"),
                "details": row.get("details"),
            })
        return out

    def _parse_html(self, html: str, search: dict, keywords: str) -> list[dict]:
        if not BeautifulSoup:
            log.warning("beautifulsoup4 not installed — cannot parse HTML Cardigann results")
            return []
        soup = BeautifulSoup(html, "lxml")
        rows_cfg = search.get("rows") or {}
        selector = rows_cfg.get("selector") or "tr"
        nodes = soup.select(selector)
        fields = search.get("fields") or {}
        out = []
        for node in nodes:
            row = {}
            for name, fcfg in fields.items():
                if not isinstance(fcfg, dict):
                    continue
                row[name] = _extract_field(node, fcfg, self.base())
            out.append(row)
        return out

    def _parse_json(self, data: Any, search: dict, keywords: str) -> list[dict]:
        rows_cfg = search.get("rows") or {}
        selector = rows_cfg.get("selector") or ""
        items = _json_path(data, selector) if selector else data
        if not isinstance(items, list):
            items = [items] if items else []
        fields = search.get("fields") or {}
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            # optional nested torrents array (YTS-style multiple)
            if rows_cfg.get("multiple") and rows_cfg.get("attribute"):
                nested = item.get(rows_cfg["attribute"]) or []
                for n in nested:
                    row = dict(item)
                    if isinstance(n, dict):
                        row.update(n)
                    out.append(_json_fields(row, fields, self.base()))
            else:
                out.append(_json_fields(item, fields, self.base()))
        return out


def _extract_field(node, fcfg: dict, base: str) -> str:
    if "text" in fcfg and "selector" not in fcfg:
        return render_template(str(fcfg["text"]), {"Result": {}, "Config": {"sitelink": base}})
    sel = fcfg.get("selector")
    if not sel:
        return str(fcfg.get("text") or "")
    el = node.select_one(sel) if hasattr(node, "select_one") else None
    if el is None:
        return ""
    attr = fcfg.get("attribute")
    if attr:
        val = el.get(attr) or ""
    else:
        val = el.get_text(" ", strip=True)
    for filt in fcfg.get("filters") or []:
        val = _apply_filter(val, filt)
    return val


def _json_fields(item: dict, fields: dict, base: str) -> dict:
    row = {}
    for name, fcfg in fields.items():
        if not isinstance(fcfg, dict):
            continue
        if "text" in fcfg and "selector" not in fcfg:
            row[name] = render_template(str(fcfg["text"]), {"Result": item, "Config": {"sitelink": base}})
            continue
        sel = fcfg.get("selector") or ""
        # support ..parent style lightly — treat as key path
        sel = sel.lstrip(".")
        val = _json_path(item, sel) if sel else ""
        if val is None:
            val = ""
        if not isinstance(val, str):
            val = str(val)
        for filt in fcfg.get("filters") or []:
            val = _apply_filter(val, filt)
        row[name] = val
    return row


def _json_path(data: Any, path: str) -> Any:
    if not path:
        return data
    cur = data
    for part in path.replace("[", ".").replace("]", "").split("."):
        part = part.strip()
        if not part:
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            idx = int(part)
            cur = cur[idx] if idx < len(cur) else None
        else:
            return None
    return cur


def _apply_filter(val: str, filt: dict) -> str:
    name = (filt.get("name") or "").lower()
    args = filt.get("args")
    if name == "querystring":
        # extract query param from URL
        from urllib.parse import parse_qs, urlparse
        key = args if isinstance(args, str) else (args[0] if args else "")
        qs = parse_qs(urlparse(val).query)
        return (qs.get(key) or [""])[0]
    if name == "regexp" or name == "re_replace":
        if isinstance(args, list) and len(args) >= 2:
            return re.sub(args[0], args[1], val)
        if isinstance(args, list) and len(args) == 1:
            m = re.search(args[0], val)
            return m.group(1) if m and m.lastindex else (m.group(0) if m else "")
    if name == "trim":
        return val.strip()
    if name == "toupper":
        return val.upper()
    if name == "tolower":
        return val.lower()
    if name == "append" and args:
        return val + str(args[0] if isinstance(args, list) else args)
    if name == "prepend" and args:
        return str(args[0] if isinstance(args, list) else args) + val
    if name == "replace" and isinstance(args, list) and len(args) >= 2:
        return val.replace(str(args[0]), str(args[1]))
    return val


def _to_int(v) -> int | None:
    if v is None:
        return None
    s = re.sub(r"[^\d]", "", str(v))
    return int(s) if s.isdigit() else None


# ── Public API used by search pipeline ─────────────────────────────────────

def search_definition(
    def_id: str,
    query: str,
    *,
    config: dict[str, str] | None = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    d = get_definition(def_id)
    if not d:
        return []
    sess = CardigannSession(d, config=config)
    try:
        return sess.search(query, limit=limit)
    finally:
        sess.close()


def search_all_cardigann(
    query: str,
    *,
    configs: dict[str, dict[str, str]] | None = None,
    limit_per: int = 20,
    public_only: bool = False,
) -> list[dict[str, Any]]:
    """Fan-out across all loaded definitions concurrently.

    Each definition's site gets its own small concurrency cap via
    rate_limit.acquire_host so a slow/private tracker can't be hammered
    just because several queries land at once; one definition failing
    never blocks the others.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from urllib.parse import urlparse
    from app.config import settings
    from app.services import rate_limit
    if not getattr(settings, "cardigann_enabled", True):
        return []
    configs = configs or {}
    metas = []
    for meta in list_definitions():
        if public_only and meta.get("type") not in ("public", None, "semi-private"):
            continue
        metas.append(meta)
    if not metas:
        return []

    def _one(meta):
        def_id = meta["id"]
        host = urlparse(meta.get("url") or "").netloc or def_id
        if not rate_limit.acquire_host(host, timeout=15.0):
            log.debug("Cardigann %s: host busy, skipped", def_id)
            return []
        try:
            cfg = (configs or {}).get(def_id) or load_def_config(def_id)
            return search_definition(def_id, query, config=cfg, limit=limit_per)
        except Exception as e:
            log.debug("Cardigann %s: %s", def_id, e)
            return []
        finally:
            rate_limit.release_host(host)

    out: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(16, len(metas))) as pool:
        futs = [pool.submit(_one, meta) for meta in metas]
        for fut in as_completed(futs):
            out.extend(fut.result())
    return out



def _config_setting_key(def_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", def_id or "unknown")
    return f"cardigann_config_{safe}"


def load_def_config(def_id: str, db=None) -> dict[str, str]:
    """Load saved username/password/cookie/apikey for a definition."""
    import json
    key = _config_setting_key(def_id)
    # try DB AppSetting
    try:
        if db is None:
            from app.database import SessionLocal
            db = SessionLocal()
            close = True
        else:
            close = False
        try:
            from app.models import AppSetting
            row = db.get(AppSetting, key)
            if row and row.value:
                data = json.loads(row.value)
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items() if v is not None}
        finally:
            if close:
                db.close()
    except Exception as e:
        log.debug("load_def_config: %s", e)
    return {}


def save_def_config(def_id: str, config: dict[str, str], db=None) -> dict[str, str]:
    import json
    key = _config_setting_key(def_id)
    clean = {str(k): str(v) for k, v in (config or {}).items() if v is not None and str(v) != ""}
    close = False
    if db is None:
        from app.database import SessionLocal
        db = SessionLocal()
        close = True
    try:
        from app.models import AppSetting
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=json.dumps(clean)))
        else:
            # merge — keep existing secrets if new value is blank/masked
            try:
                old = json.loads(row.value or "{}")
            except Exception:
                old = {}
            for k, v in clean.items():
                if v in ("••••••••", "__SET__"):
                    continue
                old[k] = v
            row.value = json.dumps(old)
            clean = old
        db.commit()
    finally:
        if close:
            db.close()
    return clean


def search_definition_with_saved(def_id: str, query: str, *, limit: int = 40, db=None) -> list[dict]:
    cfg = load_def_config(def_id, db=db)
    return search_definition(def_id, query, config=cfg, limit=limit)
