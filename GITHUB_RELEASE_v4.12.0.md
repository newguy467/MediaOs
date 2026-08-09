# MediaOs v4.12.0

Safe AI Assistant (Ollama + llama3.2) + Homelab Links + shipment polish.

## Enable AI
```bash
docker compose --profile ai up -d --build
./scripts/pull_ollama_model.sh
```

## Highlights
- AI Search in sidebar + floating panel
- Wanted, indexer health, queue, quality suggestions, error diagnosis
- Homelab Links (persisted)
- Full tree + release workflow

See `docs/SAFE_AI.md` and `docs/AUDIT_v4.12.md`.
