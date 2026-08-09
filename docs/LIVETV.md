## Automatic by default

On every MediaOs start (when `livetv_seed_iptv_org` / `livetv_auto_grab` are true):

1. If no Live TV sources → seed **US + Entertainment** playlists from iptv-org  
2. Bind matching **XMLTV EPG URLs** (GitHub Pages)  
3. Sync channel lists  
4. Index EPG (source URLs + optional Node sidecar)  
5. Scheduler keeps M3U / EPG / health running  

No UI click required for a working IPTV baseline.

# Live TV — full IPTV pack

MediaOs Live TV is a first-class module: playlists, XMLTV EPG (iptv-org / epg-grabber output), health cleanup, and Jellyfin export.

## Defaults

**Add iptv-org defaults + EPG** seeds:

| Playlist | Auto-bound EPG |
|----------|----------------|
| US | `…/epg/guides/us/tvtv.us.epg.xml` |
| Entertainment | same US guide |
| UK (optional preset) | `…/uk/sky.com.epg.xml` |
| AU | `…/au/ontvtonight.com.epg.xml` |

These XMLTV files are **published by [iptv-org/epg](https://github.com/iptv-org/epg)** (built with **epg-grabber**). MediaOs does not scrape TV sites; it downloads and indexes the guides.

## EPG merge

Every source `epg_url` plus optional `livetv_epg_extra_urls` (comma-separated) are fetched and merged into one cache.

```
POST /api/livetv/epg/refresh
GET  /api/livetv/epg/presets
POST /api/livetv/epg/presets/{key}/bind
```

## Channel ↔ guide mapping

Playlist `tvg-id` should match XMLTV `channel id`. If not:

- **Map EPG** on a channel (suggests ids from the guide)
- Or `PATCH /api/livetv/channels/{id}` with `{"epg_tvg_id": "BBCOne.uk"}`

Effective id = `epg_tvg_id` override if set, else `tvg_id`.

## Offline cleanup (12h)

Every ~30 minutes MediaOs probes a batch of streams.

| Setting | Default |
|---------|---------|
| `livetv_offline_hours` | 12 |
| `livetv_offline_action` | `delete` (`disable` to soft-remove) |
| `livetv_health_batch` | 40 |
| `livetv_health_interval_minutes` | 30 |

Channels that fail and have not been OK for longer than offline hours are deleted (or disabled).

```
POST /api/livetv/health/run
```

## Jellyfin

```
Playlist:  /api/livetv/export/playlist.m3u
Guide:     /api/livetv/export/guide.xml
```

Streams are proxied through MediaOs so both UIs share one path.

## Companion grabber (optional)

If public guides are thin for your region, run [iptv-org/epg](https://github.com/iptv-org/epg) as a sidecar, serve `guide.xml`, and set that URL as `epg_url` or in `livetv_epg_extra_urls`.


## What does Node do here?

**Node.js is only needed if you run the grabber yourself.**

| Layer | Runtime | Job |
|-------|---------|-----|
| **epg-grabber** (library) | Node | HTTP to TV guide sites + parse HTML/JSON → programmes |
| **iptv-org/epg** | Node (npm) | Hundreds of **site configs** + `npm run grab` → **XMLTV file** |
| **iptv-org GitHub Pages** | CI (Node in the cloud) | Upstream already publishes `*.epg.xml` |
| **MediaOs** | Python | **Downloads** XMLTV URLs, indexes by `tvg-id`, UI + Jellyfin export |

So:

- **Default (no Node on your server):** MediaOs uses  
  `https://iptv-org.github.io/epg/guides/us/tvtv.us.epg.xml`  
  Upstream’s CI already ran Node/epg-grabber for you.
- **Sidecar:** Your machine runs Node on a schedule (fresher data, custom sites). MediaOs still only consumes an **XMLTV URL** — it never embeds Node.

Node does **not** play streams, proxy M3U, or replace Live TV. It only **builds the guide file**.

## Sidecar

MediaOs can run the same Node epg-grabber sidecar itself — no separate compose
file needed:

```bash
docker compose -f docker-compose.yml --profile epg up -d
```

This starts the `iptv-org-epg` service already defined in `docker-compose.yml`
(same Node 20 image, same `scripts/epg-sidecar-entrypoint.sh` entrypoint). Set
`EPG_SITE` / `EPG_DAYS` / `EPG_CRON_HOURS` in your `.env` to configure it.

Files:

- `scripts/epg-sidecar-entrypoint.sh` — clone iptv-org/epg, grab, serve `guide.xml`

Point MediaOs at the guide:

```env
livetv_epg_extra_urls=http://iptv-org-epg:3000/guide.xml
```

Then: `POST /api/livetv/epg/refresh`

Site list: https://github.com/iptv-org/epg/blob/master/SITES.md

```env
EPG_SITE=tvtv.us
EPG_DAYS=2
EPG_CRON_HOURS=6
```

**Use the sidecar** when public guides lag or your region is thin.  
**Skip it** when US/UK/AU GitHub Pages guides are enough (zero extra containers).
