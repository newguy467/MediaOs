# Module Store, paths, clients, quality packs, migration

## Module Store
`GET /api/modules` — catalog with tags, categories, path needs, conflicts  
UI: Module Store page (search / filters / warnings)

## Path conflicts
`GET /api/library/path-conflicts` — duplicate paths, host-path heuristics, module gaps  
`GET /api/library/path-help` — per-field help

## Client Apply
`GET /api/tools/clients/plan`  
`POST /api/tools/clients/apply` — categories + optional qB category create

## Quality packs
`GET /api/quality-ui/presets` — hd / uhd / anime / any  
`POST /api/quality-ui/presets/{id}/apply`

## Migration wizard
UI page `migrate` — preflight then import  
`POST /api/migrate/validate` → `POST /api/migrate/{radarr|sonarr|…}`

## First-run tour
`FirstRunTour` on dashboard until dismissed (`localStorage mediaos.tour.done`)

## Settings help
`GET /api/tools/settings-help`
