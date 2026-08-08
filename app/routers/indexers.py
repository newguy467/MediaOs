from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_admin, require_permission
from app.clients.torznab import torznab_client
from app.database import get_db
from app.models import Indexer
from app.services import cardigann as cardigann_svc

router = APIRouter(prefix="/indexers", tags=["indexers"])


class IndexerIn(BaseModel):
    name: str
    url: str = ""
    api_key: str | None = None
    kind: str = "torznab"  # torznab | newznab | cardigann | builtin
    enabled: bool = True
    categories: str | None = None
    use_flaresolverr: bool = False
    priority: int = 25
    cardigann_id: str | None = None  # definition id when kind=cardigann
    credentials: dict | None = None


class IndexerOut(BaseModel):
    id: int
    name: str
    url: str
    kind: str
    enabled: bool
    categories: str | None
    use_flaresolverr: bool
    priority: int
    last_ok_at: datetime | None
    last_error: str | None
    has_api_key: bool = False

    class Config:
        from_attributes = True


def _out(row: Indexer) -> IndexerOut:
    return IndexerOut(
        id=row.id,
        name=row.name,
        url=row.url,
        kind=row.kind,
        enabled=row.enabled,
        categories=row.categories,
        use_flaresolverr=row.use_flaresolverr,
        priority=row.priority,
        last_ok_at=row.last_ok_at,
        last_error=row.last_error,
        has_api_key=bool(row.api_key),
    )


@router.get("", response_model=list[IndexerOut])
def list_indexers(db: Session = Depends(get_db)):
    return [_out(r) for r in db.query(Indexer).order_by(Indexer.priority, Indexer.name).all()]


@router.get("/catalog")
def indexer_catalog(q: str = "", privacy: str | None = None):
    """Prowlarr-style searchable list of indexers you can add (Cardigann + builtins)."""
    return cardigann_svc.catalog_search(q, privacy=privacy)


@router.get("/catalog/{def_id}")
def catalog_detail(def_id: str):
    """Definition detail with preconfigured URLs and settings fields (like Prowlarr add form)."""
    if def_id.startswith("builtin:"):
        bid = def_id.split(":", 1)[1]
        from app.services import builtin_indexers
        for ix in builtin_indexers.list_indexers():
            if ix["id"] == bid:
                return {
                    "id": def_id,
                    "name": ix["name"],
                    "type": "public",
                    "protocol": "torrent",
                    "url": "",
                    "urls": [],
                    "settings": [],
                    "source": "builtin",
                    "has_login": False,
                    "description": "Built-in public indexer",
                }
        raise HTTPException(404, "Builtin not found")
    d = cardigann_svc.get_definition(def_id)
    if not d:
        # try by scanning list
        for meta in cardigann_svc.list_definitions():
            if meta["id"] == def_id:
                return meta
        raise HTTPException(404, "Definition not found")
    links = d.get("links") or []
    if isinstance(links, str):
        links = [links]
    settings_fields = []
    for s in (d.get("settings") or []):
        if isinstance(s, dict):
            settings_fields.append({
                "name": s.get("name") or s.get("type"),
                "type": s.get("type") or "text",
                "label": s.get("label") or s.get("name") or "",
                "default": s.get("default"),
            })
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
    return {
        "id": d.get("id") or def_id,
        "name": d.get("name") or def_id,
        "type": d.get("type") or "public",
        "protocol": "torrent",
        "description": d.get("description") or "",
        "language": d.get("language"),
        "url": links[0] if links else "",
        "urls": links,
        "settings": settings_fields,
        "has_login": bool(d.get("login")),
        "source": "cardigann",
    }


class AddFromCatalogIn(BaseModel):
    def_id: str
    name: str | None = None
    url: str | None = None  # chosen site URL from preconfigured list
    enabled: bool = True
    priority: int = 25
    use_flaresolverr: bool = False
    # credentials
    username: str | None = None
    password: str | None = None
    cookie: str | None = None
    api_key: str | None = None
    extra: dict | None = None


