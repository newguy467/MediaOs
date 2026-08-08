"""YouTube creator tracking via public RSS — no API key required."""
from __future__ import annotations
import logging, re, xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote_plus, urlparse, parse_qs
import httpx
log = logging.getLogger(__name__)
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}

class YouTubeClient:
    def __init__(self) -> None:
        self.client = httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": "mediaos/2.3"})
    def resolve_channel(self, query: str) -> dict[str, Any] | None:
        q = (query or "").strip()
        if not q: return None
        cid = _extract_channel_id(q)
        if cid: return self.fetch_channel_feed(cid)
        handle = None
        m = re.search(r"(?:youtube\.com/)?@([\w.-]+)", q, re.I)
        if m: handle = m.group(1)
        elif q.startswith("@"): handle = q[1:]
        if handle:
            cid = self._resolve_handle(handle)
            if cid: return self.fetch_channel_feed(cid)
        pl = _extract_playlist_id(q)
        if pl: return self.fetch_playlist_feed(pl)
        return None
    def _resolve_handle(self, handle: str) -> str | None:
        try:
            r = self.client.get(f"https://www.youtube.com/@{handle}")
            r.raise_for_status()
            for pat in [r'"channelId"\s*:\s*"(UC[\w-]{22})"', r'<meta\s+itemprop="channelId"\s+content="(UC[\w-]{22})"', r"/channel/(UC[\w-]{22})"]:
                m = re.search(pat, r.text)
                if m: return m.group(1)
        except Exception as e:
            log.warning("handle resolve @%s: %s", handle, e)
        return None
    def fetch_channel_feed(self, channel_id: str) -> dict[str, Any]:
        return self._parse_feed(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", channel_id=channel_id)
    def fetch_playlist_feed(self, playlist_id: str) -> dict[str, Any]:
        return self._parse_feed(f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}", playlist_id=playlist_id)
    def _parse_feed(self, feed_url: str, *, channel_id: str | None = None, playlist_id: str | None = None) -> dict[str, Any]:
        r = self.client.get(feed_url); r.raise_for_status()
        root = ET.fromstring(r.text)
        title = _atom_text(root, "atom:title") or channel_id or playlist_id or "YouTube"
        author = None
        ae = root.find("atom:author", ATOM_NS)
        if ae is not None: author = _atom_text(ae, "atom:name")
        videos = []
        for entry in root.findall("atom:entry", ATOM_NS):
            vid = None
            ve = entry.find("yt:videoId", ATOM_NS)
            if ve is not None and ve.text: vid = ve.text.strip()
            if not vid:
                link = entry.find("atom:link", ATOM_NS)
                href = link.get("href") if link is not None else None
                if href: vid = _extract_video_id(href)
            if not vid: continue
            thumb = desc = None
            mg = entry.find("media:group", ATOM_NS)
            if mg is not None:
                te = mg.find("media:thumbnail", ATOM_NS)
                if te is not None: thumb = te.get("url")
                de = mg.find("media:description", ATOM_NS)
                if de is not None and de.text: desc = de.text.strip()
            videos.append({"video_id": vid, "title": _atom_text(entry, "atom:title") or vid,
                "published_at": _atom_text(entry, "atom:published"), "thumbnail": thumb,
                "description": desc, "url": f"https://www.youtube.com/watch?v={vid}"})
        return {"feed_url": feed_url, "channel_id": channel_id, "playlist_id": playlist_id,
                "title": title, "author": author, "videos": videos}
    def search_channels(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp=EgIQAg%253D%253D"
        try:
            r = self.client.get(url); r.raise_for_status(); html = r.text
        except Exception as e:
            log.warning("yt search: %s", e); return []
        out, seen = [], set()
        for m in re.finditer(r'"channelId"\s*:\s*"(UC[\w-]{22})".{0,400}?"title"\s*:\s*\{\s*"simpleText"\s*:\s*"([^"]+)"', html):
            cid, title = m.group(1), m.group(2)
            if cid in seen: continue
            seen.add(cid)
            out.append({"channel_id": cid, "title": title, "url": f"https://www.youtube.com/channel/{cid}",
                        "feed_url": f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"})
            if len(out) >= limit: break
        return out

def _atom_text(el, path):
    c = el.find(path, ATOM_NS)
    return c.text.strip() if c is not None and c.text else None
def _extract_channel_id(s):
    m = re.search(r"(UC[\w-]{22})", s); return m.group(1) if m else None
def _extract_playlist_id(s):
    m = re.search(r"(?:list=)(PL[\w-]+)", s)
    if m: return m.group(1)
    m = re.search(r"\b(PL[\w-]{10,})\b", s); return m.group(1) if m else None
def _extract_video_id(url):
    try:
        p = urlparse(url)
        if "youtu.be" in (p.netloc or ""): return p.path.strip("/").split("/")[0] or None
        qs = parse_qs(p.query or "")
        if "v" in qs: return qs["v"][0]
    except Exception: pass
    return None

youtube_client = YouTubeClient()
