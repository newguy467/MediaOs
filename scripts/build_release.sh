#!/usr/bin/env bash
# Build MediaOS v4.12.0 release artefacts (zip + checksums)
# Safe, non-destructive. Does not push to GitHub — only prepares the release package.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(cat VERSION 2>/dev/null || echo "4.12.0")"
NAME="MediaOs-v${VERSION}"
OUT_DIR="${ROOT}/../release"
mkdir -p "$OUT_DIR"

echo "==> Building MediaOS release ${VERSION}"
echo "    Source: $ROOT"
echo "    Output: $OUT_DIR"

# 1. Ensure Safe AI is applied
if [[ -x scripts/apply_safe_ai.sh ]]; then
  bash scripts/apply_safe_ai.sh
else
  echo "WARN: apply_safe_ai.sh missing — continuing"
fi

# 2. Optional UI rebuild (if node is available and full ui/ present)
if command -v npm >/dev/null 2>&1 && [[ -f package.json ]] && [[ -d ui/src ]]; then
  echo "==> Rebuilding UI (optional)..."
  npm install --no-fund --no-audit 2>/dev/null || true
  npm run build 2>/dev/null || echo "  (UI build skipped / failed — using existing static if any)"
else
  echo "==> Skipping UI rebuild (npm or full sources not present)"
fi

# 3. Create clean release tree
STAGE="${OUT_DIR}/.stage-${VERSION}"
rm -rf "$STAGE"
mkdir -p "$STAGE"

# Copy everything except heavy / generated junk
rsync -a \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '.stage-*' \
  --exclude '*.pyc' \
  --exclude '__pycache__' \
  --exclude '.env' \
  --exclude 'data' \
  --exclude 'release' \
  "$ROOT/" "$STAGE/"

# 4. Stamp version everywhere useful
echo "$VERSION" > "$STAGE/VERSION"
# Light touch on package.json if present
if [[ -f "$STAGE/package.json" ]]; then
  python3 - <<PY || true
import json, pathlib
p = pathlib.Path("$STAGE/package.json")
d = json.loads(p.read_text())
d["version"] = "$VERSION"
p.write_text(json.dumps(d, indent=2) + "\n")
PY
fi

# 5. Zip
ZIP="${OUT_DIR}/${NAME}.zip"
rm -f "$ZIP"
( cd "$STAGE" && zip -r -q "$ZIP" . -x "*.pyc" -x "*__pycache__*" -x "*.git*" )
echo "  Created $ZIP"

# 6. Checksums
( cd "$OUT_DIR" && sha256sum "${NAME}.zip" > "${NAME}.zip.sha256" )
echo "  Checksum: $(cat "${OUT_DIR}/${NAME}.zip.sha256")"

# 7. Size
ls -lh "$ZIP"

# Cleanup stage (keep zip)
rm -rf "$STAGE"


# Embed GitHub release notes + checksum inside the zip (always)
if [[ -f "$OUT_DIR/GITHUB_RELEASE_v${VERSION}.md" ]]; then
  ( cd "$OUT_DIR" && zip -j "${NAME}.zip" "GITHUB_RELEASE_v${VERSION}.md" )
elif [[ -f "$ROOT/docs/SAFE_AI.md" ]]; then
  cp "$ROOT/docs/SAFE_AI.md" "$OUT_DIR/RELEASE_NOTES.md"
  ( cd "$OUT_DIR" && zip -j "${NAME}.zip" RELEASE_NOTES.md )
fi
( cd "$OUT_DIR" && sha256sum "${NAME}.zip" > "${NAME}.zip.sha256" )
# Also put a SHA256SUMS.txt inside the zip for convenience
cp "$OUT_DIR/${NAME}.zip.sha256" "$OUT_DIR/SHA256SUMS.txt"
( cd "$OUT_DIR" && zip -j "${NAME}.zip" SHA256SUMS.txt )
# Final checksum of the complete zip
( cd "$OUT_DIR" && sha256sum "${NAME}.zip" > "${NAME}.zip.sha256" )

echo ""
echo "==> Release package ready:"
echo "    ${ZIP}"
echo "    ${OUT_DIR}/${NAME}.zip.sha256"
echo ""
echo "GitHub release tip:"
echo "  gh release create v${VERSION} ${ZIP} ${OUT_DIR}/${NAME}.zip.sha256 \\"
echo "    --title \"MediaOs v${VERSION}\" \\"
echo "    --notes-file docs/SAFE_AI.md"
