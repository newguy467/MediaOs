# MediaOs v4 Architecture

## High-level

```
┌─────────────────────────────────────────────────────────────┐
│  UI (React + Tailwind / DaisyUI → hybrid denser layouts)    │
│  Basic Mode  |  Advanced Mode  |  Homelab Links             │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST + SSE
┌──────────────────────────▼──────────────────────────────────┐
│  FastAPI  /api/{movies,tv,music,books,comics,livetv,...}    │
│  Auth + Permissions (multi-user)                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  Core Services (shared pipeline)                            │
│  • Metadata providers (TMDb, TVDb, MusicBrainz, ComicVine…) │
│  • Search + Interactive Search                              │
│  • Quality Engine (live TRaSH + custom formats + profiles)  │
│  • Grab  |  Stream-as-primary                               │
│  • Organize + Naming                                        │
│  • Wanted / Hunt engine                                     │
│  • Maintenance / Cleanup rules (Maintainerr-style)          │
│  • Subtitles                                                │
│  • Rate-limit registry                                      │
│  • Activity + Notifications                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  Domain Modules                                             │
│  Movies │ TV │ Music (hierarchy) │ Books │ Audiobooks       │
│  Comics (pull + arcs) │ Manga │ Live TV │ YouTube │ Podcasts│
│  Converter │ Requests / Smart Lists │ Dashboard widgets     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  Clients & Integrations                                     │
│  Indexers (Torznab / Cardigann / built-in)                  │
│  Download clients (qB, SAB, NZBGet, Transmission, …)        │
│  Debrid, Usenet stream, .strm writers                       │
│  *arr migrators (Sonarr/Radarr/Lidarr/Readarr import)       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  Persistence                                                │
│  SQLite (default, single-file simplicity)                   │
│  Optional Postgres                                          │
│  media_items, episodes/tracks/issues, quality_*,            │
│  downloads, activity, rules, stream_links, users, …         │
└─────────────────────────────────────────────────────────────┘
```

## Key v4 enhancements over 3.7.x

### 1. Quality Engine (Recyclarr-level)
- Live fetch from TRaSH Guides (real definitions, not only builtin snapshot)
- Custom Formats with scores, conditions, and profile assignment
- Quality Definitions (file size limits)
- Media naming formats
- Admin UI to view/edit profiles, scores, and last sync status

### 2. Music Module (Lidarr + Headphones depth)
- Full artist → album → track tree
- Album completeness percentage + missing track list
- Wanted hierarchy in UI
- MusicBrainz primary + completeness scoring

### 3. Comics / Manga (Mylar-level)
- Weekly pull-list automation (auto-search / auto-grab)
- Story-arc UI + reading order
- Issue metatagging (ComicTagger-style)
- Publisher / series / arc organization

### 4. Stream-as-primary
- “Add as stream” button next to Grab in detail views and interactive search
- .strm generation + library placement
- Usenet seekable stream path (where possible)
- Provider registry

### 5. Live TV
- Channel editor (enable / order / logos / groups)
- Portal scan (Stalker etc.) + bulk tools
- Polished EPG grid
- HLS / stream playback integration

### 6. Maintenance & Hunt
- Rule engine (Maintainerr-style): age, size, quality, tags, collections → action (delete, unmonitor, upgrade, notify)
- Hunt engine: aggressive missing / cutoff / upgrade searches with prioritization and rate-limit awareness

### 7. Indexer layer
- Strong Torznab (Prowlarr-compatible) + Cardigann YAML + curated built-ins
- Rate-limit registry UI (per-host limits, backoffs, current state)
- Capability detection

### 8. Migration
- Strong import from Sonarr / Radarr / Lidarr / Readarr databases or API
- Quality profiles + custom formats + monitored flags + history
- Side-by-side mode during transition

### 9. UI
- Basic mode: simplified movie + TV focused first-run
- Advanced mode: full power (custom formats, hunt rules, Live TV editor, music hierarchy, comics arcs…)
- Denser dashboard (calendar + multi-queue widgets inspired by Prismarr)
- Homelab Apps/Links page (Organizr-lite)

### 10. Multi-language readiness
- Core remains Python/FastAPI
- Selected high-performance or UI-adjacent pieces can use TypeScript/Node where beneficial (e.g. certain parsers, Live TV helpers, or future Svelte islands)
- Clear service boundaries so languages interoperate cleanly

## Database recommendation

- **Default**: SQLite (Cinephage-style simplicity, zero-config, single file)
- **Optional**: Postgres for larger libraries / multi-writer scenarios
- Schema designed to support both

## External services we still recommend

- Download clients (qBittorrent primary)
- Gluetun (or equivalent) for VPN
- Jellyfin / Plex / Emby / Kodi as the actual players
- Optional: Prowlarr for very exotic private trackers until MediaOs indexer coverage is complete

Everything else lives inside MediaOs.
