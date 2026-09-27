/** @type {import('next').NextConfig} */
// STATIC_EXPORT=1 builds a static site (app/out) for GitHub Pages: no API, the
// forecast bundles served as files under NEXT_PUBLIC_DATA_BASE, the site under
// NEXT_PUBLIC_BASE_PATH. Everything else is the normal server build.
const staticExport = process.env.STATIC_EXPORT === "1";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig = {
  reactStrictMode: true,
  ...(staticExport
    ? { output: "export", basePath, trailingSlash: true, images: { unoptimized: true } }
    : {}),
};
export default nextConfig;
