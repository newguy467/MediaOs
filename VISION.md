# MediaOs v4 — The True All-in-One Media OS

**One app. One database. Every library type. Full *arr replacement.**

MediaOs v4 is designed to completely replace the day-to-day need for:

| Legacy App          | MediaOs Module                          | Target Status |
|---------------------|-----------------------------------------|---------------|
| Radarr              | Movies                                  | Full parity + stream path |
| Sonarr              | TV                                      | Full parity + stream path |
| Lidarr              | Music (artist → album → track)          | Full hierarchy + completeness |
| Readarr             | Books + Audiobooks                      | Full parity |
| Bazarr              | Subtitles                               | Parity or better |
| Prowlarr / Jackett  | Indexers (Torznab + Cardigann + built-in) | Largely replaces |
| Recyclarr           | Live TRaSH Guides + Custom Formats + Profiles | Native live sync |
| Maintainerr         | Library maintenance / cleanup rules     | Native rules engine |
| Huntarr / similar   | Aggressive missing / upgrade / hunt     | Native hunt engine |
| Overseerr / Jellyseerr | Requests + Discover + Smart Lists    | Built-in |
| Mylar3              | Comics / Manga (pull-list + story arcs) | Full depth |
| Headphones          | Music wanted hierarchy                  | Merged into Music |
| Cinephage strengths | Live TV channel editor, stream-as-primary, modern UX density | Integrated |
| Organizr            | Apps / Links page                       | Homelab Links |
| Cleanuparr          | Queue / stalled / malware cleaner       | Native (already strong) |

## Design Principles (v4)

1. **Shared pipeline for every media type**  
   metadata → discover → search → score (TRaSH) → grab **or stream** → organize → maintain → activity

2. **Quality first**  
   Real live TRaSH Guides feed, custom formats, quality profiles, scoring matrices — not static snapshots.

3. **One database, one UI**  
   No sync hell between multiple *arr instances. SQLite (default) or Postgres.

4. **Basic + Advanced modes**  
   New users get a simple movie/TV-first experience. Power users unlock full hierarchy, custom formats, hunt rules, Live TV editor, etc.

5. **Absorb what makes sense**  
   Indexers, quality, subtitles, requests, Live TV, comics depth, music hierarchy, maintenance rules, hunt logic all live inside MediaOs.  
   Keep external only what is proven and specialized (qBittorrent / other download clients, Gluetun for VPN, Jellyfin/Plex/Emby as players).

6. **Progressive replacement + strong migration**  
   Import from Sonarr/Radarr/Lidarr/Readarr (library, profiles, custom formats, monitored status, history).  
   Side-by-side coexistence supported during transition.

7. **Hybrid modern UI**  
   Evolve the current React + Tailwind/DaisyUI foundation toward denser, more polished layouts inspired by Cinephage while remaining approachable.

## Non-goals (still)

- Full proprietary tracker reverse-engineering (prefer Prowlarr Torznab for exotic private trackers)
- Built-in VPN (use Gluetun)
- Multi-tenant SaaS hosting
- Replacing the media *player* (Jellyfin/Plex/Emby stay)

## Audience

- People who already run the *arr stack and want to consolidate
- People who have never used Sonarr/Radarr and just want a working media library manager

**MediaOs v4 = the single center of your self-hosted media world.**
