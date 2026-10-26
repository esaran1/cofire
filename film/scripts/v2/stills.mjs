/**
 * Stills from film v2 at given film times, for review: node scripts/v2/stills.mjs <out dir> <comp> t1 t2 ...
 * (scripts/serve_static.py must be running for the map scenes.)
 */
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { browserOptions } from "../browser.mjs";
import { FILM } from "../lib.mjs";
import { webpackOverride } from "../webpack.mjs";

const [dir, id, ...ts] = process.argv.slice(2);
mkdirSync(dir, { recursive: true });
const serveUrl = await bundle({ entryPoint: join(FILM, "src/index.ts"), webpackOverride });
const inputProps = { scratch: false };
const comp = await selectComposition({ serveUrl, id, inputProps, ...browserOptions() });
for (const t of ts) {
  const frame = Math.min(comp.durationInFrames - 1, Math.round(Number(t) * comp.fps));
  await renderStill({ composition: comp, serveUrl, frame, output: join(dir, `${id}_${String(t).padStart(6, "0")}.jpg`), imageFormat: "jpeg", jpegQuality: 80, inputProps, scale: 0.5, ...browserOptions() });
  console.log("still", t);
}
