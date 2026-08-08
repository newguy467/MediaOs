# Cardigann definitions

Jackett/Cardigann-compatible `.yml` files live here (or under
`CARDIGANN_DEFINITIONS_PATH`).

## Fully automatic (default)

You do **not** need to run scripts or press sync:

1. **Setup wizard Finish** → background bootstrap seeds + syncs definitions
2. **Every startup** (after setup) → bootstrap refreshes as needed
3. **Weekly** scheduler job → full Jackett YAML refresh

Optional manual API: `POST /api/setup/bootstrap` or `POST /api/indexers/cardigann/sync`

Disable with `CARDIGANN_AUTO_SYNC=false` only if you manage files yourself.
Mark local edits with a `mediaos-local` comment so auto-sync skips them.

Built-in public indexers (YTS, EZTV, 1337x, …) work with **zero** Cardigann/Jackett config.


## Private trackers

Cardigann here is a **subset** of Jackett (form/cookie/API + selectors).
For complex private trackers, connect **Prowlarr** or **Jackett Torznab** in the setup wizard and pick indexers there — that path is fully supported and preferred.
