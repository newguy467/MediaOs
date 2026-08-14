# Ops: Redis multi-worker + scheduler leader election

## When you need this

Running **more than one** uvicorn/gunicorn worker or multiple MediaOS containers
against the same database.

Without Redis:
- Rate-limit / backoff state is **per process**
- Scheduler jobs may **double-run** on every replica
- Session DB is still shared (AuthSession table); memory cache is per process

## Enable

```bash
# .env
REDIS_URL=redis://redis:6379/0

# compose profile
docker compose --profile redis up -d
```

Point MediaOS at Redis:

```yaml
environment:
  REDIS_URL: redis://redis:6379/0
```

## What Redis backs

| Feature | Redis key prefix | Fallback without Redis |
|---------|------------------|------------------------|
| Indexer rate limit / backoff | `mediaos:rl:` | process-local RLock |
| Host concurrency slots | `mediaos:rl:host*` | process-local |
| Session access-token cache | `mediaos:sess:` | memory + DB |
| Scheduler leader lock | `mediaos:scheduler:leader` | every process is leader |

## Leader election

- Lock TTL defaults to `SCHEDULER_LEADER_TTL_SECONDS=45`
- Each scheduled job refreshes the lock; followers no-op
- If Redis blips, code **assumes leader** so a single-node install never stalls

## Legal / maintenance notes

- Keep root `NOTICE` when distributing `definitions/` (Jackett GPL-2.0 YAML)
- LimeTorrents remains **disabled by default**; enable only if you accept scraper risk
- Prefer Prowlarr/Jackett Torznab for private trackers over vendored scrapers
