#!/usr/bin/env bash
# Pull the required Safe AI model (llama3.2) into the ollama service.
set -euo pipefail
MODEL="${OLLAMA_MODEL:-llama3.2}"
COMPOSE="${COMPOSE_FILE:-docker-compose.yml}"

echo "==> Ensuring ollama is up (profile ai)..."
if docker compose -f "$COMPOSE" ps ollama 2>/dev/null | grep -q Up; then
  echo "  ollama already running"
else
  docker compose -f "$COMPOSE" --profile ai up -d ollama
fi

echo "==> Pulling model: $MODEL"
docker compose -f "$COMPOSE" exec -T ollama ollama pull "$MODEL"
echo "==> Done. Model $MODEL is ready for MediaOS Safe AI."
