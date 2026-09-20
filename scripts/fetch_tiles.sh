#!/usr/bin/env bash
# Fetch a self-hosted PMTiles basemap extract for Colorado.
#
# Why this exists: the OSM Foundation tile servers are donated bandwidth with a
# usage policy that requires a descriptive User-Agent and discourages
# app-embedded and bulk use. Fine for a local demo on one laptop; not fine for a
# deployed build. This produces a keyless, self-hosted alternative so the
# zero-API-key requirement survives deployment.
#
# Usage:  bash scripts/fetch_tiles.sh
# Output: app/public/tiles/colorado.pmtiles
set -euo pipefail

OUT_DIR="app/public/tiles"
OUT="$OUT_DIR/colorado.pmtiles"
# Colorado bbox (buffered), matching COLORADO_BBOX_BUFFERED in config.py
BBOX="-109.56,36.49,-101.54,41.50"

mkdir -p "$OUT_DIR"

if [ -f "$OUT" ]; then
  echo "already present: $OUT ($(du -h "$OUT" | cut -f1))"
  exit 0
fi

echo "Building a Colorado PMTiles extract (keyless, self-hosted)."
echo "Requires the 'pmtiles' CLI: https://github.com/protomaps/go-pmtiles/releases"
if ! command -v pmtiles >/dev/null 2>&1; then
  cat <<'MSG'
pmtiles CLI not found. Install it, then re-run:

  # macOS
  brew install pmtiles
  # or download a release binary from
  # https://github.com/protomaps/go-pmtiles/releases

Until then the app falls back to OSM tiles in local demo mode, which is within
the OSM tile policy for single-machine demo use.
MSG
  exit 1
fi

# Protomaps publishes a daily planet build; extract just Colorado from it.
pmtiles extract \
  "https://build.protomaps.com/20240101.pmtiles" \
  "$OUT" \
  --bbox="$BBOX"

echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
