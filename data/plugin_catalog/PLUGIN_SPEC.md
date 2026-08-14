# MediaOS Plugin Spec

Community plugins install into the data directory (`/config/plugins` or `data/plugins`)
and are discovered at startup.

## Layout

```
my-plugin/
  mediaos.plugin.json   # required manifest
  plugin.py             # required entry (or path in "entry")
  ... optional assets
```

## Manifest (`mediaos.plugin.json`)

```json
{
  "id": "community.my-plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "What it does",
  "author": "You",
  "category": "integrations",
  "entry": "plugin.py",
  "hooks": ["startup"]
}
```

- `id` — unique, prefer `community.*` or `vendor.*`
- `entry` — Python file relative to the plugin folder (default `plugin.py`)

## Entry module

```python
def register_plugin(register):
    def on_startup():
        ...
    register(
        "community.my-plugin",
        name="My Plugin",
        version="1.0.0",
        hooks={"startup": on_startup},
    )
```

`register` is provided by MediaOS. Hooks are invoked via `run_hook(name, ...)`.

## Install sources

| Type | How |
|------|-----|
| Catalog | Module & Plugin Store → Community plugins → Install |
| GitHub repo | Store → Install from GitHub (`owner/repo` + branch) |
| Remote catalog | Set `plugin_registry_url` to a GitHub raw JSON URL |
| Env | `PLUGINS=my_package.plugin` Python import path |

## Catalog JSON (GitHub-backed)

Host a `catalog.json` in a GitHub repo and point MediaOS at the raw URL:

```
plugin_registry_url=https://raw.githubusercontent.com/OWNER/REPO/main/catalog.json
```

Schema: `{ "schema_version": 1, "name": "...", "plugins": [ { id, name, description, version, install: { type, repo, ref } } ] }`

Install types: `github_archive`, `github_release`, `url`, `bundled`.

## Security notes

- Plugins run **in-process** with app privileges — only install from sources you trust.
- Zip extraction rejects path traversal (`..`, absolute paths).
- Prefer official / reviewed catalog entries when possible.
