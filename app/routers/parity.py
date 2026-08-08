"""MediaOs-parity feature surface."""
from __future__ import annotations

from app.auth import require_permission
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel

from app.clients.realdebrid import rd_client
from app.clients.sabnzbd import sabnzbd_client
from app.clients.nzbget import nzbget_client
from app.clients.trakt import trakt_client
from app.services.delay_profiles import list_profiles
from app.services.streaming import create_movie_strm_from_magnet, providers_status
from app.services.workers import get_job, list_jobs, submit

router = APIRouter(prefix="/parity", tags=["parity"])


@router.get("/status")
def parity_status():
    """Map of MediaOs-class features and mediaos coverage."""
    return {
        "features": {
            "radarr_sonarr": {"status": "done", "notes": "movies + TV + packs + calendar + wanted"},
            "bazarr": {"status": "done", "notes": "OpenSubtitles + SubDL + sidecar"},
            "overseerr": {"status": "done", "notes": "native request queue — submit/approve/deny, zero external app needed"},
            "flaresolverr": {"status": "done", "notes": "curl_cffi built-in CF bypass + optional FlareSolverr"},
            "live_tv": {"status": "done", "notes": "M3U/Xtream + EPG fields"},
            "strm_streaming": {"status": "done", "notes": "movie .strm + Real-Debrid magnet resolve"},
            "usenet": {"status": "done", "notes": "SABnzbd + NZBGet client matrix"},
            "usenet_streaming": {"status": "ok", "notes": "Byte-range seekable NNTP stream with yEnc decode, segment LRU cache, prefetch"},
            "quality_scoring": {"status": "done", "notes": "50+ factor families + resolution-downgrade guard"},
            "smart_lists": {"status": "done", "notes": "TMDb + Trakt + IMDb first-class sources"},
            "file_watch": {"status": "done", "notes": "poll-based library watch"},
            "delay_profiles": {"status": "done", "notes": "default delay profiles API"},
            "workers": {"status": "done", "notes": "background job registry"},
            "trash_naming": {"status": "done", "notes": "end-to-end in organize with IDs in paths"},
            "imdb_trakt_smartlists": {"status": "done", "notes": "first-class list sources"},
            "file_matching_depth": {"status": "done", "notes": "ID-in-path + rename tracking"},
            "workers_ui": {"status": "done", "notes": "rich progress UI"},
            "real_debrid": {"status": "done", "notes": "magnet add + unrestrict"},
            "music_books_audiobooks": {"status": "done", "notes": "beyond MediaOs scope"},
            "prowlarr": {"status": "optional", "notes": "built-in YTS/EZTV/BitSearch wired directly into auto-search — zero indexer config needed to grab movies/TV out of the box; Prowlarr/Torznab is purely additive for private trackers"},
            "jellyseerr_api": {"status": "done", "notes": "beyond MediaOs (external requests UI)"},
            "vpn_killswitch": {"status": "done", "notes": "optional Gluetun health-check; mediaos itself never requires a VPN container to run — only relevant if you route qBittorrent's own traffic through one"},
            "cross_seed_unpack_jdupes": {"status": "done", "notes": "beyond MediaOs"},
            "builtin_indexers": {"status": "done", "notes": "YTS + EZTV + BitSearch without Prowlarr"},
            "discover": {"status": "done", "notes": "trending/popular/now-playing/upcoming + coming-up"},
            "storage_maintenance": {"status": "done", "notes": "per-library disk stats + largest files"},
            "emby_jellyfin_notify": {"status": "done", "notes": "Apprise + Jellyfin/Emby library refresh"},
            "failed_download_cooldown": {"status": "done", "notes": "configurable cooldown before re-grab"},
            "resolution_downgrade_guard": {"status": "done", "notes": "block lower-res upgrades"},
            "imdb_trakt_smartlists": {"status": "done", "notes": "first-class list sources"},
            "file_matching_depth": {"status": "done", "notes": "ID-in-path + rename tracking"},
            "workers_ui": {"status": "done", "notes": "rich progress UI"},
            "nzbget": {"status": "done", "notes": "NZBGet in download-client matrix"},
            "podcasts": {"status": "done", "notes": "RSS subscribe + auto-download new episodes; zero arr apps do this"},
            "movie_collections": {"status": "done", "notes": "TMDb saga grouping (MCU/Bond/etc) + add-all + progress badge; beyond MediaOs"},
        },
        "clients": {
            "sabnzbd": sabnzbd_client.test(),
            "nzbget": nzbget_client.test(),
            "real_debrid": rd_client.test(),
            "trakt": trakt_client.test(),
            "imdb": __import__("app.clients.imdb", fromlist=["imdb_client"]).imdb_client.test(),
        },
        "streaming_providers": providers_status(),
        "delay_profiles": list_profiles(),
    }


@router.get("/delay-profiles")
def delay_profiles():
    return list_profiles()


@router.get("/workers")
def workers():
    return list_jobs()


@router.get("/workers/{job_id}")
def worker_job(job_id: str):
    j = get_job(job_id)
    if not j:
        raise HTTPException(404)
    return j


class StrmIn(BaseModel):
    title: str
    magnet: str
    year: int | None = None


