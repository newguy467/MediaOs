# Module & Plugin Store

MediaOS has two layers in the same UI (**Module Store** in the sidebar):

## 1. Built-in modules

Library domains toggled on/off (Movies & TV are **required**):

Music, Books, Games, Live TV, Podcasts, etc.

Stored as `enabled_modules` in app settings. No download required.

## 2. Community plugins (GitHub-backed)

Installable extensions that drop into `/config/plugins` (or `data/plugins`).

### Catalog sources (first wins)

1. `plugin_registry_url` — remote JSON (typically GitHub raw)
2. Bundled `data/plugin_catalog/catalog.json`

### Install methods

| Method | UI | API |
|--------|----|-----|
| Catalog entry | Community plugins → Install | `POST /api/plugins/marketplace/{id}/install` |
| Any GitHub repo | Install from GitHub tab | `POST /api/plugins/install/github` |
| Refresh remote catalog | Refresh catalog button | `POST /api/plugins/marketplace/refresh` |

### Config

```env
PLUGIN_REGISTRY_URL=https://raw.githubusercontent.com/OWNER/REPO/main/catalog.json
PLUGINS_PATH=/config/plugins
GITHUB_TOKEN=ghp_...   # optional, rate limits / private repos
PLUGINS=my_pkg.plugin  # optional comma-separated Python modules
```

### Plugin package shape

See `data/plugin_catalog/PLUGIN_SPEC.md` and the bundled example under
`data/plugin_catalog/examples/hello`.

### Security

Plugins execute **inside the MediaOS process**. Only install from repositories you trust.
