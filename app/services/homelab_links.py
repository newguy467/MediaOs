"""
Homelab Apps / Links page (Organizr-lite).

Simple, high-value page for linking other self-hosted tools
(iframes or external URLs) without leaving MediaOs.
"""
from __future__ import annotations

from typing import Any

# Default starter links — users edit via settings / UI
DEFAULT_LINKS = [
    {"name": "Jellyfin", "url": "http://jellyfin:8096", "icon": "play", "iframe": True},
    {"name": "qBittorrent", "url": "http://qbittorrent:8080", "icon": "download", "iframe": True},
    {"name": "Portainer", "url": "http://portainer:9000", "icon": "box", "iframe": False},
    {"name": "Docs", "url": "https://github.com/newguy467/mediaos", "icon": "book", "iframe": False},
]


def get_links() -> list[dict[str, Any]]:
    # Later: load from DB / settings
    return DEFAULT_LINKS


def save_links(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Foundation: echo back; persist in settings store next
    return links
