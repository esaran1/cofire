#!/usr/bin/env bash
# The web service's install and build steps on Vercel (see vercel.json).
#
#   bash scripts/vercel_build.sh install   # uv, Python 3.12 with the site extra, the app's npm packages
#   bash scripts/vercel_build.sh build     # the basemap, the forecast bundles, then the Next.js build
#
# Vercel runs these from the service root (app/); the script works from the
# repository's root either way. The site is the Next.js server build: the map
# reads the forecast bundles as static files under /data, and Predict and
# Observe call the api service at /api on the same domain.
#
# The basemap (app/public/tiles/colorado.pmtiles) is committed, so a deploy
# finds it in the checkout, checks its sha256 and needs no token. If it is
# ever missing, the build falls back to the 'basemap' release asset of this
# private repository, which needs COFIRE_RELEASE_TOKEN (a fine-grained GitHub
# token with read-only Contents access to this repository) in the Vercel
# project's environment variables.
set -euo pipefail
cd "$(dirname "$0")/.."

UV_VERSION=0.11.17
BASEMAP=app/public/tiles/colorado.pmtiles
BASEMAP_SHA256=b661b095ddda73c62b705e478a31deea66c7f3b745e2411e9361c79b7bb50fba
TOOLS="$PWD/.vercel-tools"
export PATH="$TOOLS:$PATH"
# Install exactly what uv.lock pins; never re-resolve during a deploy.
export UV_FROZEN=1
# Vercel offers Python 3.12 and later only; its build cannot fetch the 3.11
# that .python-version names for local runs and CI. The site build reads the
# committed export and runs no model, so 3.12 changes nothing it writes.
export UV_PYTHON=3.12
export NEXT_TELEMETRY_DISABLED=1

sha256() {
  if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1
}

install() {
  if ! command -v uv >/dev/null || [ "$(uv --version | cut -d' ' -f2)" != "$UV_VERSION" ]; then
    curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" \
      | env UV_INSTALL_DIR="$TOOLS" UV_NO_MODIFY_PATH=1 INSTALLER_NO_MODIFY_PATH=1 sh
  fi
  # The API's packages plus the site extra (geopandas, pyarrow): not the whole
  # pipeline, whose torch alone brings gigabytes of CUDA libraries on Linux.
  uv sync --extra site
  npm ci --prefix app
}

fetch_basemap() {
  if [ -f "$BASEMAP" ] && [ "$(sha256 "$BASEMAP")" = "$BASEMAP_SHA256" ]; then
    echo "basemap: already present"
    return
  fi
  if [ -z "${COFIRE_RELEASE_TOKEN:-}" ]; then
    if [ "${VERCEL_ENV:-}" = "production" ]; then
      echo "error: COFIRE_RELEASE_TOKEN is not set, so the basemap cannot be read from the private release." >&2
      echo "Set it in the Vercel project's environment variables (README, 'Deploying')." >&2
      exit 1
    fi
    echo "warning: no COFIRE_RELEASE_TOKEN: this preview draws the map on a plain background" >&2
    return
  fi
  local repo="${VERCEL_GIT_REPO_OWNER:-esaran1}/${VERCEL_GIT_REPO_SLUG:-cofire}"
  local api="https://api.github.com/repos/$repo"
  local auth=(-H "Authorization: Bearer $COFIRE_RELEASE_TOKEN" -H "X-GitHub-Api-Version: 2022-11-28")
  local id
  id=$(curl -fsSL "${auth[@]}" "$api/releases/tags/basemap" \
    | uv run python -c 'import json, sys; print(next(a["id"] for a in json.load(sys.stdin)["assets"] if a["name"] == "colorado.pmtiles"))')
  mkdir -p "$(dirname "$BASEMAP")"
  # curl drops the Authorization header on the redirect to GitHub's file storage.
  curl -fsSL "${auth[@]}" -H "Accept: application/octet-stream" -o "$BASEMAP" "$api/releases/assets/$id"
  local got
  got=$(sha256 "$BASEMAP")
  if [ "$got" != "$BASEMAP_SHA256" ]; then
    rm -f "$BASEMAP"
    echo "error: the basemap's sha256 is $got, expected $BASEMAP_SHA256" >&2
    exit 1
  fi
  echo "basemap: downloaded and verified"
}

build() {
  fetch_basemap
  uv run python -m cofire.ship.bundles
  uv run python -m cofire.ship.static_site
  cd app
  NEXT_PUBLIC_DATA_BASE=/data NEXT_PUBLIC_API_URL=/api npx next build
}

case "${1:-}" in
  install) install ;;
  build) build ;;
  *) echo "usage: $0 install|build" >&2; exit 2 ;;
esac
