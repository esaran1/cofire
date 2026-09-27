#!/usr/bin/env bash
# Build the static site into app/out for GitHub Pages.
#
# Needs only what the repo carries: the frozen export parquet and the domain
# footprints. No data/ directory, no API, no network beyond npm.
set -euo pipefail
BASE="${BASE_PATH:-/cofire}"
cd "$(dirname "$0")/.."
uv run python -m cofire.ship.bundles
uv run python -m cofire.ship.static_site
cd app
STATIC_EXPORT=1 \
NEXT_PUBLIC_BASE_PATH="$BASE" \
NEXT_PUBLIC_DATA_BASE="$BASE/data" \
NEXT_PUBLIC_BASEMAP=osm \
  npx next build
touch out/.nojekyll
echo "static site: $(du -sh out | cut -f1) in app/out, base path $BASE"
