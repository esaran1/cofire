#!/usr/bin/env bash
# Vercel's install and build steps for the static site (see vercel.json).
#
#   bash scripts/vercel_build.sh install   # uv, the locked Python environment, the app's npm packages
#   bash scripts/vercel_build.sh build     # the basemap, then scripts/build_static.sh at the root path
#
# Vercel serves the site from the domain's root, so the base path is empty.
# The basemap is the 'basemap' release asset of this private repository, so
# reading it needs COFIRE_RELEASE_TOKEN in the Vercel project's environment
# variables: a fine-grained GitHub token with read-only Contents access to
# this repository and nothing else. A production build without it fails; a
# preview build draws the map on a plain background and says so in the log.
set -euo pipefail
cd "$(dirname "$0")/.."

UV_VERSION=0.11.17
BASEMAP=app/public/tiles/colorado.pmtiles
BASEMAP_SHA256=b661b095ddda73c62b705e478a31deea66c7f3b745e2411e9361c79b7bb50fba
TOOLS="$PWD/.vercel-tools"
export PATH="$TOOLS:$PATH"
# Install exactly what uv.lock pins; never re-resolve during a deploy.
export UV_FROZEN=1
export NEXT_TELEMETRY_DISABLED=1

sha256() {
  if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1
}

install() {
  if ! command -v uv >/dev/null || [ "$(uv --version | cut -d' ' -f2)" != "$UV_VERSION" ]; then
    curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" \
      | env UV_INSTALL_DIR="$TOOLS" UV_NO_MODIFY_PATH=1 INSTALLER_NO_MODIFY_PATH=1 sh
  fi
  # uv fetches the Python that .python-version names if the image lacks it.
  uv sync
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
  BASE_PATH="" ./scripts/build_static.sh
}

case "${1:-}" in
  install) install ;;
  build) build ;;
  *) echo "usage: $0 install|build" >&2; exit 2 ;;
esac
