## Implemented in v4.12.0 (was still open)

| Item | Status |
|------|--------|
| Live TV channel editor | PATCH + reorder + bulk + editor list + sort_order |
| Multi-quality keep | desired_qualities enforced in grab_release |
| Comic pull auto-grab | auto_grab_from_pull_list in pull sync cycle |
| Stream next to Grab | Interactive search Stream button → /api/overhaul/streams |
| Plex/Tautulli now playing | /api/now-playing + dashboard widget |

# Gap audit vs source zips (post 4.0.2)

## Implemented in MediaOs v4 foundation

| Source | Idea | MediaOs status |
|--------|------|----------------|
| Recyclarr | Live TRaSH Guides | live fetch + Quality Profiles sync panel |
| Mylar3 | Pull list + story arcs | models, API, Comics UI tabs |
| Headphones | Music hierarchy + completeness | hierarchy UI + track completeness |
| Cinephage | Stream-as-primary, Live TV | stream helpers exist; Live TV channel editor needs polish |
| Prismarr | Dense calendar + multi widgets | month grid calendar + dashboard strip |
| Bobarr | First-run simplicity, multi-quality | modules wizard = simplicity; multi-quality policy still thin |
| Organizr | Apps/Links | service stub; UI page thin |
| Cleanuparr | Queue cleaner | native cleanup service |
| Huntarr | Aggressive hunt | plan/run + scheduler job + Wanted button |
| YT-Lite | Ad-free YouTube tunnel | different domain; SponsorBlock covers download path |

## Still worth improving

1. Live TV channel editor (enable/order/logos/groups) — Cinephage depth
2. Keep multiple qualities policy in organize/grab (Bobarr)
3. Homelab Links UI page (wire homelab_links.py)
4. Plex/Tautulli now playing widget (Prismarr optional)
5. Stream button next to Grab in movie/TV detail interactive search
6. Stronger CF bypass for stubborn indexers (Cinephage)
7. Comic auto-grab from pull-list worker
8. Stronger *arr DB import validation checklist

## VPN note

Gluetun remains external. MediaOs stores provider credentials for compose generation + health checks
(ProtonVPN, Surfshark, Mullvad, NordVPN, PIA, ExpressVPN, custom WireGuard).
