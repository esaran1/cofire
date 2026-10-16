/**
 * Evidence for REVIEW.md, measured from the rendered files, not asserted.
 *
 *   node scripts/review.mjs
 *
 * Writes out/review.json and out/review/ (contact sheets, one frame per two
 * seconds, for a person to look through):
 * - every output's duration, and the film's bounds;
 * - the longest shot, and any over 6 s other than the magic moment;
 * - loudness of the master and the vertical cut;
 * - captions: most characters on a line, most lines, shortest cue, fastest
 *   reading speed;
 * - black frames and frozen stretches (ffmpeg blackdetect and freezedetect),
 *   which would show a dropped capture or a stuck render;
 * - the static checks (scripts/check.mjs).
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { duration, ff, FILM, loudness, OUT, timeline } from "./lib.mjs";

const TL = timeline();
const R = {};
const file = (n) => join(OUT, n);
const outputs = {
  master: "cofire_master_1920x1080_60fps.mp4", upload: "cofire_upload_1920x1080_30fps.mp4",
  captioned: "cofire_upload_1920x1080_30fps_captions_en.mp4", vertical: "cofire_vertical_1080x1920_30fps_45s.mp4",
  animatic: "cofire_animatic_640x360_15fps_scratch.mp4",
};
R.durations = Object.fromEntries(Object.entries(outputs).filter(([, f]) => existsSync(file(f))).map(([k, f]) => [k, Number(duration(file(f)).toFixed(2))]));
R.film_in_bounds = R.durations.master >= 150 && R.durations.master <= 175;
const shots = TL.shots.map((s) => ({ id: s.id, s: Number((s.end - s.start).toFixed(2)) }));
R.longest_shot = shots.reduce((a, b) => (b.s > a.s ? b : a));
R.over_6s = shots.filter((s) => s.s > 6 && s.id !== "product.tap");
R.loudness = { master: loudness(file(outputs.master)), vertical: loudness(file(outputs.vertical)) };

function srt(name) {
  const blocks = readFileSync(file(name), "utf8").trim().split(/\n\n+/);
  const cues = blocks.map((b) => {
    const [, time, ...lines] = b.split("\n");
    const [a, z] = time.split(" --> ").map((t) => { const [h, m, s] = t.replace(",", ".").split(":").map(Number); return h * 3600 + m * 60 + s; });
    return { d: z - a, lines, chars: lines.join(" ").length };
  });
  return {
    cues: cues.length, max_line_chars: Math.max(...cues.flatMap((c) => c.lines.map((l) => l.length))), max_lines: Math.max(...cues.map((c) => c.lines.length)),
    shortest_cue_s: Number(Math.min(...cues.map((c) => c.d)).toFixed(2)), fastest_chars_per_s: Number(Math.max(...cues.map((c) => c.chars / c.d)).toFixed(1)),
  };
}
R.captions = { en: srt("captions_en.srt"), es: srt("captions_es.srt") };

function detect(name) {
  const err = ff(["-nostats", "-i", file(name), "-vf", "blackdetect=d=0.3:pix_th=0.06,freezedetect=n=0.001:d=2.5", "-an", "-f", "null", "-"]);
  const black = [...err.matchAll(/black_start:([\d.]+) black_end:([\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])]);
  const freezes = [];
  for (const m of err.matchAll(/freeze_start: ([\d.]+)[\s\S]*?freeze_end: ([\d.]+)/g)) freezes.push([Number(m[1]), Number(m[2])]);
  return { black, freezes };
}
R.frames = { upload: detect(outputs.upload), vertical: detect(outputs.vertical) };

try { R.check = execFileSync("node", [join(FILM, "scripts/check.mjs")], { encoding: "utf8" }).trim(); } catch (e) { R.check = `FAILED: ${e.stdout || e.message}`; }

mkdirSync(join(OUT, "review"), { recursive: true });
ff(["-i", file(outputs.upload), "-vf", "fps=1/2,scale=320:180,tile=6x5", join(OUT, "review", "sheet_%d.png")]);
ff(["-i", file(outputs.vertical), "-vf", "fps=1/2,scale=180:320,tile=8x3", join(OUT, "review", "vertical_%d.png")]);
writeFileSync(join(OUT, "review.json"), JSON.stringify(R, null, 1));
console.log(JSON.stringify(R, null, 1));
