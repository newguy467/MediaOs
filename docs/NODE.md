# Node.js in MediaOs — full project audit

MediaOs is a **Python FastAPI + React** all-in-one. Node is used only where the ecosystem is clearly better.

## Implemented Node uses

| Area | How | Default |
|------|-----|---------|
| **UI build** | Docker stage `FROM node:20` → Vite + React + Tailwind + DaisyUI → static assets | Always (image build) |
| **hls.js** | npm dep; Live TV `<HlsVideo>` for `.m3u8` in browsers without native HLS | Always (bundled in UI) |
| **iptv-org/epg** | Compose service `iptv-org-epg` (Node 20) runs epg-grabber site configs → `guide.xml` | Profile `full` / `epg` |

## Related companions (Node under the hood, separate images)

| Service | Why not inside MediaOs process |
|---------|--------------------------------|
| **FlareSolverr** | Headless Chromium + Node API for Cloudflare. Heavy; keep as sidecar (`docker-compose.integrations.example.yml`, profile `full`) |
| **Prowlarr / Jackett** | .NET, not Node — Torznab indexers |
| **Cardigann defs** | YAML + git sync (`scripts/sync_cardigann_defs.sh`) — no Node |

## Audited — do **not** put Node here

| Area | Stack | Reason |
|------|-------|--------|
| Search / grab / quality | Python | *arr core |
| Organize / hardlinks | Python | Filesystem |
| qBittorrent / SABnzbd clients | Python httpx | APIs |
| Player transcode | **ffmpeg** | Not Node |
| TRaSH profiles, Hunt, Cleanup | Python | Schedulers |
| Subtitles | Python clients | OpenSubtitles etc. |
| YouTube | **yt-dlp** (Python) | Already best-in-class |
| Metadata (TMDb, TPDB, OpenLibrary) | Python | REST |
| Auth / settings / DB | Python + SQLAlchemy | — |
| Definitions / Cardigann parse | Python YAML | — |

## Optional future (only if needed)

| Idea | Verdict |
|------|---------|
| Puppeteer/Playwright in-process | Prefer FlareSolverr sidecar |
| TypeScript rewrite of UI | Optional; JSX is fine |
| Node subtitle tools | No gain over Python |
| Embed epg-grabber in main image | Sidecar preferred (weight + update cycle) |

## Commands

```bash
# UI only (dev)
npm install
npm run dev

# Production image (Node stage builds UI, runtime is Python)
docker build -t mediaos .

# Full stack with local EPG grab + optional FlareSolverr
docker compose --profile full up -d
```

## Env

```env
LIVETV_SEED_IPTV_ORG=true
LIVETV_AUTO_GRAB=true
LIVETV_EPG_SIDECAR_URL=http://iptv-org-epg:3000/guide.xml
FLARESOLVERR_URL=http://flaresolverr:8191
EPG_SITE=tvtv.us
```

**Bottom line:** Node = **UI toolchain + HLS playback library + optional EPG scraper + optional FlareSolverr**. Everything else stays Python/ffmpeg.
