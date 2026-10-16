/**
 * The browser for every render: the Chrome for Testing headless shell that
 * Playwright already installed (nothing is downloaded), with software WebGL
 * so renders are CPU only. Shared by the CLI config (remotion.config.ts) and
 * the Node scripts.
 */
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export function headlessShell() {
  if (process.env.REMOTION_BROWSER) return process.env.REMOTION_BROWSER;
  const root = join(homedir(), "Library/Caches/ms-playwright");
  const dirs = existsSync(root) ? readdirSync(root).filter((d) => d.startsWith("chromium_headless_shell-")).sort().reverse() : [];
  for (const d of dirs) {
    const p = join(root, d, "chrome-headless-shell-mac-arm64", "chrome-headless-shell");
    if (existsSync(p)) return p;
  }
  throw new Error("No Chrome headless shell found. Set REMOTION_BROWSER to a Chromium binary; nothing is downloaded automatically.");
}

export function browserOptions() {
  return { browserExecutable: headlessShell(), chromiumOptions: { gl: "swangle" }, timeoutInMilliseconds: 180000 };
}
