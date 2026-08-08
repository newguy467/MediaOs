# YouTube in MediaOs

## Built-in capabilities
- Channel / playlist subscriptions via RSS
- Auto-download with **yt-dlp**
- **SponsorBlock** segment removal on download (`youtube_sponsorblock_remove`)
- Optional cookies (file or browser) for age-restricted / member content
- In-app player for local files

## What YT-Lite-Tunnel is (and is not)
[YT Lite Tunnel](https://github.com/) is a **network-level YouTube ad proxy** (route only YouTube traffic through a tunnel to strip ads in the browser/app). It is **not** a downloader or library manager.

MediaOs already removes sponsors at **download time** via SponsorBlock. For **live browsing** without ads, users can:

1. Use an external client (Happ / similar) with a YT-Lite-style subscription, **or**
2. Point `youtube_proxy` at a SOCKS/HTTP proxy if yt-dlp needs region unlock (e.g. through Gluetun).

## Recommended setup
- Keep download + SponsorBlock in MediaOs (library path, Jellyfin-friendly files).
- For interactive watching without downloading, use Jellyfin/Plex or an ad-aware client.
- Do not embed a full VPN/proxy stack inside MediaOs — use Gluetun externally.

## Config keys
| Key | Purpose |
|-----|---------|
| `youtube_library_path` | Where videos land |
| `youtube_format` | yt-dlp format selector |
| `youtube_sponsorblock_remove` | Categories to strip |
| `youtube_cookies_path` / `youtube_cookies_from_browser` | Auth |
| `youtube_proxy` | Optional proxy for yt-dlp only |
