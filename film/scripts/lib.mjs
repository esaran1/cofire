/**
 * Shared by the film's Node scripts: the data, the timeline, the narration,
 * field filling with the same rules as src/trace.ts, and ffmpeg helpers.
 */
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const FILM = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const REPO = resolve(FILM, "..");
export const OUT = join(FILM, "out");
export const AUDIO = join(FILM, "audio");
export const read = (p) => JSON.parse(readFileSync(p, "utf8"));

export const timeline = () => read(join(FILM, "script/timeline.json"));
export const narration = () => read(join(FILM, "script/narration.json"));
export const data = () => read(join(FILM, "public/data/film.json"));
export const manifest = () => read(join(FILM, "public/captures/manifest.json"));

export const DIGITS = /\d+(?:[.,:]\d+)*/g;

/** Fill {field} references; refuse digits typed into the template (as src/trace.ts does). */
export function fill(template, lang, fields) {
  const literal = template.replace(/\{[a-z0-9_]+\}/g, "").match(DIGITS);
  if (literal) throw new Error(`Untraceable: digits "${literal.join(", ")}" typed into "${template}"`);
  return template.replace(/\{([a-z0-9_]+)\}/g, (_, k) => {
    const f = fields[k];
    if (!f) throw new Error(`Untraceable: no field "${k}" in public/data/film.json`);
    return lang === "es" && f.es ? f.es : f.en;
  });
}

export function words(text) {
  return text.split(/\s+/).filter(Boolean).length;
}

/** Film time of every recorded click: shot start + cursor start + the click's offset in the capture's track. */
export function clickTimes(tl = timeline(), m = manifest()) {
  const out = [];
  for (const s of tl.shots) {
    if (!s.cursor) continue;
    const track = m.shots[s.cursor.capture]?.cursor;
    if (!track?.length) throw new Error(`${s.id}: capture ${s.cursor.capture} has no cursor track`);
    for (const p of track.filter((x) => x.click)) {
      out.push({ t: s.start + s.cursor.start + (p.t - track[0].t) / 1000 / s.cursor.speed, shot: s.id });
    }
  }
  return out;
}

export function which(cmd) {
  for (const d of ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]) if (existsSync(join(d, cmd))) return join(d, cmd);
  throw new Error(`${cmd} not found`);
}
export const FFMPEG = () => which("ffmpeg");
export const FFPROBE = () => which("ffprobe");

export function ff(args, opts = {}) {
  const r = spawnSync(FFMPEG(), ["-hide_banner", "-y", ...args], { encoding: "utf8", maxBuffer: 1 << 28, ...opts });
  if (r.status !== 0) throw new Error(`ffmpeg failed: ${args.join(" ")}\n${r.stderr.slice(-3000)}`);
  return r.stderr;
}

export function duration(file) {
  return Number(execFileSync(FFPROBE(), ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file], { encoding: "utf8" }).trim());
}

/** Integrated loudness, true peak and range of a file (EBU R128). */
export function loudness(file) {
  const err = ff(["-nostats", "-i", file, "-filter_complex", "ebur128=peak=true", "-f", "null", "-"]);
  const tail = err.slice(err.lastIndexOf("Summary:"));
  const num = (re) => Number(tail.match(re)?.[1]);
  return { integrated_lufs: num(/I:\s+(-?[\d.]+) LUFS/), true_peak_dbtp: num(/Peak:\s+(-?[\d.]+) dBFS/), lra_lu: num(/LRA:\s+(-?[\d.]+) LU/) };
}
