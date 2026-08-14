# Why feature audits passed while release audit failed

| Focus | Feature audits (2.0.3–2.0.7) | Release audit (2.0.8) |
|-------|------------------------------|------------------------|
| Pipeline cohesion | Yes | Assumed |
| npm lock vs package.json | Not checked | Broken → fixed |
| Compose app data volumes | Not checked | Missing → fixed |
| Dual migrations conflict | Documented dual path | Made Alembic idempotent |
| Default open auth | Known as “dev default” | Bootstrap key now |
| Player can read /config | Not scanned | Removed |
| Image/tag floating | Not scanned | Pinned |

Lesson: “cohesive features” ≠ “reproducible, secure, persistent install.”
