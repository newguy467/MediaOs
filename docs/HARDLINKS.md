# Hardlinks (downloads → library)

## Compose volume mappings (correct)

```yaml
- ${MOVIES_PATH:-./data/movies}:/movies
- ${TV_PATH:-./data/tv}:/tv
- ${MUSIC_PATH:-./data/music}:/music
- ${BOOKS_PATH:-./data/books}:/books
- ${AUDIOBOOKS_PATH:-./data/audiobooks}:/audiobooks
- ${PODCASTS_PATH:-./data/podcasts}:/podcasts
- ${COMICS_PATH:-./data/comics}:/comics
- ${MANGA_PATH:-./data/manga}:/manga
- ${YOUTUBE_PATH:-./data/youtube}:/youtube
- ${DOWNLOADS_PATH:-./data/downloads}:/downloads
```

qBittorrent must mount the **same** host `DOWNLOADS_PATH` at `/downloads`.

## Same filesystem requirement

`os.link` only works when source and destination are on the same device.

| Host layout | Hardlink |
|-------------|----------|
| `./data/downloads` + `./data/movies` on one disk | Yes |
| Movies on `/mnt/disk1`, downloads on `/mnt/disk2` | No → automatic **move** fallback |

## Behaviour (2.0.20)

1. Organize prefers hardlink (`LIBRARY_PREFER_HARDLINK=true`).
2. On success, the torrent **stays in qBittorrent** so seeding continues.
3. Set `LIBRARY_REMOVE_DOWNLOAD_AFTER_HARDLINK=true` to remove the client item but keep files (`deleteFiles=false`).
4. On cross-device or link failure → `shutil.move`, then remove torrent **with** files.

## Verify inside the container

```bash
docker compose exec mediaos sh -c 'stat -c %d /downloads /movies'
# same number ⇒ hardlinks possible
```
