"""Stalker Middleware (MAG) portal client + simple MAC probe."""
from __future__ import annotations

import logging
import random
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx

log = logging.getLogger(__name__)


def _rand_mac() -> str:
    return "00:1A:79:%02X:%02X:%02X" % (
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
    )


class StalkerClient:
    def __init__(self, portal_url: str, mac: str | None = None):
        self.portal_url = portal_url.rstrip("/") + "/"
        self.mac = (mac or _rand_mac()).upper()
        self.token: str | None = None
        self._client = httpx.Client(timeout=30.0, follow_redirects=True)

    def _headers(self) -> dict:
        h = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
            "X-User-Agent": "Model: MAG254; Link: Ethernet",
            "Cookie": f"mac={self.mac}; stb_lang=en; timezone=America/New_York",
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _api(self, **params) -> dict:
        # common stalker load.php endpoint
        url = urljoin(self.portal_url, "portal.php")
        if "portal.php" not in self.portal_url and "server/load.php" not in self.portal_url:
            # try server/load.php style
            alt = urljoin(self.portal_url, "server/load.php")
            try:
                r = self._client.get(alt, params=params, headers=self._headers())
                if r.status_code == 200:
                    return r.json()
            except Exception:
                pass
        r = self._client.get(url, params=params, headers=self._headers())
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"raw": r.text[:500]}

    def handshake(self) -> dict:
        data = self._api(type="stb", action="handshake", JsHttpRequest="1-xml")
        token = (data.get("js") or {}).get("token") or data.get("token")
        if token:
            self.token = token
        return data

    def get_profile(self) -> dict:
        return self._api(type="stb", action="get_profile", JsHttpRequest="1-xml")

    def get_genres(self) -> list:
        data = self._api(type="itv", action="get_genres", JsHttpRequest="1-xml")
        return data.get("js") or data.get("data") or []

    def get_ordered_list(self, genre: str = "*", page: int = 1) -> list[dict]:
        data = self._api(
            type="itv",
            action="get_ordered_list",
            genre=genre,
            p=page,
            JsHttpRequest="1-xml",
        )
        js = data.get("js") or {}
        return js.get("data") or data.get("data") or []

    def create_link(self, cmd: str) -> str | None:
        data = self._api(type="itv", action="create_link", cmd=cmd, JsHttpRequest="1-xml")
        js = data.get("js") or {}
        link = js.get("cmd") or js.get("url")
        if link and link.startswith("ffmpeg "):
            link = link.split(" ", 1)[-1]
        return link

    def create_timeshift_link(self, cmd: str, start: datetime, duration_min: int) -> str | None:
        """Resolve a catch-up/timeshift playback URL for a past program.

        Stalker/MAG portals expose this via the same create_link action but
        with a start timestamp + duration appended to the stream cmd.
        """
        ts_cmd = f"{cmd}&start={start.strftime('%Y-%m-%d:%H-%M')}&duration={duration_min}"
        data = self._api(
            type="itv",
            action="create_link",
            cmd=ts_cmd,
            JsHttpRequest="1-xml",
        )
        js = data.get("js") or {}
        link = js.get("cmd") or js.get("url")
        if link and link.startswith("ffmpeg "):
            link = link.split(" ", 1)[-1]
        return link

    def discover_macs(self, attempts: int = 8) -> list[dict]:
        """Probe random MAG-style MACs for a portal (best-effort)."""
        found = []
        for _ in range(attempts):
            mac = _rand_mac()
            try:
                c = StalkerClient(self.portal_url, mac)
                hs = c.handshake()
                tok = (hs.get("js") or {}).get("token") or hs.get("token")
                if tok:
                    found.append({"mac": mac, "token": True, "raw_keys": list(hs.keys())[:8]})
            except Exception as e:
                log.debug("mac %s fail: %s", mac, e)
        return found


def parse_epg_xmltv(text: str) -> list[dict]:
    """Minimal XMLTV parse without heavy deps."""
    programmes = []
    # channel map
    channels = {}
    for m in re.finditer(r'<channel id="([^"]+)">[\s\S]*?<display-name[^>]*>([^<]+)', text):
        channels[m.group(1)] = m.group(2)
    for m in re.finditer(
        r'<programme start="(\d+)"\s+stop="(\d+)"\s+channel="([^"]+)"[\s\S]*?<title[^>]*>([^<]*)',
        text,
    ):
        programmes.append(
            {
                "start": m.group(1),
                "stop": m.group(2),
                "channel_id": m.group(3),
                "channel_name": channels.get(m.group(3), m.group(3)),
                "title": m.group(4),
            }
        )
    return programmes
