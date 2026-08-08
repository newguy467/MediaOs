"""Torznab / Newznab search client (Prowlarr wedge)."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urljoin

import httpx

from app.clients.flaresolverr import flaresolverr_client

log = logging.getLogger(__name__)

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "torznab": "http://torznab.com/schemas/2015/feed",
}


def _text(el: ET.Element | None, default: str = "") -> str:
    if el is None or el.text is None:
        return default
    return el.text.strip()


def _attr_map(item: ET.Element) -> dict[str, str]:
    out = {}
    for attr in item.findall("torznab:attr", NS):
        name = attr.attrib.get("name")
        val = attr.attrib.get("value")
        if name:
            out[name] = val or ""
    # also bare attr without ns
    for attr in item.findall("attr"):
        name = attr.attrib.get("name")
        val = attr.attrib.get("value")
        if name:
            out[name] = val or ""
    return out


class TorznabClient:
    def search(
        self,
        base_url: str,
        *,
        query: str,
        api_key: str | None = None,
        categories: str | None = None,
        limit: int = 50,
        use_flaresolverr: bool = False,
    ) -> list[dict[str, Any]]:
        base = base_url.rstrip("/")
        # Accept either .../api or site root
        if not base.endswith("/api"):
            endpoint = base + "/api"
        else:
            endpoint = base
        params: dict[str, str] = {
            "t": "search",
            "q": query,
            "limit": str(limit),
        }
        if api_key:
            params["apikey"] = api_key
        if categories:
            params["cat"] = categories

        xml_text: str
        if use_flaresolverr and flaresolverr_client.enabled:
            # FlareSolverr can't easily POST query params as GET via solution — build URL
            from urllib.parse import urlencode

            full = endpoint + "?" + urlencode(params)
            xml_text = flaresolverr_client.get_text(full)
        else:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                r = client.get(endpoint, params=params)
                r.raise_for_status()
                xml_text = r.text

        return self._parse(xml_text, indexer_name=base_url)

    def _parse(self, xml_text: str, indexer_name: str) -> list[dict[str, Any]]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            log.warning("Torznab XML parse error: %s", exc)
            return []
        items = root.findall(".//item")
        rows: list[dict[str, Any]] = []
        for item in items:
            title = _text(item.find("title"))
            link = _text(item.find("link"))
            guid = _text(item.find("guid")) or link
            attrs = _attr_map(item)
            size = int(attrs.get("size") or 0) if str(attrs.get("size") or "").isdigit() else 0
            seeders = int(attrs.get("seeders") or 0) if str(attrs.get("seeders") or "").isdigit() else 0
            peers = int(attrs.get("peers") or 0) if str(attrs.get("peers") or "").isdigit() else 0
            magnet = attrs.get("magneturl") or attrs.get("magnetUrl") or ""
            download_url = magnet or link
            info_hash = (attrs.get("infohash") or attrs.get("infoHash") or "").lower() or None
            if not title or not download_url:
                continue
            rows.append(
                {
                    "title": title,
                    "download_url": download_url,
                    "indexer": indexer_name,
                    "size": size,
                    "seeders": seeders,
                    "peers": peers,
                    "info_hash": info_hash,
                    "guid": guid,
                }
            )
        return rows

    def caps(self, base_url: str, api_key: str | None = None) -> dict:
        base = base_url.rstrip("/")
        endpoint = base if base.endswith("/api") else base + "/api"
        params = {"t": "caps"}
        if api_key:
            params["apikey"] = api_key
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            r = client.get(endpoint, params=params)
            r.raise_for_status()
            return {"ok": True, "bytes": len(r.content), "status": r.status_code}


torznab_client = TorznabClient()
