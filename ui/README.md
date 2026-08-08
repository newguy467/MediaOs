# mediaos UI (Vite)

Production UI is built with Vite + React. Source lives here; the FastAPI
image serves the build output from `app/static/`.

## Develop

```bash
# terminal 1 — API
uvicorn app.main:app --reload --port 8000

# terminal 2 — UI
npm install
npm run dev          # http://localhost:5173  (proxies /api → :8000)
```

## Production build

```bash
npm ci
npm run build        # → app/static/index.html + app/static/assets/*
```

The Docker image runs this build in a multi-stage layer automatically.

## Legacy CDN UI

Pre-Vite single-file UI is preserved as:

- `app/static/app.js`
- `app/static/index.cdn.html`

Point a browser at `/index.cdn.html` if you need the old zero-build path.
