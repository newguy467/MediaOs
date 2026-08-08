"""Multi-provider subtitle fetch (Bazarr-style)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from app.clients.opensubtitles import opensubtitles_client
from app.config import settings

# HTML scrapers that break when sites change or Cloudflare blocks.
# Only run when the user explicitly includes them in subtitle_providers.
FRAGILE_PROVIDERS = frozenset({"addic7ed", "subscene", "yifysubtitles", "yify"})

from app.models import Episode, MediaItem, MediaType

log = logging.getLogger(__name__)


class SubtitleProvider(Protocol):
    name: str

    def fetch(
        self,
        video_path: Path,
        *,
        languages: str,
        hearing_impaired: str,
        tmdb_id: int | None = None,
        parent_tmdb_id: int | None = None,
        season: int | None = None,
        episode: int | None = None,
        title_query: str | None = None,
    ) -> Path | None: ...




class EmbeddedSidecarProvider:
    """Prefer already-present .srt next to the video (no download)."""
    name = "sidecar"

    def fetch(self, video_path, *, languages, hearing_impaired, tmdb_id=None, parent_tmdb_id=None, season=None, episode=None, title_query=None):
        stem = video_path.with_suffix("")
        for lang in [x.strip() for x in languages.split(",") if x.strip()]:
            for cand in (
                Path(f"{stem}.{lang}.srt"),
                Path(f"{stem}.{lang}.en.srt"),
                video_path.with_suffix(".srt"),
            ):
                if cand.exists() and cand.stat().st_size > 32:
                    return cand
        return None


class SubdlStyleProvider:
    """Optional SubDL API (SUBDL_API_KEY) — skipped if unset."""
    name = "subdl"

    def fetch(self, video_path, *, languages, hearing_impaired, tmdb_id=None, parent_tmdb_id=None, season=None, episode=None, title_query=None):
        import os, zipfile, io, requests
        key = os.environ.get("SUBDL_API_KEY") or getattr(settings, "subdl_api_key", "") or ""
        if not key:
            return None
        try:
            params = {"api_key": key, "languages": languages.replace(",", ","), "type": "movie" if not season else "tv"}
            if tmdb_id:
                params["tmdb_id"] = tmdb_id
            if parent_tmdb_id:
                params["tmdb_id"] = parent_tmdb_id
            if season is not None:
                params["season_number"] = season
            if episode is not None:
                params["episode_number"] = episode
            if title_query and not tmdb_id:
                params["film_name"] = title_query
            r = requests.get("https://api.subdl.com/api/v1/subtitles", params=params, timeout=20)
            if r.status_code != 200:
                return None
            data = r.json()
            subs = data.get("subtitles") or data.get("data") or []
            if not subs:
                return None
            # download first
            url = subs[0].get("url") or subs[0].get("download_link")
            if not url:
                return None
            if url.startswith("/"):
                url = "https://dl.subdl.com" + url
            binr = requests.get(url, timeout=30)
            dest = video_path.with_suffix(".srt")
            # may be zip
            if binr.content[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(binr.content)) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(".srt"):
                            dest.write_bytes(zf.read(name))
                            return dest
            else:
                dest.write_bytes(binr.content)
                return dest
        except Exception as exc:
            log.debug("subdl: %s", exc)
            return None


class OpenSubtitlesLegacyProvider:
    """Fallback title search via opensubtitles if API key missing but client still tries."""
    name = "opensubtitles_legacy"

    def fetch(self, video_path, *, languages, hearing_impaired, tmdb_id=None, parent_tmdb_id=None, season=None, episode=None, title_query=None):
        # Reuse main client when key present; else no-op
        if not settings.opensubtitles_api_key:
            return None
        return None  # primary provider already covers this

class OpenSubtitlesProvider:
    name = "opensubtitles"

    def fetch(
        self,
        video_path: Path,
        *,
        languages: str,
        hearing_impaired: str,
        tmdb_id: int | None = None,
        parent_tmdb_id: int | None = None,
        season: int | None = None,
        episode: int | None = None,
        title_query: str | None = None,
    ) -> Path | None:
        if not settings.opensubtitles_api_key:
            return None
        # HI preference is applied inside client when searching attributes
        return opensubtitles_client.fetch_best_srt(
            video_path,
            languages=languages,
            tmdb_id=tmdb_id,
            parent_tmdb_id=parent_tmdb_id,
            season=season,
            episode=episode,
            title_query=title_query,
            hearing_impaired=hearing_impaired,
        )




class Addic7edProvider:
    """Best-effort Addic7ed search via CF bypass when available."""
    name = "addic7ed"
    def fetch(self, video_path, *, languages, hearing_impaired, tmdb_id=None, parent_tmdb_id=None, season=None, episode=None, title_query=None):
        import re, httpx
        q = title_query or video_path.stem
        if not q:
            return None
        try:
            search_url = f"https://www.addic7ed.com/search.php?search={q.replace(' ', '+')}&Submit=Search"
            html = None
            try:
                from app.clients.cf_bypass import cf_bypass_client
                if cf_bypass_client.enabled():
                    html = cf_bypass_client.get_text(search_url)
            except Exception as e:
                log.debug("addic7ed cf_bypass: %s", e)
            if not html:
                try:
                    from app.clients.flaresolverr import flaresolverr_client
                    if flaresolverr_client.enabled:
                        html = flaresolverr_client.get_text(search_url)
                except Exception as e:
                    log.debug("addic7ed flaresolverr: %s", e)
            if not html:
                r = httpx.get(
                    "https://www.addic7ed.com/search.php",
                    params={"search": q, "Submit": "Search"},
                    timeout=15,
                    follow_redirects=True,
                    headers={"User-Agent": "mediaos/2.13"},
                )
                if r.status_code != 200:
                    return None
                html = r.text
            m = re.search(r'href="(/updated/[^"]+\.srt)"', html, re.I)
            if not m:
                m = re.search(r'href="(/original/[^"]+\.srt)"', html, re.I)
            if not m:
                return None
            dl = "https://www.addic7ed.com" + m.group(1)
            body = None
            try:
                from app.clients.cf_bypass import cf_bypass_client
                body = cf_bypass_client.get_text(dl)
            except Exception:
                sr = httpx.get(dl, timeout=20, headers={"User-Agent": "mediaos/2.13", "Referer": search_url})
                if sr.status_code == 200 and len(sr.content) >= 64:
                    body = sr.text if "-->" in (sr.text or "") else None
                    if body is None:
                        lang = (languages.split(",")[0] or "en").strip()
                        dest = video_path.with_suffix(f".{lang}.srt")
                        dest.write_bytes(sr.content)
                        return dest
            if not body or len(body) < 64:
                return None
            lang = (languages.split(",")[0] or "en").strip()
            dest = video_path.with_suffix(f".{lang}.srt")
            dest.write_text(body, encoding="utf-8", errors="ignore")
            return dest
        except Exception as e:
            log.debug("addic7ed: %s", e)
            return None


class SubsceneProvider:
    """Subscene via CF bypass / FlareSolverr when available."""
    name = "subscene"

    def _get(self, url: str) -> str | None:
        try:
            from app.clients.cf_bypass import cf_bypass_client
            if cf_bypass_client.enabled():
                return cf_bypass_client.get_text(url, timeout=30)
        except Exception as e:
            log.debug("subscene cf_bypass: %s", e)
        try:
            from app.clients.flaresolverr import flaresolverr_client
            if flaresolverr_client.enabled:
                return flaresolverr_client.get_text(url)
        except Exception as e:
            log.debug("subscene flaresolverr: %s", e)
        return None

    def fetch(self, video_path, *, languages, hearing_impaired, tmdb_id=None, parent_tmdb_id=None, season=None, episode=None, title_query=None):
        import re
        import io
        import zipfile
        from pathlib import Path as P
        q = title_query or video_path.stem
        if not q:
            return None
        lang = (languages.split(",")[0] or "english").strip().lower()
        lang_map = {
            "en": "english", "es": "spanish", "fr": "french", "de": "german",
            "it": "italian", "pt": "portuguese", "ar": "arabic", "nl": "dutch",
            "pl": "polish", "ru": "russian", "tr": "turkish", "sv": "swedish",
        }
        lang_name = lang_map.get(lang, lang if len(lang) > 2 else "english")
        try:
            search_url = f"https://subscene.com/subtitles/searchbytitle?query={q.replace(' ', '+')}"
            html = self._get(search_url)
            if not html:
                log.debug("subscene: no CF bypass available")
                return None
            links = re.findall(r'href="(/subtitles/[^"]+)"', html)
            if not links:
                return None
            page_url = "https://subscene.com" + links[0]
            page = self._get(page_url)
            if not page:
                return None
            lang_links = re.findall(
                rf'href="(/subtitles/[^"]*{re.escape(lang_name)}[^"]*)"',
                page,
                flags=re.I,
            )
            if not lang_links:
                lang_links = re.findall(r'href="(/subtitles/[^"]+/\d+)"', page)
            if not lang_links:
                return None
            detail_url = "https://subscene.com" + lang_links[0]
            detail = self._get(detail_url)
            if not detail:
                return None
            m = re.search(r'href="(/subtitle/download[^"]+|/subtitles/[^"]*download[^"]*)"', detail, re.I)
            if not m:
                m = re.search(r'data-href="([^"]*download[^"]*)"', detail, re.I)
            if not m:
                log.debug("subscene: no download link on detail page")
                return None
            dl_path = m.group(1)
            dl_url = dl_path if dl_path.startswith("http") else "https://subscene.com" + dl_path
            body = self._get(dl_url)
            if not body or len(body) < 20:
                return None
            if "<html" in body[:200].lower() and "cloudflare" in body[:2000].lower():
                return None
            dest_lang = (languages.split(",")[0] or "en").strip() or "en"
            raw = body.encode("latin-1", errors="ignore") if isinstance(body, str) else body
            if raw[:2] == b"PK":
                try:
                    zf = zipfile.ZipFile(io.BytesIO(raw))
                    for name in zf.namelist():
                        if name.lower().endswith((".srt", ".ass", ".vtt")):
                            data = zf.read(name)
                            dest = video_path.with_suffix(f".{dest_lang}{P(name).suffix.lower()}")
                            dest.write_bytes(data)
                            return dest
                except Exception as e:
                    log.debug("subscene zip extract: %s", e)
                dest = video_path.with_suffix(f".{dest_lang}.zip")
                dest.write_bytes(raw)
                return dest
            dest = video_path.with_suffix(f".{dest_lang}.srt")
            if isinstance(body, bytes):
                dest.write_bytes(body)
            else:
                dest.write_text(body, encoding="utf-8", errors="ignore")
            return dest
        except Exception as e:
            log.debug("subscene: %s", e)
            return None


class YifySubtitlesProvider:
    """YIFY subtitles unofficial mirror search (movies)."""
    name = "yifysubtitles"
    def fetch(self, video_path, *, languages, hearing_impaired, tmdb_id=None, parent_tmdb_id=None, season=None, episode=None, title_query=None):
        import re, zipfile, io, httpx
        if season is not None:
            return None  # movie-oriented
        q = title_query or video_path.stem
        if not q:
            return None
        try:
            # yifysubtitles.org style search
            r = httpx.get(
                "https://yifysubtitles.ch/search",
                params={"q": q},
                timeout=15,
                follow_redirects=True,
                headers={"User-Agent": "mediaos/2.11"},
            )
            if r.status_code != 200:
                return None
            # first subtitle page link
            m = re.search(r'href="(/subtitles/[^"]+)"', r.text)
            if not m:
                return None
            page = "https://yifysubtitles.ch" + m.group(1)
            pr = httpx.get(page, timeout=15, headers={"User-Agent": "mediaos/2.11"})
            # language-filtered download
            lang = (languages.split(",")[0] or "english").strip().lower()
            dm = re.search(rf'href="(/subtitle/[^"]*{re.escape(lang)}[^"]*\.zip)"', pr.text, re.I)
            if not dm:
                dm = re.search(r'href="(/subtitle/[^"]+\.zip)"', pr.text, re.I)
            if not dm:
                return None
            zr = httpx.get("https://yifysubtitles.ch" + dm.group(1), timeout=20, headers={"User-Agent": "mediaos/2.11"})
            if zr.status_code != 200:
                return None
            zf = zipfile.ZipFile(io.BytesIO(zr.content))
            for name in zf.namelist():
                if name.lower().endswith(".srt"):
                    dest = video_path.with_suffix(f".{lang[:2]}.srt")
                    dest.write_bytes(zf.read(name))
                    return dest
        except Exception as e:
            log.debug("yifysubtitles: %s", e)
            return None


class EmbeddedHashProbeProvider:
    """If an .srt already exists near the file matching preferred langs, use it."""
    name = "hash-sidecar"
    def fetch(self, video_path, *, languages, hearing_impaired, tmdb_id=None, parent_tmdb_id=None, season=None, episode=None, title_query=None):
        # same as sidecar but also check parent folder for matching names
        stem = video_path.with_suffix("")
        langs = [x.strip() for x in languages.split(",") if x.strip()] or ["en"]
        candidates = []
        for lang in langs:
            candidates.extend([
                Path(f"{stem}.{lang}.srt"),
                Path(f"{stem}.{lang}.en.srt"),
                video_path.with_suffix(".srt"),
            ])
        parent = video_path.parent
        if parent.is_dir():
            for p in parent.glob("*.srt"):
                candidates.append(p)
        for cand in candidates:
            try:
                if cand.exists() and cand.stat().st_size > 32:
                    return cand
            except Exception:
                continue
        return None

class OpenSubtitlesComProvider:
    """Alias so profile list can show 6 distinct provider names."""
    name = "opensubtitlescom"
    def fetch(self, video_path, *, languages, hearing_impaired, tmdb_id=None, parent_tmdb_id=None, season=None, episode=None, title_query=None):
        return OpenSubtitlesProvider().fetch(
            video_path, languages=languages, hearing_impaired=hearing_impaired,
            tmdb_id=tmdb_id, parent_tmdb_id=parent_tmdb_id, season=season, episode=episode, title_query=title_query,
        )

def _providers() -> list[SubtitleProvider]:
    names = [x.strip().lower() for x in (settings.subtitle_providers or "opensubtitles").split(",") if x.strip()]
    out: list[SubtitleProvider] = []
    # always try local sidecar first
    out.append(EmbeddedSidecarProvider())
    mapping = {
        "opensubtitles": OpenSubtitlesProvider,
        "os": OpenSubtitlesProvider,
        "opensubtitlescom": OpenSubtitlesComProvider,
        "subdl": SubdlStyleProvider,
        "addic7ed": Addic7edProvider,
        "subscene": SubsceneProvider,
        "yifysubtitles": YifySubtitlesProvider,
        "yify": YifySubtitlesProvider,
        "hash-sidecar": EmbeddedHashProbeProvider,
    }
    # expand local probe after basic sidecar
    out.append(EmbeddedHashProbeProvider())
    for n in names:
        if n in ("sidecar", "hash-sidecar"):
            continue
        cls = mapping.get(n)
        if cls:
            out.append(cls())
    # also try SubDL if key present even when not listed
    if any(isinstance(x, SubdlStyleProvider) for x in out) is False:
        out.append(SubdlStyleProvider())
    if not any(isinstance(x, OpenSubtitlesProvider) for x in out):
        out.append(OpenSubtitlesProvider())
    return out


def fetch_subtitles(
    video_path: Path,
    *,
    item: MediaItem | None = None,
    episode: Episode | None = None,
    languages: str | None = None,
    hearing_impaired: str | None = None,
) -> dict:
    """Try each provider; return {ok, path, provider, error}."""
    if not video_path.exists():
        return {"ok": False, "error": "video not found"}
    langs = languages or settings.subtitle_languages or "en"
    hi = hearing_impaired or settings.subtitle_hearing_impaired or "include"

    tmdb_id = parent_tmdb = season = ep_num = None
    query = None
    if item is not None:
        if item.media_type == MediaType.movie:
            tmdb_id = item.external_id
            query = f"{item.title} {item.year or ''}".strip()
        elif item.media_type == MediaType.tv:
            parent_tmdb = item.external_id
            query = item.title
    if episode is not None:
        season = episode.season_number
        ep_num = episode.episode_number
        if episode.title:
            query = f"{query or ''} {episode.title}".strip()

    errors = []
    for prov in _providers():
        try:
            path = prov.fetch(
                video_path,
                languages=langs,
                hearing_impaired=hi,
                tmdb_id=tmdb_id,
                parent_tmdb_id=parent_tmdb,
                season=season,
                episode=ep_num,
                title_query=query,
            )
            if path:
                return {"ok": True, "path": str(path), "provider": prov.name}
        except Exception as exc:
            log.warning("Subtitle provider %s failed: %s", prov.name, exc)
            errors.append(f"{prov.name}: {exc}")
    return {"ok": False, "error": "; ".join(errors) or "no subtitles found"}


def score_subtitle(candidate: dict, *, languages: list[str], hearing_impaired: str = "include") -> int:
    """Rank subtitle candidates (MediaOs-style scoring)."""
    score = 0
    lang = (candidate.get("language") or candidate.get("lang") or "").lower()
    preferred = [x.lower() for x in languages]
    if lang in preferred:
        score += 50 - preferred.index(lang) * 5
    if candidate.get("hearing_impaired") or candidate.get("hi"):
        if hearing_impaired == "exclude":
            score -= 30
        elif hearing_impaired == "prefer":
            score += 10
    if candidate.get("hash_match"):
        score += 40
    if candidate.get("download_count"):
        try:
            score += min(15, int(candidate["download_count"]) // 100)
        except Exception:
            pass
    if candidate.get("from_sidecar"):
        score += 60
    return score


def adaptive_pick(candidates: list[dict], *, languages: str = "en", hearing_impaired: str = "include") -> dict | None:
    langs = [x.strip() for x in languages.split(",") if x.strip()] or ["en"]
    ranked = sorted(
        candidates,
        key=lambda c: score_subtitle(c, languages=langs, hearing_impaired=hearing_impaired),
        reverse=True,
    )
    return ranked[0] if ranked else None


def list_wanted_subtitles(db, *, limit: int = 100) -> list[dict]:
    """Bazarr-style: library items that look like they need subtitles."""
    from app.models import MediaItem, MediaType, ItemStatus, Episode
    out = []
    # Movies downloaded without a sidecar note (best-effort: always list monitored downloaded)
    movies = (
        db.query(MediaItem)
        .filter(MediaItem.media_type == MediaType.movie, MediaItem.status == ItemStatus.downloaded)
        .limit(limit)
        .all()
    )
    for m in movies:
        out.append({
            "kind": "movie",
            "id": m.id,
            "title": m.title,
            "year": m.year,
            "file_path": m.file_path,
            "languages": None,
        })
    eps = (
        db.query(Episode)
        .filter(Episode.status == ItemStatus.downloaded, Episode.file_path.isnot(None))
        .limit(limit)
        .all()
    )
    for e in eps:
        series = e.series
        out.append({
            "kind": "episode",
            "id": e.id,
            "series_id": e.media_item_id,
            "title": f"{series.title if series else '?'} S{e.season_number:02d}E{e.episode_number:02d}",
            "file_path": e.file_path,
            "languages": None,
        })
    return out[:limit]


def provider_status() -> list[dict]:
    """Report which subtitle providers are configured / available."""
    import os
    from app.config import settings
    key = (getattr(settings, "opensubtitles_api_key", None) or "").strip()
    subdl = (os.environ.get("SUBDL_API_KEY") or getattr(settings, "subdl_api_key", "") or "").strip()
    configured = [x.strip().lower() for x in (getattr(settings, "subtitle_providers", None) or "opensubtitles").split(",") if x.strip()]
    fragile = {"addic7ed", "subscene", "yifysubtitles", "yify"}
    active_fragile = [x for x in configured if x in fragile]
    # Detect FlareSolverr / CF bypass availability for fragile providers
    cf_ok = False
    try:
        from app.clients.flaresolverr import flaresolverr_client
        cf_ok = bool(getattr(flaresolverr_client, "enabled", False))
    except Exception:
        pass
    fragile_note = (
        "optional HTML scrape — works with FlareSolverr/CF bypass"
        if cf_ok else
        "optional HTML scrape — NOT reliable without FlareSolverr (CF). Prefer OpenSubtitles."
    )
    return [
        {"name": "sidecar", "configured": True, "notes": "local .srt next to video", "supported": True},
        {"name": "opensubtitles", "configured": bool(key), "notes": "OPENSUBTITLES_API_KEY" if not key else "ready — primary supported path", "supported": True},
        {"name": "subdl", "configured": bool(subdl), "notes": "SUBDL_API_KEY" if not subdl else "ready", "supported": True},
        {"name": "addic7ed", "configured": "addic7ed" in configured, "notes": fragile_note, "supported": False, "requires_cf": True},
        {"name": "yifysubtitles", "configured": "yify" in configured or "yifysubtitles" in configured, "notes": fragile_note, "supported": False, "requires_cf": True},
        {"name": "subscene", "configured": "subscene" in configured, "notes": fragile_note + " (aggressive CF)", "supported": False, "requires_cf": True},
        {"name": "active_order", "configured": True, "notes": ",".join(configured) or "sidecar,opensubtitles,subdl"},
        {"name": "fragile_enabled", "configured": bool(active_fragile), "notes": ",".join(active_fragile) or "none (recommended — use OpenSubtitles only)"},
        {"name": "recommendation", "configured": True, "notes": "Supported path: OpenSubtitles (+ SubDL). Addic7ed/Subscene/YIFY are best-effort and CF-dependent."},
    ]
