/**
 * Re-render one stretch of the v2 master and splice it in, instead of the
 * whole film: node scripts/v2/segment.mjs <first frame> <last frame>
 * Writes out/v2/parts/master_video.mp4 (spliced) and re-muxes the master.
 * The splice re-encodes at the master's settings (x264 CRF 14).
 */
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { renameSync } from "node:fs";
import { join } from "node:path";
import { browserOptions } from "../browser.mjs";
import { duration, ff, FILM, OUT } from "../lib.mjs";
import { webpackOverride } from "../webpack.mjs";

const [a, b] = process.argv.slice(2).map(Number);
const V2 = join(OUT, "v2");
const tl = JSON.parse((await import("node:fs")).readFileSync(join(FILM, "script/v2/timeline.json"), "utf8"));
const scratch = tl.lines.some((l) => l.kind !== "recorded");
const serveUrl = await bundle({ entryPoint: join(FILM, "src/index.ts"), webpackOverride });
const inputProps = { draft: false, scratch };
const comp = await selectComposition({ serveUrl, id: "FilmV2", inputProps, ...browserOptions() });
const seg = join(V2, "parts/segment.mp4");
await renderMedia({ composition: comp, serveUrl, codec: "h264", outputLocation: seg, inputProps, muted: true, crf: 14, pixelFormat: "yuv420p", imageFormat: "jpeg", jpegQuality: 95, frameRange: [a, b], concurrency: 9, ...browserOptions() });
const fps = comp.fps, base = join(V2, "parts/master_video.mp4"), out = join(V2, "parts/master_spliced.mp4");
ff(["-i", base, "-i", seg, "-filter_complex",
  `[0:v]trim=end_frame=${a},setpts=PTS-STARTPTS[p];[1:v]setpts=PTS-STARTPTS[s];[0:v]trim=start_frame=${b + 1},setpts=PTS-STARTPTS[q];[p][s][q]concat=n=3:v=1:a=0[v]`,
  "-map", "[v]", "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", String(fps), out]);
const d0 = duration(base), d1 = duration(out);
if (Math.abs(d0 - d1) > 0.05) throw new Error(`splice changed the length: ${d0} -> ${d1}`);
renameSync(out, base);
const master = join(V2, "cofire_v2_master_1920x1080_60fps.mp4");
ff(["-i", base, "-i", join(V2, "audio/mix.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", master]);
console.log(`spliced frames ${a} to ${b}; master ${duration(master).toFixed(3)} s`);
