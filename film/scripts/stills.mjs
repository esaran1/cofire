/**
 * Render stills at given times (seconds) from one bundle, for review.
 *
 *   node scripts/stills.mjs Film 34 37 40.5     # -> out/stills/Film_034.00.png ...
 *
 * Needs scripts/serve_static.py running for the map scenes (render.mjs starts it).
 */
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { browserOptions } from "./browser.mjs";

const FILM = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const [id, ...times] = process.argv.slice(2);
const serveUrl = await bundle({ entryPoint: join(FILM, "src/index.ts"), webpackOverride: (await import("./webpack.mjs")).webpackOverride });
const props = { draft: true, scratch: false };
const comp = await selectComposition({ serveUrl, id, inputProps: props, ...browserOptions() });
mkdirSync(join(FILM, "out/stills"), { recursive: true });
for (const s of times.map(Number)) {
  const frame = Math.min(comp.durationInFrames - 1, Math.round(s * comp.fps));
  const out = join(FILM, "out/stills", `${id}_${s.toFixed(2).padStart(6, "0")}.png`);
  const t0 = Date.now();
  await renderStill({ composition: comp, serveUrl, frame, output: out, inputProps: props, ...browserOptions() });
  console.log(`${out} (${Date.now() - t0} ms)`);
}
