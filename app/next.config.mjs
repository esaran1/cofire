/** @type {import('next').NextConfig} */
// STATIC_EXPORT=1 builds a static site (app/out) for GitHub Pages: no API, the
// forecast bundles served as files under NEXT_PUBLIC_DATA_BASE, the site under
// NEXT_PUBLIC_BASE_PATH. Everything else is the normal server build.
import { existsSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const staticExport = process.env.STATIC_EXPORT === "1";
// Whether a self-hosted tile archive was built (scripts/fetch_tiles.sh). A
// production build without one draws the forecast on a plain background rather
// than requesting tiles that are not there.
const hasTiles = !!process.env.NEXT_PUBLIC_PMTILES_URL || existsSync("public/tiles/colorado.pmtiles");
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig = {
  reactStrictMode: true,
  // The app has its own lockfile beside the repository's; trace from here.
  outputFileTracingRoot: dirname(fileURLToPath(import.meta.url)),
  env: { NEXT_PUBLIC_HAS_TILES: hasTiles ? "1" : "" },
  // Icons are imported by name from the package root. Without this, Next
  // compiles all ~3,000 Phosphor icons for every page in development (about
  // 10,850 modules a page, 5.5 s for the first visit to the homepage); with
  // it, each import is rewritten to the one icon it names.
  experimental: { optimizePackageImports: ["@phosphor-icons/react"] },
  ...(staticExport
    ? { output: "export", basePath, trailingSlash: true, images: { unoptimized: true } }
    : {}),
};
export default nextConfig;
