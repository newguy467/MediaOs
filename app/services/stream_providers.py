"""Multi stream providers with circuit-breaker failover (MediaOs-style)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

from app.clients.realdebrid import rd_client
from app.config import settings

log = logging.getLogger(__name__)


@dataclass
class ProviderState:
    name: str
    failures: int = 0
    open_until: float = 0.0
    last_error: str = ""

    def available(self) -> bool:
        return time.time() >= self.open_until

    def record_success(self):
        self.failures = 0
        self.open_until = 0.0
        self.last_error = ""

    def record_failure(self, err: str, threshold: int = 3, cooldown: float = 300):
        self.failures += 1
        self.last_error = err
        if self.failures >= threshold:
            self.open_until = time.time() + cooldown
            log.warning("Circuit OPEN for %s until %s (%s)", self.name, self.open_until, err)


_states: dict[str, ProviderState] = {}


def _state(name: str) -> ProviderState:
    if name not in _states:
        _states[name] = ProviderState(name=name)
    return _states[name]


@dataclass
class StreamResult:
    provider: str
    url: str
    kind: str  # strm | direct | debrid | magnet


def providers() -> list[dict]:
    return [
        {"id": "realdebrid", "name": "Real-Debrid", "enabled": rd_client.enabled()},
        {"id": "torbox", "name": "TorBox", "enabled": bool(getattr(settings, "torbox_api_key", ""))},
        {"id": "alldebrid", "name": "AllDebrid", "enabled": bool(getattr(settings, "alldebrid_api_key", ""))},
        {"id": "premiumize", "name": "Premiumize", "enabled": bool(getattr(settings, "premiumize_api_key", ""))},
        {"id": "debridlink", "name": "Debrid-Link", "enabled": bool(getattr(settings, "debridlink_api_key", ""))},
        {"id": "putio", "name": "Put.io", "enabled": bool(getattr(settings, "putio_token", ""))},
        {"id": "easydebrid", "name": "EasyDebrid", "enabled": bool(getattr(settings, "easydebrid_api_key", ""))},
        {"id": "offcloud", "name": "Offcloud", "enabled": bool(getattr(settings, "offcloud_api_key", ""))},
        {"id": "magnet_strm", "name": "Magnet .strm", "enabled": True},
        {"id": "direct_url", "name": "Direct HTTP URL", "enabled": True},
    ]


def _try_rd(magnet: str) -> str | None:
    if not rd_client.enabled():
        return None
    return rd_client.best_stream_link(magnet)




def _try_alldebrid(magnet: str) -> str | None:
    """AllDebrid magnet upload → status poll → unlock link."""
    key = getattr(settings, "alldebrid_api_key", "") or ""
    if not key:
        return None
    import time
    import httpx

    r = httpx.get(
        "https://api.alldebrid.com/v4/magnet/upload",
        params={"agent": "mediaos", "apikey": key, "magnets[]": magnet},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "success":
        raise RuntimeError(data.get("error") or "alldebrid upload failed")
    magnets = (data.get("data") or {}).get("magnets") or []
    if not magnets:
        return None
    mid = magnets[0].get("id") or magnets[0].get("magnet")
    if not mid:
        return None
    # poll status
    for _ in range(12):
        sr = httpx.get(
            "https://api.alldebrid.com/v4/magnet/status",
            params={"agent": "mediaos", "apikey": key, "id": mid},
            timeout=20,
        )
        sr.raise_for_status()
        sd = sr.json()
        mag = (sd.get("data") or {}).get("magnets") or (sd.get("data") or {})
        if isinstance(mag, list):
            mag = mag[0] if mag else {}
        status = (mag.get("status") or mag.get("statusCode") or "").__str__().lower()
        links = mag.get("links") or mag.get("files") or []
        if links and ("ready" in status or status in ("4", "downloaded", "ready")):
            link = links[0]
            if isinstance(link, dict):
                link = link.get("link") or link.get("download") or link.get("url")
            if not link:
                break
            # unlock
            ur = httpx.get(
                "https://api.alldebrid.com/v4/link/unlock",
                params={"agent": "mediaos", "apikey": key, "link": link},
                timeout=30,
            )
            ur.raise_for_status()
            ud = ur.json()
            if ud.get("status") == "success":
                return (ud.get("data") or {}).get("link") or (ud.get("data") or {}).get("download")
            return link
        time.sleep(2)
    return None


def _try_premiumize(magnet: str) -> str | None:
    """Premiumize directdl / transfer create."""
    key = getattr(settings, "premiumize_api_key", "") or ""
    if not key:
        return None
    import httpx

    # direct download endpoint for magnet
    r = httpx.post(
        "https://www.premiumize.me/api/transfer/directdl",
        data={"apikey": key, "src": magnet},
        timeout=60,
    )
    if r.status_code == 200:
        data = r.json()
        if data.get("status") == "success":
            loc = data.get("location") or data.get("content")
            if isinstance(loc, list) and loc:
                item = loc[0]
                return item.get("stream_link") or item.get("link") or item.get("path")
            if isinstance(loc, str):
                return loc
    # fallback: create transfer
    r2 = httpx.post(
        "https://www.premiumize.me/api/transfer/create",
        data={"apikey": key, "src": magnet},
        timeout=30,
    )
    r2.raise_for_status()
    data2 = r2.json()
    if data2.get("status") != "success":
        raise RuntimeError(data2.get("message") or "premiumize create failed")
    tid = data2.get("id")
    if not tid:
        return None
    import time
    for _ in range(15):
        lr = httpx.get(
            "https://www.premiumize.me/api/transfer/list",
            params={"apikey": key},
            timeout=20,
        )
        lr.raise_for_status()
        transfers = (lr.json() or {}).get("transfers") or []
        for t in transfers:
            if str(t.get("id")) == str(tid) and t.get("status") == "finished":
                return t.get("stream_link") or t.get("download_link") or t.get("folder_id")
        time.sleep(2)
    return None


def _try_debridlink(magnet: str) -> str | None:
    key = getattr(settings, "debridlink_api_key", "") or ""
    if not key:
        return None
    import httpx, time
    r = httpx.post(
        "https://debrid-link.com/api/v2/seedbox/add",
        headers={"Authorization": f"Bearer {key}"},
        data={"url": magnet, "structureType": "1"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(data.get("error") or "debridlink add failed")
    value = data.get("value") or {}
    tid = value.get("id")
    if not tid:
        return None
    for _ in range(12):
        ir = httpx.get(
            f"https://debrid-link.com/api/v2/seedbox/list",
            headers={"Authorization": f"Bearer {key}"},
            params={"ids": tid},
            timeout=20,
        )
        ir.raise_for_status()
        items = (ir.json() or {}).get("value") or []
        for it in items:
            if str(it.get("id")) == str(tid):
                files = it.get("files") or []
                for f in files:
                    dl = f.get("downloadLink") or f.get("download") or f.get("link")
                    if dl:
                        return dl
        time.sleep(2)
    return None


def _try_torbox(magnet: str) -> str | None:
    key = getattr(settings, "torbox_api_key", "") or ""
    if not key:
        return None
    import httpx, time
    headers = {"Authorization": f"Bearer {key}"}
    r = httpx.post(
        "https://api.torbox.app/v1/api/torrents/createtorrent",
        headers=headers,
        data={"magnet": magnet, "seed": 1},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(data.get("error") or "torbox create failed")
    tid = (data.get("data") or {}).get("torrent_id") or (data.get("data") or {}).get("id")
    if not tid:
        return None
    for _ in range(15):
        lr = httpx.get(
            "https://api.torbox.app/v1/api/torrents/mylist",
            headers=headers,
            timeout=20,
        )
        lr.raise_for_status()
        items = (lr.json() or {}).get("data") or []
        for it in items:
            if str(it.get("id")) == str(tid) or str(it.get("torrent_id")) == str(tid):
                if it.get("download_finished") or it.get("download_state") == "completed":
                    files = it.get("files") or []
                    # request download link for first file
                    fid = 0
                    if files:
                        fid = files[0].get("id") or 0
                    dr = httpx.get(
                        "https://api.torbox.app/v1/api/torrents/requestdl",
                        headers=headers,
                        params={"token": key, "torrent_id": tid, "file_id": fid},
                        timeout=30,
                    )
                    if dr.status_code == 200:
                        dd = dr.json()
                        return (dd.get("data") or dd.get("download_url") or
                                (dd.get("data") if isinstance(dd.get("data"), str) else None))
        time.sleep(2)
    return None




def _try_putio(magnet: str) -> str | None:
    """Add magnet to put.io, wait for completion, pick best file when multi-file."""
    token = getattr(settings, "putio_token", "") or ""
    if not token:
        return None
    import httpx, time
    headers = {"Authorization": f"Bearer {token}"}
    r = httpx.post(
        "https://api.put.io/v2/transfers/add",
        headers=headers,
        data={"url": magnet},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    tid = (data.get("transfer") or {}).get("id")
    if not tid:
        raise RuntimeError(data.get("error_message") or "put.io add failed")

    MEDIA_EXT = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".m2ts", ".ts",
                 ".cbz", ".cbr", ".pdf", ".epub", ".m4b", ".mp3", ".flac"}

    def _download_link(file_id: int) -> str | None:
        fr = httpx.get(
            f"https://api.put.io/v2/files/{file_id}/download",
            headers=headers,
            timeout=20,
            follow_redirects=False,
        )
        if fr.status_code in (301, 302, 303, 307, 308):
            return fr.headers.get("Location")
        try:
            jd = fr.json()
            return (
                jd.get("download_link")
                or jd.get("link")
                or (jd.get("file") or {}).get("download_url")
            )
        except Exception:
            return None

    def _best_file_id(root_id: int) -> int | None:
        """Walk put.io folder tree; pick largest media file (or largest overall)."""
        lr = httpx.get(
            "https://api.put.io/v2/files/list",
            headers=headers,
            params={"parent_id": root_id},
            timeout=20,
        )
        lr.raise_for_status()
        files = (lr.json() or {}).get("files") or []
        candidates = []
        folders = []
        for f in files:
            fid = f.get("id")
            if not fid:
                continue
            if f.get("content_type") == "application/x-directory" or f.get("file_type") == "FOLDER":
                folders.append(fid)
                continue
            name = (f.get("name") or "").lower()
            size = int(f.get("size") or 0)
            is_media = any(name.endswith(ext) for ext in MEDIA_EXT)
            candidates.append((is_media, size, fid))
        # recurse one level of folders if no media at root
        if not any(c[0] for c in candidates):
            for fid in folders[:8]:
                try:
                    sub = httpx.get(
                        "https://api.put.io/v2/files/list",
                        headers=headers,
                        params={"parent_id": fid},
                        timeout=20,
                    )
                    sub.raise_for_status()
                    for f in (sub.json() or {}).get("files") or []:
                        name = (f.get("name") or "").lower()
                        size = int(f.get("size") or 0)
                        is_media = any(name.endswith(ext) for ext in MEDIA_EXT)
                        if f.get("id"):
                            candidates.append((is_media, size, f["id"]))
                except Exception:
                    continue
        if not candidates:
            return root_id
        # prefer media, then largest size
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return candidates[0][2]

    for _ in range(25):
        ir = httpx.get(f"https://api.put.io/v2/transfers/{tid}", headers=headers, timeout=20)
        ir.raise_for_status()
        tr = (ir.json() or {}).get("transfer") or {}
        status = (tr.get("status") or "").lower()
        if status in ("completed", "seeding"):
            file_id = tr.get("file_id")
            if not file_id:
                return None
            best = _best_file_id(int(file_id))
            return _download_link(int(best or file_id))
        if status in ("error", "canceled"):
            raise RuntimeError(tr.get("error_message") or "put.io transfer error")
        time.sleep(2)
    return None



def _try_easydebrid(magnet: str) -> str | None:
    key = getattr(settings, "easydebrid_api_key", "") or ""
    if not key:
        return None
    import httpx, time
    headers = {"Authorization": f"Bearer {key}"}
    r = httpx.post(
        "https://easydebrid.com/api/v1/link/generate",
        headers=headers,
        json={"url": magnet},
        timeout=30,
    )
    # Some EasyDebrid builds use /torrents/add
    if r.status_code == 404:
        r = httpx.post(
            "https://easydebrid.com/api/v1/torrents/add",
            headers=headers,
            json={"magnet": magnet},
            timeout=30,
        )
    r.raise_for_status()
    data = r.json() if r.content else {}
    link = data.get("download") or data.get("link") or data.get("url")
    if link:
        return link
    tid = data.get("id") or data.get("torrent_id")
    if not tid:
        return None
    for _ in range(15):
        ir = httpx.get(f"https://easydebrid.com/api/v1/torrents/{tid}", headers=headers, timeout=20)
        if ir.status_code != 200:
            time.sleep(2)
            continue
        jd = ir.json()
        files = jd.get("files") or jd.get("links") or []
        for f in files:
            if isinstance(f, str) and f.startswith("http"):
                return f
            if isinstance(f, dict):
                u = f.get("url") or f.get("download") or f.get("link")
                if u:
                    return u
        if jd.get("download") or jd.get("link"):
            return jd.get("download") or jd.get("link")
        time.sleep(2)
    return None


def _try_offcloud(magnet: str) -> str | None:
    key = getattr(settings, "offcloud_api_key", "") or ""
    if not key:
        return None
    import httpx, time
    headers = {"Authorization": f"Bearer {key}"}
    r = httpx.post(
        "https://offcloud.com/api/cloud/download",
        headers=headers,
        data={"url": magnet, "key": key},
        timeout=30,
    )
    # alternate endpoint
    if r.status_code >= 400:
        r = httpx.post(
            "https://offcloud.com/api/remote/download",
            data={"url": magnet, "apiKey": key},
            timeout=30,
        )
    r.raise_for_status()
    data = r.json() if r.content else {}
    rid = data.get("requestId") or data.get("id")
    if data.get("url") or data.get("downloadLink"):
        return data.get("url") or data.get("downloadLink")
    if not rid:
        return None
    for _ in range(15):
        sr = httpx.get(
            "https://offcloud.com/api/cloud/status",
            params={"id": rid, "key": key},
            timeout=20,
        )
        if sr.status_code != 200:
            time.sleep(2)
            continue
        sd = sr.json()
        status = str(sd.get("status") or "").lower()
        if status in ("downloaded", "ready", "completed"):
            return sd.get("url") or sd.get("downloadLink") or sd.get("link")
        if status in ("error", "failed"):
            raise RuntimeError(sd.get("error") or "offcloud failed")
        time.sleep(2)
    return None


def resolve_stream(magnet_or_url: str, *, prefer: list[str] | None = None) -> StreamResult:
    """Try providers in order with circuit-breaker failover."""
    is_magnet = magnet_or_url.startswith("magnet:")
    order = prefer or [
        "realdebrid",
        "torbox",
        "alldebrid",
        "premiumize",
        "debridlink",
        "putio",
        "easydebrid",
        "offcloud",
        "magnet_strm",
        "direct_url",
    ]
    handlers: dict[str, Callable[[], str | None]] = {
        "realdebrid": lambda: _try_rd(magnet_or_url) if is_magnet else None,
        "torbox": lambda: _try_torbox(magnet_or_url) if is_magnet else None,
        "alldebrid": lambda: _try_alldebrid(magnet_or_url) if is_magnet else None,
        "premiumize": lambda: _try_premiumize(magnet_or_url) if is_magnet else None,
        "debridlink": lambda: _try_debridlink(magnet_or_url) if is_magnet else None,
        "putio": lambda: _try_putio(magnet_or_url) if is_magnet else None,
        "easydebrid": lambda: _try_easydebrid(magnet_or_url) if is_magnet else None,
        "offcloud": lambda: _try_offcloud(magnet_or_url) if is_magnet else None,
        "magnet_strm": lambda: magnet_or_url if is_magnet else None,
        "direct_url": lambda: magnet_or_url if not is_magnet else None,
    }
    errors = []
    for name in order:
        st = _state(name)
        if not st.available():
            errors.append(f"{name}:circuit_open")
            continue
        fn = handlers.get(name)
        if not fn:
            continue
        try:
            url = fn()
            if url:
                st.record_success()
                kind = "debrid" if name not in ("magnet_strm", "direct_url") else ("magnet" if is_magnet else "direct")
                return StreamResult(provider=name, url=url, kind=kind)
        except Exception as e:
            st.record_failure(str(e))
            errors.append(f"{name}:{e}")
    raise RuntimeError("All stream providers failed: " + "; ".join(errors[:6]))


def circuit_status() -> list[dict]:
    """Per-provider circuit state + honesty about API completeness."""
    completeness = {
        "realdebrid": "full",
        "rd": "full",
        "torbox": "good",
        "alldebrid": "good",
        "premiumize": "good",
        "debridlink": "good",
        "putio": "good",
        "easydebrid": "best-effort",
        "offcloud": "best-effort",
    }
    out = []
    for p in providers():
        st = _state(p["id"])
        out.append(
            {
                **p,
                "failures": st.failures,
                "circuit_open": not st.available(),
                "last_error": st.last_error,
                "completeness": completeness.get(p["id"], "unknown"),
            }
        )
    return out
