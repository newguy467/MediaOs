#!/usr/bin/env bash
# Bump MediaOs VERSION, optionally stamp package.json/Dockerfile, commit + tag.
# Usage:
#   bash scripts/bump_version.sh patch   # 4.13.0 → 4.13.1
#   bash scripts/bump_version.sh minor   # 4.13.0 → 4.14.0
#   bash scripts/bump_version.sh major   # 4.13.0 → 5.0.0
#   bash scripts/bump_version.sh 4.15.0  # set exact
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CUR=$(tr -d '[:space:]' < VERSION 2>/dev/null || echo "0.0.0")
IFS=. read -r MA MI PA <<< "$CUR"
MA=${MA:-0}; MI=${MI:-0}; PA=${PA:-0}

case "${1:-}" in
  major) MA=$((MA+1)); MI=0; PA=0; NEW="$MA.$MI.$PA" ;;
  minor) MI=$((MI+1)); PA=0; NEW="$MA.$MI.$PA" ;;
  patch) PA=$((PA+1)); NEW="$MA.$MI.$PA" ;;
  *)
    if [[ "${1:-}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      NEW="$1"
    else
      echo "Usage: $0 major|minor|patch|X.Y.Z"
      exit 1
    fi
    ;;
esac

echo "$NEW" > VERSION
echo "VERSION: $CUR → $NEW"

if [[ -f package.json ]]; then
  sed -i.bak "s/\"version\": *\"[^\"]*\"/\"version\": \"$NEW\"/" package.json && rm -f package.json.bak
fi
if [[ -f Dockerfile ]]; then
  sed -i.bak "s/ARG APP_VERSION=.*/ARG APP_VERSION=$NEW/" Dockerfile && rm -f Dockerfile.bak
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add VERSION package.json Dockerfile 2>/dev/null || git add VERSION
  git commit -m "chore: bump version to v$NEW" || echo "(nothing to commit or commit skipped)"
  git tag -a "v$NEW" -m "MediaOs v$NEW" 2>/dev/null || {
    git tag -d "v$NEW" 2>/dev/null || true
    git tag -a "v$NEW" -m "MediaOs v$NEW"
  }
  echo "Tagged v$NEW"
  echo "Push:  git push origin HEAD && git push origin v$NEW"
else
  echo "Not a git repo — VERSION file updated only."
fi
