# Built-in media player

MediaOs can play library files without Jellyfin/Plex.

## Where

- Movie / episode detail → **Play**
- Sidebar **Watch** → library browser
- Mini-player bar while browsing

## How

1. Prefer direct file stream when the browser supports the container (mp4, webm, …)
2. Otherwise ffmpeg transcodes to H.264 + AAC fragmented MP4 on the fly
3. Status: `GET /api/player/status` (ffmpeg available?)

## Paths

Only files under configured library roots are served.
