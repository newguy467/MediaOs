"""RSS podcast feed parsing + iTunes search + chapter metadata.

Chapters sources (in order):
  1. Podcasting 2.0 <podcast:chapters> JSON URL
  2. PSC namespace <psc:chapters>/<psc:chapter>
  3. Inline JSON in description (`[ { "startTime": ... } ]`)
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

import httpx

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
PSC_NS = "http://podlove.org/simple-chapters"
PODCAST_NS = "https://podcastindex.org/namespace/1.0"
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


def _text(el, tag: str, ns: dict | None = None) -> str | None:
    if el is None:
        return None
    found = el.find(tag, ns) if ns else el.find(tag)
    if found is None or found.text is None:
        return None
    return found.text.strip()


def _duration_to_seconds(raw: str | None) -> int | None:
    if not raw:
        return None
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    parts = raw.split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return None
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts[-3:]
    return h * 3600 + m * 60 + s


def _time_to_seconds(raw: str | float | int | None) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    raw = str(raw).strip()
    if not raw:
        return None
    if raw.replace(".", "", 1).isdigit():
        return float(raw)
    return float(_duration_to_seconds(raw) or 0)


def parse_chapters_from_item(item, ns: dict, client: httpx.Client | None = None) -> list[dict]:
    """Extract chapter list: [{title, start_seconds, href?}]."""
    chapters: list[dict] = []

    # Podcasting 2.0 remote JSON
    for tag in ("{%s}chapters" % PODCAST_NS, "podcast:chapters"):
        el = item.find(tag) if "{" in tag else item.find(tag, ns)
        if el is None:
            continue
        url = el.get("url") or el.get("href")
        if url and client is not None:
            try:
                r = client.get(url, timeout=15.0)
                r.raise_for_status()
                data = r.json()
                rows = data.get("chapters") if isinstance(data, dict) else data
                for ch in rows or []:
                    start = _time_to_seconds(ch.get("startTime") or ch.get("start"))
                    title = ch.get("title") or ch.get("name") or "Chapter"
                    if start is None:
                        continue
                    chapters.append({
                        "title": str(title)[:200],
                        "start_seconds": float(start),
                        "href": ch.get("url") or ch.get("img") or None,
                    })
            except Exception:
                pass
        if chapters:
            return chapters

    # PSC simple chapters
    # NOTE: must use explicit `is None` checks here, not `or` — ElementTree
    # Element truthiness is based on child count (len(element)), not
    # identity, so `el1 or el2` would silently skip a real-but-empty
    # <psc:chapters> element and fall through to the second find().
    psc = item.find("psc:chapters", ns)
    if psc is None:
        psc = item.find("{%s}chapters" % PSC_NS)
    if psc is not None:
        for ch in list(psc):
            if not ch.tag.endswith("chapter"):
                continue
            start = _time_to_seconds(ch.get("start") or ch.get("startTime"))
            title = ch.get("title") or (ch.text or "Chapter")
            if start is None:
                continue
            chapters.append({
                "title": str(title).strip()[:200],
                "start_seconds": float(start),
                "href": ch.get("href"),
            })
        if chapters:
            return chapters

    # JSON blob in description / content:encoded
    desc = _text(item, "description") or ""
    content = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
    if content is not None and content.text:
        desc = desc + "\n" + content.text
    m = re.search(r"\[\s*\{\s*\"startTime\"", desc)
    if m:
        # try to find JSON array
        start_idx = desc.find("[", m.start())
        depth = 0
        end_idx = None
        for i, c in enumerate(desc[start_idx:], start_idx):
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        if end_idx:
            try:
                rows = json.loads(desc[start_idx:end_idx])
                for ch in rows:
                    start = _time_to_seconds(ch.get("startTime") or ch.get("start"))
                    if start is None:
                        continue
                    chapters.append({
                        "title": str(ch.get("title") or "Chapter")[:200],
                        "start_seconds": float(start),
                        "href": ch.get("url"),
                    })
            except Exception:
                pass
    return chapters


class PodcastRSSClient:
    def __init__(self):
        self.client = httpx.Client(timeout=20.0, follow_redirects=True)

    def fetch_feed(self, feed_url: str) -> dict:
        resp = self.client.get(feed_url, headers={"User-Agent": "mediaos/2.3 (+podcasts)"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            raise ValueError("Not a valid RSS feed (no <channel>)")

        ns = {"itunes": ITUNES_NS, "psc": PSC_NS, "podcast": PODCAST_NS}
        title = _text(channel, "title") or feed_url
        description = _text(channel, "description") or _text(channel, "itunes:summary", ns)
        author = _text(channel, "itunes:author", ns)
        image = None
        image_el = channel.find("image")
        if image_el is not None:
            image = _text(image_el, "url")
        if not image:
            itunes_image = channel.find("itunes:image", ns)
            if itunes_image is not None:
                image = itunes_image.get("href")

        episodes = []
        for item in channel.findall("item"):
            audio_url = None
            enclosure = item.find("enclosure")
            if enclosure is not None:
                audio_url = enclosure.get("url")
            if not audio_url:
                continue
            guid_el = item.find("guid")
            guid = (guid_el.text or "").strip() if guid_el is not None and guid_el.text else audio_url
            ep_title = _text(item, "title") or "Episode"
            pub_date = _text(item, "pubDate")
            duration = _duration_to_seconds(_text(item, "itunes:duration", ns))
            ep_num = _text(item, "itunes:episode", ns)
            chapters = parse_chapters_from_item(item, ns, client=self.client)
            episodes.append({
                "guid": guid,
                "title": ep_title,
                "audio_url": audio_url,
                "pub_date": pub_date,
                "duration_seconds": duration,
                "episode_number": int(ep_num) if ep_num and str(ep_num).isdigit() else None,
                "chapters": chapters,
            })

        return {
            "title": title,
            "description": description,
            "author": author,
            "image": image,
            "episodes": episodes,
        }

    def search_itunes(self, query: str, limit: int = 20) -> list[dict]:
        resp = self.client.get(
            ITUNES_SEARCH_URL,
            params={"term": query, "media": "podcast", "entity": "podcast", "limit": limit},
        )
        resp.raise_for_status()
        out = []
        for row in resp.json().get("results") or []:
            feed = row.get("feedUrl")
            if not feed:
                continue
            out.append({
                "title": row.get("collectionName") or row.get("trackName") or "Podcast",
                "author": row.get("artistName"),
                "feed_url": feed,
                "image": row.get("artworkUrl600") or row.get("artworkUrl100"),
                "itunes_id": row.get("collectionId"),
            })
        return out


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name or "podcast", flags=re.U).strip().lower()
    return (re.sub(r"[-\s]+", "-", s)[:80]) or "podcast"


podcast_rss_client = PodcastRSSClient()
