#!/usr/bin/env bash
# Back-compat entrypoint — prefer scripts/smoke_api.sh / smoke_unit.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "Running offline unit smoke..."
python3 "$ROOT/scripts/smoke_unit.py"
if curl -sf "${MEDIAOS_URL:-http://127.0.0.1:8000}/api/health" >/dev/null 2>&1; then
  echo "Running API smoke..."
  bash "$ROOT/scripts/smoke_api.sh"
else
  echo "API not reachable — skip live smoke (set MEDIAOS_URL)"
fi
