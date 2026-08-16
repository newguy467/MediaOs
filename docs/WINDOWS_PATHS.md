# Windows / Docker Desktop paths

## Rule
- **Inside containers** MediaOS uses POSIX paths: `/movies`, `/tv`, `/downloads`.
- **On the host** (Windows) you set `MOVIES_PATH`, `TV_PATH`, `DOWNLOADS_PATH` in `.env` to folders Docker Desktop can mount.

## Good examples
```env
MOVIES_PATH=./data/movies
TV_PATH=./data/tv
DOWNLOADS_PATH=./data/downloads
```
Or absolute:
```env
MOVIES_PATH=D:/Media/Movies
```
Docker Desktop converts these; the app still sees `/movies`.

## Avoid
- Putting `D:\Media\Movies` **inside** MediaOS library settings — that is a host path.
- Setting library path and downloads path to the **same** folder (breaks hardlinks; path-conflict detector warns).

## PathMap
If organize sees container paths but tools run on the host (or the reverse), add PathMap rules:
`GET/POST /api/library/path-maps` and dry-run before apply.

## Check
`GET /api/library/path-conflicts` or Settings → Path health card.
