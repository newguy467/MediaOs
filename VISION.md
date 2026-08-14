# MediaOS v2 — The Complete Self-Hosted Media Operating System

**One app. One database. Every media type. Full *arr ecosystem absorption + games + tracking + scrobbling.**

MediaOS v2 is the spiritual and technical successor that fully absorbs the best ideas from the open-source ecosystem:

| Source Project     | What we absorb                                      | MediaOS v2 Home                  |
|--------------------|-----------------------------------------------------|----------------------------------|
| **bobarr**         | Extreme simplicity, multi-quality keep philosophy   | Core pipeline + Quality policy   |
| **Cinephage**      | Stream-as-primary, dense modern UI, Live TV depth   | Stream engine + Live TV module   |
| **headphones**     | Artist → Album → Track hierarchy + completeness     | Music module (deepened)          |
| **mylar3**         | Pull-lists, story-arcs, metatagging                 | Comics / Manga module            |
| **Organizr**       | Beautiful service organizer / tabs                  | Homelab Links + Dashboard        |
| **Prismarr**       | Extremely dense dashboard, calendar, control strip  | Dashboard & Calendar system      |
| **Questarr**       | Full *arr-style video game management               | **Games module (new)**           |
| **recyclarr**      | Live TRaSH Guides + config-as-code quality          | Native Quality Engine (already)  |
| **scrob**          | Local scrobbling / watch history / progress         | **Scrobbling & History layer**   |
| **trawl**          | Advanced indexer tooling + FlareSolverr depth       | Indexer & Search layer           |
| **Yamtrack**       | Multi-media tracking (movies/TV/anime/games/books)  | **Unified Tracking layer**       |
| MediaOs v4         | Shared pipeline, modules, adult, hunt, maintenance  | Foundation (upgraded)            |

## Core Philosophy (v2)

1. **Absorb, don’t reinvent poorly**  
   Take the best UX patterns, data models, and workflows from the open-source projects above and re-implement them cleanly inside one coherent codebase under MediaOS’s license and architecture.

2. **One shared pipeline for everything**  
   Metadata → Discover → Search → Score (TRaSH + custom) → Grab **or** Stream → Organize → Scrobble / Track Progress → Maintain → Activity

3. **Modules + Tracking layer**  
   Media types (Movies, TV, Music, Books, Audiobooks, Comics, Adult, Live TV, Podcasts, **Games**) are modules.  
   Scrobbling, watch/play progress, and multi-service tracking are a horizontal layer that works across all modules.

4. **Basic + Advanced + Power modes**  
   New users get a clean Movies + TV experience.  
   Power users unlock full hierarchy, custom formats, hunt rules, Live TV editor, Games, Scrobbling analytics, etc.

5. **Stream-first is first-class**  
   “Add as stream” sits next to Grab everywhere. Live TV, debrid streams, and .strm generation are core, not afterthoughts.

6. **Local-first tracking & scrobbling**  
   Your watch history, play progress, and “continue watching” live in MediaOS. Optional export to Trakt / others.

7. **Open source absorption, clean re-implementation**  
   Ideas, patterns, and public algorithms are fair game. We re-implement in MediaOS’s FastAPI + React style. We do **not** wholesale copy proprietary or license-incompatible code.

## What MediaOS v2 replaces / absorbs

| Legacy / Competing App      | MediaOS v2 Equivalent                          |
|-----------------------------|------------------------------------------------|
| Sonarr + Radarr             | Movies + TV modules (full parity + stream)     |
| Lidarr + Headphones         | Music module (full hierarchy)                  |
| Readarr                     | Books + Audiobooks                             |
| Mylar3                      | Comics / Manga                                 |
| Whisparr                    | Adult module                                   |
| Prowlarr / Jackett + trawl  | Indexers + advanced search                     |
| Recyclarr                   | Live TRaSH Quality Engine                      |
| Maintainerr + Huntarr       | Rules engine + Hunt engine                     |
| Overseerr / Jellyseerr      | Requests + Discover + Smart Lists              |
| Cinephage (key strengths)   | Stream path + Live TV + dense UX               |
| Prismarr                    | Dashboard density + calendar                   |
| bobarr                      | Simplicity + multi-quality policy              |
| scrob + Yamtrack            | Scrobbling + Unified Tracking layer            |
| Questarr                    | **Games module**                               |
| Organizr                    | Homelab Links / Services page                  |
| Bazarr                      | Subtitles                                      |

## Non-goals (still)

- Built-in VPN (use Gluetun / external)
- Replacing the media *player* (Jellyfin / Plex / Emby / third-party clients stay)
- Multi-tenant SaaS
- Reverse-engineering private trackers (prefer Torznab / Prowlarr-compatible)

## Audience

- People tired of running 8–15 containers
- People who want one beautiful control plane for their entire media + games library
- People who want local scrobbling and progress without depending only on Trakt
- Power users who still want deep quality control, hunt, and maintenance rules

**MediaOS v2 = the single center of your self-hosted media *and* games world.**
