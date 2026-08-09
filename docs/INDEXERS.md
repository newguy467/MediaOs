# Indexers — without Prowlarr / Jackett (and when to keep them)

## Default path (recommended)

**Prowlarr is optional — only needed for private trackers** if you do not want to configure Cardigann credentials yourself.

MediaOs indexes releases via:

1. **Built-in public indexers** (YTS, EZTV, 1337x, TPB, Lime, Nyaa, BitSearch, Knaben, BT4G, SolidTorrents, …)
2. **Cardigann definitions** — Jackett’s full YAML pack, synced automatically
3. **Local Torznab rows** you Add from Catalog / Prowlarr / Jackett UI

```env
CARDIGANN_ENABLED=true
CARDIGANN_AUTO_SYNC=true
CARDIGANN_AUTO_SYNC_ON_STARTUP=true
CARDIGANN_SYNC_MAX_FILES=0          # 0 = ALL Jackett definitions
INDEXER_HEALTH_ENABLED=true
INDEXER_HEALTH_FAIL_DISABLE=5
FLARESOLVERR_URL=http://flaresolverr:8191   # for CF-protected publics/privates
```

After setup wizard **Finish**, bootstrap pulls definitions in the background.  
UI: **Settings → Indexers → Sync all Jackett defs**.

## Private trackers

You can use private trackers **without** Prowlarr:

1. **Settings → Indexers → Cardigann catalog**
2. Search the tracker name → open detail
3. Pick base URL from dropdown
4. Enter **username / password / cookie / API key**
5. Enable **FlareSolverr** if the site uses Cloudflare
6. **Test** → **Add to MediaOs**

Defs come from the same Jackett definition tree (synced in full). Login/cookie fields are stored per indexer.

Optional: still link Prowlarr/Jackett and **Add** from those tabs if you already maintain indexers there.

## Health monitoring

Every few hours MediaOs tests enabled indexers. After **5 consecutive failures** (configurable) the indexer is **auto-disabled** (Prowlarr-style).  
Manual: **Run health check** on the Indexers page.

## Torznab ecosystem

Each added indexer exposes a minimal Torznab-compatible feed:

```text
GET /api/indexers/torznab/{id}/api?t=search&q=query
```

Use this if another app must query MediaOs as a Torznab source. MediaOs itself searches indexers natively (no external hub required).

## When to keep Prowlarr or Jackett

| Keep them if… | Skip them if… |
|---------------|---------------|
| You rely on Prowlarr appsync to other *arrs | MediaOs is your only *arr |
| Complex private trackers you already configured there | Public + Cardigann private logins are enough |
| You want their UI as source of truth | You use MediaOs Indexers UI only |

**Bottom line:** steal/sync **all** Jackett defs, use builtins + FlareSolverr + health. Prowlarr/Jackett remain **optional importers**, not required hubs.
