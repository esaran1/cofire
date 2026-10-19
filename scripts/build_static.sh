#!/usr/bin/env bash
# Build the static site into app/out.
#
# Needs only what the repo carries: the frozen export parquet and the domain
# footprints. No data/ directory, no API, no network beyond npm.
#
# BASE_PATH is the path the site is served under: empty for Vercel, which
# serves it from the domain's root (scripts/vercel_build.sh); /cofire, the
# default, for the film's local captures.
set -euo pipefail
BASE="${BASE_PATH-/cofire}"
cd "$(dirname "$0")/.."
uv run python -m cofire.ship.bundles
uv run python -m cofire.ship.static_site
cd app
STATIC_EXPORT=1 \
NEXT_PUBLIC_BASE_PATH="$BASE" \
NEXT_PUBLIC_DATA_BASE="$BASE/data" \
  npx next build
# The basemap: the self-hosted Colorado extract when public/tiles holds it
# (downloaded from the 'basemap' release), otherwise a plain background.
# OSM's own tile servers are for local development only.
echo "static site: $(du -sh out | cut -f1) in app/out, base path ${BASE:-/}"
