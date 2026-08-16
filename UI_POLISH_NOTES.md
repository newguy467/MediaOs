# MediaOS UI Polish (applied)

Date: 2026-08-16

## Fixes included

1. **Sidebar on the left** — DaisyUI drawer was overridden by `display:flex`, which pushed the nav rail to the right. Restored CSS grid so the primary sidebar stays on the left (matches mockups).

2. **Consistent button / icon sizes** — Toolbar icons (including RSS Sync) no longer expand. `btn-sm` height unified at 2rem; SVGs locked to 1rem.

3. **Settings typography** — Single scale for page titles, section headers, card labels, form labels, and hints (removed mixed 10px/11px/xs sizes).

4. **Page titles** — Outliers (`text-xl` / `text-2xl` toolbars) normalized to `.mr-page-title` (1.5rem / weight 800).

5. **PageChrome** — Top “MediaOS” logo bar is mobile-only; desktop matches mockups (logo only in the left sidebar).

6. **Global polish CSS** — Cards, poster grids, search pills, nav active pills, spacing, and borders aligned to the mockup collage.

## Files changed

- `ui/src/styles.css`
- `ui/src/app.jsx`
- `ui/src/icons.jsx`
- `ui/src/components/ui.jsx`
- `ui/src/pages/tv.jsx`
- `ui/src/pages/settings-hub.jsx`
- `ui/src/pages/settings-config-group.jsx`
- `ui/src/pages/about.jsx`
- `ui/src/pages/books.jsx`

## After unpack

```bash
cd mediaos-next   # or your folder name
npm ci            # if needed
npm run build     # rebuild static UI into app/static
# or: npm run dev
docker compose up -d --build
```
