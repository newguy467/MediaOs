#!/usr/bin/env bash
# Sync Cardigann-compatible YAML definitions from Jackett (and optionally Prowlarr).
# Usage:
#   ./scripts/sync_cardigann_defs.sh [dest_dir]
# Default dest: ./definitions
# Requires: git, rsync (or cp)
set -euo pipefail

DEST="${1:-$(cd "$(dirname "$0")/.." && pwd)/definitions}"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "==> Cloning Jackett definitions (sparse)..."
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/Jackett/Jackett.git "$TMP/jackett" 2>/dev/null || {
  echo "git clone failed; check network"
  exit 1
}
(
  cd "$TMP/jackett"
  git sparse-checkout set src/Jackett.Common/Definitions
)

SRC="$TMP/jackett/src/Jackett.Common/Definitions"
mkdir -p "$DEST"
# Copy only .yml (skip any non-yaml)
count=0
for f in "$SRC"/*.yml; do
  [ -f "$f" ] || continue
  base=$(basename "$f")
  # Prefer not to overwrite local customizations if marked
  if [ -f "$DEST/$base" ] && grep -q "mediaos-local" "$DEST/$base" 2>/dev/null; then
    echo "  skip (local): $base"
    continue
  fi
  cp -f "$f" "$DEST/$base"
  count=$((count+1))
done

echo "==> Synced $count definitions into $DEST"
echo "    Reload in MediaOs: Settings → Indexers → Cardigann → Reload defs"
echo "    (or restart the container)"
