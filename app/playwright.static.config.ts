import { defineConfig, devices } from "@playwright/test";

/**
 * Checks against the production static build: the daily smoke run and the
 * accessibility checks (e2e/static/). STATIC_URL is the site's root, with its
 * base path and a trailing slash: the deployed GitHub Pages address once Pages
 * is enabled, otherwise the local build served by scripts/serve_static.py.
 */
const base = process.env.STATIC_URL ?? "http://127.0.0.1:4100/cofire/";

export default defineConfig({
  testDir: "./e2e/static",
  timeout: 90_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never", outputFolder: "playwright-report-static" }]] : "list",
  use: { baseURL: base.endsWith("/") ? base : `${base}/`, channel: "chrome" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: "chrome" } },
  ],
});
