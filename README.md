# MediaOs v4.13.4 — True All-in-One Media OS

**One app that replaces Sonarr + Radarr + Lidarr + Readarr + Bazarr + Prowlarr + Recyclarr + Maintainerr + Huntarr + NeutArr + Whisparr (+ Live TV, comics depth, stream-as-primary, and more).**

Current version: **4.13.4**

## Why MediaOs?

People are tired of juggling 8–12 containers just to manage a media library.  
MediaOs consolidates the entire *arr ecosystem into a single, coherent application with:

- Shared pipeline for every media type
- Live TRaSH Guides quality system
- Full music hierarchy + comics pull-list / story-arcs
- Stream-as-primary path
- Native maintenance rules + hunt engine
- Built-in stalled-download cleanup (no external Swaparr needed)
- Native hardlink-into-library option (zero extra disk space while seeding)
- **Built-in Adult (Whisparr class)** — passcode gate, TPDB metadata, XXX search, arr-compat `library=adult`
- **Built-in Hunt (NeutArr / Huntarr class)** — no external NeutArr container
- **Built-in Cleanup (Cleanuparr / Swaparr class)** — stalled strikes, seed goals
- Basic mode (friendly) + Advanced mode (power)
- Strong import from existing *arr instances

### New in 4.12.0 — Safe AI + Homelab Links

- Optional local AI (Ollama + **llama3.2**) — sidebar **AI Search** + floating panel
- Tools: library search, wanted, indexer health, queue, quality suggestions, errors
- Homelab Links page (persisted) — Organizr-lite quick links
- `docker compose --profile ai up -d` then `./scripts/pull_ollama_model.sh`

**Still external (on purpose):** download clients (qBittorrent, SABnzbd, …) and your media player (Jellyfin / Plex / Emby).

## Quick start

```bash
git clone https://github.com/newguy467/MediaOs.git
cd MediaOs
cp .env.example .env
# edit paths / API keys

docker compose -f docker-compose.standalone.yml up -d --build
open http://localhost:8787
```

## What’s in 4.7.1

- Version strings aligned across `VERSION`, `package.json`, `Dockerfile`, and runtime
- Native hardlink support in the organizer (Settings → Library → “Hardlink into library instead of moving”)
- Reproducible UI builds via committed `package-lock.json`
- Improved Basic / Advanced mode gating
- Live TRaSH Guides sync improvements
- Health endpoint and startup logs report the correct version
- Cleanup engine already covers stalled downloads across companion *arr apps — no separate Swaparr required

## Docs

| File | Purpose |
|------|---------|
| VISION.md | Product goal & principles |
| ARCHITECTURE.md | Technical design |
| ROADMAP.md | Implementation phases |
| STRUCTURE.txt | Folder map |
| docs/ | Screenshots & GitHub Pages site |

## License

MIT.  
Ideas and patterns drawn from open-source projects including Cinephage, Recyclarr, Mylar3, Headphones, Prismarr, Bobarr, Organizr, and the classic *arr suite — all credit to their authors.

---

**MediaOs — stop switching apps. Manage everything in one place.**
