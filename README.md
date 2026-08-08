# MediaOs v4 — True All-in-One Media OS

**One app that replaces Sonarr + Radarr + Lidarr + Readarr + Bazarr + Prowlarr + Recyclarr + Maintainerr + Huntarr (+ Live TV, comics depth, stream-as-primary, and more).**

This is the **4.0.0-foundation** package: the big-bang architecture, elevated vision, and enhanced modules on top of the solid 3.7.x codebase.

## Why v4?

People are tired of juggling 8–12 containers just to manage a media library.  
MediaOs v4 consolidates the entire *arr ecosystem into a single, coherent application with:

- Shared pipeline for every media type
- Live TRaSH Guides quality system
- Full music hierarchy + comics pull-list/story-arcs
- Stream-as-primary path
- Native maintenance rules + hunt engine
- Basic mode (friendly) + Advanced mode (power)
- Strong import from existing *arr instances

## Quick start (same as 3.7)

```bash
cp .env.example .env
# edit paths / API keys
docker compose -f docker-compose.standalone.yml up -d --build
open http://localhost:8787
```

## What’s new in this foundation zip

- `VISION.md` — full replacement scope
- `ARCHITECTURE.md` — system design
- `ROADMAP.md` — phased path from foundation → complete AIO
- Enhanced `trash_guide_fetch.py` (live TRaSH / Recyclarr-style)
- New `comic_arcs.py` (story-arc + reading order + metatag hooks)
- New `music_hierarchy.py` (artist → album tree + wanted hierarchy)
- New `hunt.py` (aggressive missing/upgrade engine)
- New `maintenance_rules.py` (Maintainerr-style rules)
- New `homelab_links.py` (Organizr-lite Apps/Links)
- Existing strengths retained & extended: stream_mode, comic_pull_sync, music_completeness, cleanup, arr_migrator, Live TV, quality engine, etc.

## Docs

| File | Purpose |
|------|---------|
| VISION.md | Product goal & principles |
| ARCHITECTURE.md | Technical design |
| ROADMAP.md | Implementation phases |
| STRUCTURE.txt | Folder map |
| docs/ | Screenshots & GitHub Pages site |

## Contributing / Next work

See ROADMAP.md. Highest leverage next steps:

1. Wire live TRaSH sync end-to-end + Quality Profiles admin UI
2. Full music track-level model + hierarchy UI
3. Comics story-arc models + pull-list auto-grab polish
4. Stream button next to Grab in the React UI
5. Basic vs Advanced mode switch

## License

MIT (same as upstream MediaOs).  
Ideas and patterns drawn from open-source projects including Cinephage, Recyclarr, Mylar3, Headphones, Prismarr, Bobarr, Organizr, and the classic *arr suite — all credit to their authors.

---

**MediaOs v4 — stop switching apps. Manage everything in one place.**