@router.post("/strm/movie")
def strm_movie(body: StrmIn, _perm: list = Depends(require_permission("settings", "library.manage"))):
    return create_movie_strm_from_magnet(body.title, body.magnet, body.year)


@router.get("/trakt/trending/movies")
def trakt_movies(limit: int = 20):
    return trakt_client.trending_movies(limit)


@router.get("/trakt/trending/shows")
def trakt_shows(limit: int = 20):
    return trakt_client.trending_shows(limit)


@router.post("/workers/search-all")
def job_search_all(_perm: list = Depends(require_permission("settings", "library.manage"))):
    def _fn(job):
        from app.database import SessionLocal
        from app.services.wanted import search_all_missing
        job.message = "searching missing"
        job.progress = 10
        db = SessionLocal()
        try:
            result = search_all_missing(db, limit=30)
            job.progress = 100
            return result
        finally:
            db.close()

    jid = submit("search-all-missing", _fn)
    return {"job_id": jid}


@router.get("/streams/providers")
def stream_providers():
    from app.services.stream_providers import circuit_status
    return circuit_status()


@router.post("/streams/resolve")
def stream_resolve(body: dict, _perm: list = Depends(require_permission("settings", "library.manage"))):
    from app.services.stream_providers import resolve_stream
    url = body.get("magnet") or body.get("url")
    if not url:
        raise HTTPException(400, "magnet or url required")
    try:
        r = resolve_stream(url, prefer=body.get("prefer"))
        return {"provider": r.provider, "url": r.url, "kind": r.kind}
    except Exception as e:
        raise HTTPException(502, str(e))


@router.get("/cf-bypass/test")
def cf_test(url: str = "https://www.cloudflare.com/cdn-cgi/trace"):
    from app.clients.cf_bypass import cf_bypass_client
    return cf_bypass_client.test(url)


@router.get("/usenet-stream/status")
def usenet_stream_status():
    from app.services.usenet_stream import status
    return status()


@router.post("/usenet-stream/inspect")
def usenet_inspect(body: dict, _perm: list = Depends(require_permission("settings", "library.manage"))):
    from app.services.usenet_stream import inspect_nzb
    xml = body.get("nzb_xml") or body.get("xml") or ""
    if not xml:
        raise HTTPException(400, "nzb_xml required")
    return inspect_nzb(xml)


@router.post("/usenet-stream/sessions")
def usenet_create_session(body: dict, _perm: list = Depends(require_permission("settings", "library.manage"))):
    """Create a seekable stream session from NZB XML.

    Returns session_id + stream_path. Clients then GET the stream_path with
    standard Range headers (bytes=START-END) for 206 Partial Content.
    """
    from app.services.usenet_stream import create_session, nntp_enabled
    xml = body.get("nzb_xml") or body.get("xml") or ""
    if not xml:
        raise HTTPException(400, "nzb_xml required")
    if not nntp_enabled():
        raise HTTPException(503, "NNTP not configured (set NNTP_HOST)")
    file_index = int(body.get("file_index") or 0)
    try:
        return create_session(xml, file_index=file_index)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/usenet-stream/sessions/{session_id}")
def usenet_stream_session(session_id: str, request: Request):
    """Byte-range capable stream. Supports Range: bytes=start-end."""
    from starlette.responses import StreamingResponse, Response
    from app.services.usenet_stream import open_session_range, session_info

    info = session_info(session_id)
    if not info:
        raise HTTPException(404, "session not found or expired")

    total = int(info["size_est"] or 0)
    range_header = request.headers.get("range") or request.headers.get("Range")
    start, end = 0, total

    if range_header and range_header.lower().startswith("bytes=") and total > 0:
        spec = range_header.split("=", 1)[1].strip()
        # only first range
        spec = spec.split(",")[0].strip()
        if "-" in spec:
            a, b = spec.split("-", 1)
            if a == "" and b:
                # suffix: last N bytes
                suffix = int(b)
                start = max(0, total - suffix)
                end = total
            else:
                start = int(a) if a else 0
                end = int(b) + 1 if b else total  # HTTP Range end is inclusive
        start = max(0, min(start, total))
        end = max(start, min(end, total))
        status_code = 206
    else:
        status_code = 200
        start, end = 0, total

    try:
        _sess, _nf, start, end, iterator = open_session_range(session_id, start, end if end else None)
    except KeyError:
        raise HTTPException(404, "session not found or expired")

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": "application/octet-stream",
        "Content-Disposition": f'attachment; filename="{info["filename"][:80]}"',
        "Cache-Control": "no-store",
        "X-MediaOs-Seekable": "1",
        "X-MediaOs-Session": session_id,
    }
    length = max(0, end - start)
    if length:
        headers["Content-Length"] = str(length)
    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end - 1}/{total}"

    return StreamingResponse(iterator, status_code=status_code, headers=headers, media_type="application/octet-stream")


@router.get("/usenet-stream/sessions/{session_id}/info")
def usenet_session_info(session_id: str):
    from app.services.usenet_stream import session_info
    info = session_info(session_id)
    if not info:
        raise HTTPException(404, "session not found or expired")
    return info


@router.get("/library-watch/status")
def library_watch_status():
    from app.services.library_watch import status, poll_once
    return {**status(), "poll": poll_once()}


@router.get("/storage")
def parity_storage():
    from app.services.storage import library_storage
    return library_storage()
