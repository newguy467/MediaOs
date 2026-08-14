# Announce Lab (autobrr-style, in-app)

Instead of running a separate **autobrr** container, MediaOS can match indexer
announces inside the Homelab panel and push downloads to your existing client.

## Where

**Sidebar → Homelab → Announce Lab**

(Service links stay on the other tab for Jellyfin, Grafana, or a real autobrr
UI if you still want an external instance.)

## How it works

1. You define **filters** (match/except regex, optional size bounds).
2. Every **5 minutes** (or **Run cycle now**), MediaOS polls enabled Torznab indexers.
3. New release titles that match a filter are sent to **qBittorrent** (`mediaos-announce` category) and recorded in the download queue.
4. GUIDs are remembered so the same release is not grabbed twice.

## vs external autobrr

| | Announce Lab | External autobrr |
|--|----------------|------------------|
| Process | Inside MediaOS | Separate container |
| IRC announce networks | Not yet (Torznab/RSS poll) | Full IRC |
| Filters | Regex match/except | Advanced filter DSL |
| Download | MediaOS qBittorrent settings | Own client config |
| UI | Homelab tab | Own web UI (optional link) |

Use Announce Lab for “good enough” title filters without another service.
Link a full autobrr under **Service links** when you need IRC-grade announce speed.

## API

- `GET /api/homelab/announce` — status, filters, recent hits
- `PUT /api/homelab/announce/filters` — replace filter list
- `POST /api/homelab/announce/run` — run one cycle now