@router.post("/catalog/add", response_model=IndexerOut)
def add_from_catalog(payload: AddFromCatalogIn, db: Session = Depends(get_db), _: str = Depends(require_permission("indexers", "settings"))):
    """Add an indexer from the catalog (Cardigann def or builtin) with preconfigured URL."""
    import json
    def_id = payload.def_id
    detail = catalog_detail(def_id)
    name = (payload.name or detail.get("name") or def_id).strip()
    if db.query(Indexer).filter(Indexer.name == name).first():
        raise HTTPException(409, f"Indexer already added: {name}")

    # pick URL: user choice → first preconfigured link
    urls = detail.get("urls") or []
    url = (payload.url or "").strip() or (urls[0] if urls else "") or f"cardigann://{def_id}"

    if def_id.startswith("builtin:"):
        kind = "builtin"
        cardigann_ref = def_id
    else:
        kind = "cardigann"
        cardigann_ref = detail.get("id") or def_id

    creds = {}
    for k in ("username", "password", "cookie", "api_key"):
        v = getattr(payload, k, None)
        if v:
            creds[k] = v
    if payload.extra:
        creds.update({str(k): str(v) for k, v in payload.extra.items() if v is not None})
    if "api_key" in creds and "apikey" not in creds:
        creds["apikey"] = creds["api_key"]
    creds["cardigann_id"] = cardigann_ref
    if url and url.startswith("http"):
        creds["sitelink"] = url.rstrip("/") + "/"

    row = Indexer(
        name=name,
        url=url or f"cardigann://{cardigann_ref}",
        api_key=creds.get("api_key") or creds.get("apikey"),
        kind=kind,
        enabled=payload.enabled,
        use_flaresolverr=payload.use_flaresolverr,
        priority=payload.priority,
        credentials_json=json.dumps(creds) if creds else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # also persist cardigann def config for search pipeline
    if kind == "cardigann":
        try:
            cardigann_svc.save_def_config(cardigann_ref, creds, db=db)
        except Exception:
            pass

    return _out(row)


@router.post("/{indexer_id}/test-search")
def test_indexer_search(indexer_id: int, query: str = "ubuntu", db: Session = Depends(get_db)):
    """Test search on an enabled indexer row (Prowlarr-style Test)."""
    from datetime import datetime, timezone
    row = db.get(Indexer, indexer_id)
    if not row:
        raise HTTPException(404, "Not found")
    import json
    creds = {}
    if row.credentials_json:
        try:
            creds = json.loads(row.credentials_json)
        except Exception:
            pass
    results = []
    error = None
    try:
        if row.kind == "cardigann":
            def_id = creds.get("cardigann_id") or row.name
            results = cardigann_svc.search_definition(def_id, query, config=creds, limit=10)
        elif row.kind == "builtin":
            from app.services import builtin_indexers
            bid = (creds.get("cardigann_id") or "").replace("builtin:", "") or row.name.lower()
            results = builtin_indexers.search(bid, query, limit=10)
        else:
            # torznab
            results = torznab_client.search(row.url, query=query, apikey=row.api_key, limit=10)
        row.last_ok_at = datetime.now(timezone.utc)
        row.last_error = None
        db.add(row)
        db.commit()
        return {"ok": True, "count": len(results), "sample": [
            {"title": r.get("title"), "seeders": r.get("seeders"), "size": r.get("size")}
            for r in results[:5]
        ]}
    except Exception as e:
        error = str(e)
        row.last_error = error[:500]
        db.add(row)
        db.commit()
        return {"ok": False, "error": error, "count": 0}




@router.post("", response_model=IndexerOut)
def add_indexer(payload: IndexerIn, db: Session = Depends(get_db), _: str = Depends(require_permission("indexers", "settings"))):
    if db.query(Indexer).filter(Indexer.name == payload.name).first():
        raise HTTPException(409, "Name taken")
    row = Indexer(
        name=payload.name,
        url=payload.url,
        api_key=payload.api_key,
        kind=payload.kind,
        enabled=payload.enabled,
        categories=payload.categories,
        use_flaresolverr=payload.use_flaresolverr,
        priority=payload.priority,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.put("/{indexer_id}", response_model=IndexerOut)
def update_indexer(
    indexer_id: int,
    payload: IndexerIn,
    db: Session = Depends(get_db),
    _: str = Depends(require_permission("indexers", "settings")),
):
    row = db.get(Indexer, indexer_id)
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in payload.model_dump().items():
        if k == "api_key" and (v is None or v == ""):
            continue  # keep existing key
        setattr(row, k, v)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/{indexer_id}", status_code=204)
def delete_indexer(indexer_id: int, db: Session = Depends(get_db), _: str = Depends(require_permission("indexers", "settings"))):
    row = db.get(Indexer, indexer_id)
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row)
    db.commit()


@router.post("/{indexer_id}/test")
def test_indexer(indexer_id: int, db: Session = Depends(get_db), _: str = Depends(require_permission("indexers", "settings"))):
    row = db.get(Indexer, indexer_id)
    if not row:
        raise HTTPException(404, "Not found")
    try:
        caps = torznab_client.caps(row.url, row.api_key)
        sample = torznab_client.search(
            row.url,
            query="linux",
            api_key=row.api_key,
            categories=row.categories,
            limit=3,
            use_flaresolverr=row.use_flaresolverr,
        )
        row.last_ok_at = datetime.now(timezone.utc)
        row.last_error = None
        db.add(row)
        db.commit()
        return {"ok": True, "caps": caps, "sample_count": len(sample), "sample": sample[:3]}
    except Exception as exc:
        row.last_error = str(exc)[:500]
        db.add(row)
        db.commit()
        return {"ok": False, "error": str(exc)}


@router.get("/builtin")
def builtin_indexers():
    from app.services.builtin_indexers import list_indexers
    return list_indexers()


@router.get("/builtin/search")
def builtin_search(q: str, indexer: str | None = None, media: str | None = None, limit: int = 20):
    from app.services.builtin_indexers import search, search_all
    if indexer:
        return search(indexer, q, limit=limit)
    return search_all(q, media=media, limit=limit)



# ── Cardigann YAML definitions ─────────────────────────────────────────────

@router.get("/cardigann")
def list_cardigann_defs():
    """List loaded Cardigann/Jackett YAML definitions."""
    return cardigann_svc.list_definitions()


@router.post("/cardigann/sync")
def sync_cardigann_definitions(priority_only: bool = False, force: bool = True):
    """Pull Jackett YAML definitions into the local definitions path (automatic for installs)."""
    from app.services.definition_sync import sync_definitions, ensure_seed_definitions
    if priority_only:
        return ensure_seed_definitions()
    return sync_definitions(force=force)


@router.get("/cardigann/sync/status")
def cardigann_sync_status():
    from pathlib import Path as P
    from app.services.cardigann import definitions_dir, list_definition_files
    root = definitions_dir()
    files = list_definition_files()
    return {
        "path": str(root),
        "count": len(files),
        "sample": [f.name for f in files[:15]],
    }



@router.get("/cardigann/{def_id}")
def get_cardigann_def(def_id: str):
    d = cardigann_svc.get_definition(def_id)
    if not d:
        raise HTTPException(404, "Definition not found")
    # strip heavy internal bits for API
    return {
        "id": d.get("id"),
        "name": d.get("name"),
        "type": d.get("type"),
        "description": d.get("description"),
        "language": d.get("language"),
        "links": d.get("links"),
        "has_login": bool(d.get("login")),
        "settings": d.get("settings") or [],
        "file": d.get("_file"),
    }


@router.get("/cardigann/{def_id}/search")
def search_cardigann(def_id: str, query: str, limit: int = 40, db: Session = Depends(get_db)):
    if not query.strip():
        return []
    try:
        return cardigann_svc.search_definition_with_saved(def_id, query, limit=limit, db=db)
    except Exception as exc:
        raise HTTPException(502, f"Cardigann search failed: {exc}")


@router.post("/cardigann/reload")
def reload_cardigann(_: str = Depends(require_permission("indexers", "settings"))):
    """Rescan definitions directory (no-op cache; files are read each call)."""
    defs = cardigann_svc.list_definitions()
    return {"count": len(defs), "definitions": [d["id"] for d in defs]}




@router.get("/cardigann/{def_id}/config")
def get_cardigann_config(def_id: str, db: Session = Depends(get_db), _: str = Depends(require_permission("indexers", "settings"))):
    """Return which credential keys are set (values masked)."""
    cfg = cardigann_svc.load_def_config(def_id, db=db)
    return {
        "id": def_id,
        "keys": list(cfg.keys()),
        "has_credentials": bool(cfg),
        "fields": {k: ("••••••••" if k.lower() in ("password", "cookie", "cookies", "apikey", "api_key") else v) for k, v in cfg.items()},
    }


@router.put("/cardigann/{def_id}/config")
def set_cardigann_config(def_id: str, payload: CredentialsIn, db: Session = Depends(get_db), _: str = Depends(require_permission("indexers", "settings"))):
    """Save login credentials for a Cardigann definition."""
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    # flatten extra
    if payload.extra:
        data.update({k: str(v) for k, v in payload.extra.items() if v is not None})
    # map api_key -> apikey for templates
    if "api_key" in data and "apikey" not in data:
        data["apikey"] = data["api_key"]
    saved = cardigann_svc.save_def_config(def_id, data, db=db)
    return {"ok": True, "id": def_id, "keys": list(saved.keys())}


@router.post("/cardigann/{def_id}/test-login")
def test_cardigann_login(def_id: str, db: Session = Depends(get_db), _: str = Depends(require_permission("indexers", "settings"))):
    """Attempt login with saved credentials."""
    d = cardigann_svc.get_definition(def_id)
    if not d:
        raise HTTPException(404, "Definition not found")
    cfg = cardigann_svc.load_def_config(def_id, db=db)
    sess = cardigann_svc.CardigannSession(d, config=cfg)
    try:
        sess.login_if_needed()
        return {"ok": True, "id": def_id, "logged_in": sess._logged_in}
    except Exception as e:
        return {"ok": False, "id": def_id, "error": str(e)}
    finally:
        sess.close()


@router.get("/jackett/status")
def jackett_status():
    from app.clients.jackett import jackett_client
    from app.config import settings
    return {
        "configured": jackett_client.enabled(),
        "url": getattr(settings, "jackett_url", "") or None,
        "test": jackett_client.test() if jackett_client.enabled() else {"ok": False, "error": "not configured"},
    }


@router.post("/jackett/sync")
def jackett_sync(
    enable_new: bool = True,
    db: Session = Depends(get_db),
    _: str = Depends(require_permission("indexers", "settings")),
):
    """Pull Jackett configured indexers into mediaos Indexer (Torznab) rows."""
    from app.services.jackett_sync import sync_jackett_indexers
    return sync_jackett_indexers(db, enable_new=enable_new)


class CredentialsIn(BaseModel):
    username: str | None = None
    password: str | None = None
    cookie: str | None = None
    api_key: str | None = None
    extra: dict | None = None


@router.put("/{indexer_id}/credentials")
def set_credentials(indexer_id: int, payload: CredentialsIn, db: Session = Depends(get_db), _: str = Depends(require_permission("indexers", "settings"))):
    """Store private-tracker login/cookie/API key for an indexer row (Cardigann/Torznab)."""
    import json
    row = db.get(Indexer, indexer_id)
    if not row:
        raise HTTPException(404, "Indexer not found")
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    row.credentials_json = json.dumps(data)
    if payload.api_key:
        row.api_key = payload.api_key
    db.add(row)
    db.commit()
    return {"ok": True, "id": row.id, "has_credentials": True}


@router.get("/{indexer_id}/credentials")
def get_credentials_meta(indexer_id: int, db: Session = Depends(get_db), _: str = Depends(require_permission("indexers", "settings"))):
    import json
    row = db.get(Indexer, indexer_id)
    if not row:
        raise HTTPException(404, "Indexer not found")
    keys = []
    if row.credentials_json:
        try:
            keys = list(json.loads(row.credentials_json).keys())
        except Exception:
            keys = ["(invalid json)"]
    return {"id": row.id, "name": row.name, "keys": keys, "has_api_key": bool(row.api_key)}
