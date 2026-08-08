#!/usr/bin/env bash
# Live API smoke against a running mediaos instance.
set -euo pipefail
BASE="${MEDIAOS_URL:-http://127.0.0.1:8000}"
AUTH=()
[[ -n "${AUTH_TOKEN:-}" ]] && AUTH+=(-H "Authorization: Bearer $AUTH_TOKEN")
[[ -n "${AUTH_API_KEY:-}" ]] && AUTH+=(-H "X-API-Key: $AUTH_API_KEY")

pass=0; fail=0
check() {
  local name="$1"; shift
  if "$@"; then
    echo "  PASS  $name"; pass=$((pass+1))
  else
    echo "  FAIL  $name"; fail=$((fail+1))
  fi
}

echo "== API smoke against $BASE =="
check "health" curl -sf "${AUTH[@]}" "$BASE/api/health" >/dev/null
check "usenet status" curl -sf "${AUTH[@]}" "$BASE/api/parity/usenet-stream/status" >/dev/null
check "cardigann list" curl -sf "${AUTH[@]}" "$BASE/api/indexers/cardigann" >/dev/null
check "calendar" curl -sf "${AUTH[@]}" "$BASE/api/calendar?days=7" >/dev/null
check "indexers list" curl -sf "${AUTH[@]}" "$BASE/api/indexers" >/dev/null

# Optional: features that need keys may soft-fail
curl -sf "${AUTH[@]}" "$BASE/api/parity/usenet-stream/status" | grep -q seekable && echo "  PASS  usenet seekable flag" || echo "  WARN  usenet seekable flag"

echo "pass=$pass fail=$fail"
[[ "$fail" -eq 0 ]]
