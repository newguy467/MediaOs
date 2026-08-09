# First-run setup

MediaOs opens a **short wizard** until setup is complete.

## Steps

1. **Welcome** — what is automatic  
2. **Admin & users** — username/password, role, optional extra users  
3. **Libraries** — Movies & TV required; toggle others; Adult needs a 5-digit PIN  
4. **Folders** — paths inside the container (map disks in Compose)  
5. **Finish** — saves everything and starts background bootstrap  

## Automatic after Finish

- Cardigann / built-in indexers  
- Quality profiles  
- Live TV iptv-org seed + EPG (if Live TV enabled)  
- Cleanup defaults  

Configure qBittorrent, Prowlarr, Jellyfin, VPN later under **Settings** if you need them.


**Prowlarr/Jackett are optional** — only for private trackers if you prefer their UI. See `docs/INDEXERS.md`.
