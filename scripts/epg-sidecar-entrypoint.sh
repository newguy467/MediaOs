#!/usr/bin/env bash
# iptv-org/epg sidecar: Node runs site grabbers → guide.xml → static HTTP server
set -euo pipefail

SITE="${EPG_SITE:-tvtv.us}"
DAYS="${EPG_DAYS:-2}"
CRON_H="${EPG_CRON_HOURS:-6}"
OUT="/epg/public/guide.xml"

mkdir -p /epg/public

if [ ! -f /epg/package.json ]; then
  echo "[epg-sidecar] Cloning iptv-org/epg…"
  apt-get update -qq && apt-get install -y -qq git ca-certificates >/dev/null
  git clone --depth 1 https://github.com/iptv-org/epg.git /epg-src
  cp -a /epg-src/. /epg/
  npm install --omit=dev
fi

grab_once() {
  echo "[epg-sidecar] Grabbing site=${SITE} days=${DAYS}…"
  if npm run grab -- --site="${SITE}" --days="${DAYS}" --output="${OUT}" 2>/tmp/epg-grab.err; then
    echo "[epg-sidecar] Wrote ${OUT}"
  elif npm run grab -- --sites="${SITE}" --days="${DAYS}" -o "${OUT}" 2>>/tmp/epg-grab.err; then
    echo "[epg-sidecar] Wrote ${OUT} (sites form)"
  else
    echo "[epg-sidecar] Grab failed — last errors:"
    cat /tmp/epg-grab.err || true
  fi
}

grab_once
(
  while true; do
    sleep $((CRON_H * 3600))
    grab_once || true
  done
) &

# Serve public/ so MediaOs can GET http://iptv-org-epg:3000/guide.xml
npx --yes serve -l 3000 /epg/public
