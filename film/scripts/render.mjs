/**
 * Render the film, locally, in pieces.
 *
 *   node scripts/render.mjs animatic        # low-resolution animatic with the scratch voice
 *   node scripts/render.mjs master          # 1920x1080 at 60 fps, rendered part by part, then joined
 *   node scripts/render.mjs exports         # from the master: 30 fps upload, captioned upload
 *   node scripts/render.mjs vertical        # 1080x1920 at 30 fps, the first 45 seconds
 *   node scripts/render.mjs prompter        # a silent prompter video for recording the narration
 *   node scripts/render.mjs all             # prepare, check, audio, then all of the above
 *
 * - Parts P1 to P5 are rendered separately (no single render may run over
 *   60 minutes; one that does fails, and is to be split further) and joined
 *   without re-encoding. An idle watchdog cancels a render that makes no
 *   progress for 10 minutes.
 * - Video is rendered silent; the sound is the mix from scripts/audio.mjs
 *   (-14 LUFS), muxed in afterwards.
 * - The map scenes read the basemap from the production build, so
 *   scripts/serve_static.py is started if it is not already running.
 * - Every output's duration is checked (the film may not run over 3:00) and
 *   recorded with its render time, size and sha256 in out/render_report.json.
 */
import { bundle } from "@remotion/bundler";
import { makeCancelSignal, renderMedia, selectComposition } from "@remotion/renderer";
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { createReadStream, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { browserOptions } from "./browser.mjs";
import { duration, ff, FILM, loudness, OUT, REPO, timeline } from "./lib.mjs";
import { webpackOverride } from "./webpack.mjs";

const what = process.argv[2] ?? "animatic";
const TL = timeline();
const MAX_RENDER_MIN = Number(process.env.FILM_MAX_MIN ?? 60);
const IDLE_MIN = 10;
const CONCURRENCY = Number(process.env.FILM_CONCURRENCY ?? 5);
mkdirSync(join(OUT, "parts"), { recursive: true });
const reportPath = join(OUT, "render_report.json");
const report = existsSync(reportPath) ? JSON.parse(readFileSync(reportPath, "utf8")) : { renders: {}, outputs: {} };
const save = () => writeFileSync(reportPath, JSON.stringify(report, null, 1));

function run(cmd, args) {
  const r = spawnSync(cmd, args, { stdio: "inherit", cwd: FILM });
  if (r.status !== 0) throw new Error(`${cmd} ${args.join(" ")} failed`);
}
async function sha256(file) {
  const h = createHash("sha256");
  for await (const c of createReadStream(file)) h.update(c);
  return h.digest("hex");
}
async function record(name, file, extra = {}) {
  report.outputs[name] = { file: file.replace(`${FILM}/`, "film/"), seconds: Number(duration(file).toFixed(3)), bytes: statSync(file).size, sha256: await sha256(file), ...extra };
  save();
  console.log(`${name}: ${report.outputs[name].seconds} s, ${(report.outputs[name].bytes / 1e6).toFixed(1)} MB`);
}

// --- the local site, for the basemap ------------------------------------------
async function up() { try { return (await fetch("http://127.0.0.1:4100/cofire/")).ok; } catch { return false; } }
let server = null;
async function ensureServer() {
  if (await up()) return;
  server = spawn("python3", [join(REPO, "scripts/serve_static.py"), "--port", "4100", "--root", join(REPO, "app/out")], { stdio: "ignore" });
  for (let i = 0; i < 50 && !(await up()); i++) await new Promise((r) => setTimeout(r, 100));
  if (!(await up())) throw new Error("scripts/serve_static.py did not start");
}

let serveUrl = null;
async function getBundle() {
  if (!serveUrl) serveUrl = await bundle({ entryPoint: join(FILM, "src/index.ts"), webpackOverride });
  return serveUrl;
}

async function renderComp(id, output, opts = {}) {
  await ensureServer();
  const url = await getBundle();
  const inputProps = { draft: false, scratch: !existsSync(join(FILM, "audio/voice.wav")), ...(opts.inputProps ?? {}) };
  const comp = await selectComposition({ serveUrl: url, id, inputProps, ...browserOptions() });
  const { cancelSignal, cancel } = makeCancelSignal();
  let last = Date.now(), lastFrames = -1;
  const t0 = Date.now();
  const dog = setInterval(() => {
    const idle = (Date.now() - last) / 60000, total = (Date.now() - t0) / 60000;
    if (idle > IDLE_MIN) { console.error(`${id}: no progress for ${IDLE_MIN} min, cancelling`); cancel(); }
    if (total > MAX_RENDER_MIN) { console.error(`${id}: over ${MAX_RENDER_MIN} min, cancelling; split it further`); cancel(); }
  }, 30000);
  try {
    await renderMedia({
      composition: comp, serveUrl: url, codec: "h264", outputLocation: output, inputProps, muted: true,
      crf: opts.crf ?? 14, pixelFormat: "yuv420p", imageFormat: "jpeg", jpegQuality: opts.jpegQuality ?? 95,
      x264Preset: opts.preset ?? "medium", concurrency: CONCURRENCY, scale: opts.scale ?? 1, cancelSignal,
      onProgress: ({ renderedFrames }) => {
        if (renderedFrames !== lastFrames) { lastFrames = renderedFrames; last = Date.now(); }
        if (renderedFrames % 300 === 0) process.stdout.write(`\r${id}: ${renderedFrames}/${comp.durationInFrames} frames, ${((Date.now() - t0) / 60000).toFixed(1)} min`);
      },
      ...browserOptions(),
    });
  } finally {
    clearInterval(dog);
  }
  const minutes = (Date.now() - t0) / 60000;
  process.stdout.write("\n");
  report.renders[id] = { frames: comp.durationInFrames, fps: comp.fps, size: `${Math.round(comp.width * (opts.scale ?? 1))}x${Math.round(comp.height * (opts.scale ?? 1))}`, minutes: Number(minutes.toFixed(2)), concurrency: CONCURRENCY, at: new Date().toISOString() };
  save();
  if (minutes > MAX_RENDER_MIN) throw new Error(`${id} took ${minutes.toFixed(1)} min, over ${MAX_RENDER_MIN}: split it further`);
  return output;
}

function assertLength(file, expected, label) {
  const d = duration(file);
  if (d > 180) throw new Error(`${label} is ${d.toFixed(2)} s: over 3:00`);
  if (Math.abs(d - expected) > 0.1) throw new Error(`${label} is ${d.toFixed(2)} s, expected ${expected}`);
}

const MIX = join(OUT, "audio/mix_master.wav");
const MIX_V = join(OUT, "audio/mix_vertical.wav");

async function animatic() {
  const v = await renderComp("Animatic", join(OUT, "parts/animatic.mp4"), { scale: 1 / 3, crf: 26, jpegQuality: 80, preset: "veryfast", inputProps: { draft: true, scratch: true } });
  const out = join(OUT, "cofire_animatic_640x360_15fps_scratch.mp4");
  ff(["-i", v, "-i", MIX, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", out]);
  assertLength(out, TL.duration, "animatic");
  await record("animatic", out, { note: "scratch narration (macOS say); draft stand-ins allowed" });
}

async function master() {
  const parts = [];
  // FILM_PARTS=P2,P4 re-renders only those parts and reuses the others' files
  // (for a fix confined to some parts); unset renders every part.
  const only = process.env.FILM_PARTS ? new Set(process.env.FILM_PARTS.split(",")) : null;
  for (const p of TL.parts) {
    const out = join(OUT, "parts", `${p.id}.mp4`);
    if (only && !only.has(p.id) && existsSync(out)) { parts.push(out); continue; }
    await renderComp(p.id, out);
    assertLength(out, p.end - p.start, p.id);
    parts.push(out);
  }
  const list = join(OUT, "parts/list.txt");
  writeFileSync(list, parts.map((p) => `file '${p}'`).join("\n") + "\n");
  const video = join(OUT, "parts/master_video.mp4");
  ff(["-f", "concat", "-safe", "0", "-i", list, "-c", "copy", video]);
  const out = join(OUT, "cofire_master_1920x1080_60fps.mp4");
  ff(["-i", video, "-i", MIX, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", out]);
  assertLength(out, TL.duration, "master");
  await record("master", out, { loudness: loudness(out) });
}

async function exports() {
  const masterFile = join(OUT, "cofire_master_1920x1080_60fps.mp4");
  if (!existsSync(masterFile)) throw new Error("render the master first");
  const t0 = Date.now();
  const upload = join(OUT, "cofire_upload_1920x1080_30fps.mp4");
  ff(["-i", masterFile, "-vf", "fps=30", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", upload]);
  assertLength(upload, TL.duration, "upload");
  await record("upload", upload, { loudness: loudness(upload) });
  const cap = join(OUT, "cofire_upload_1920x1080_30fps_captions_en.mp4");
  // An opaque box behind each caption, so it reads over light app screens as well as dark maps.
  const style = "FontName=Outfit,FontSize=15,PrimaryColour=&H00ECF2F4,BackColour=&H26171817,OutlineColour=&H26171817,BorderStyle=4,Outline=6,Shadow=0,MarginV=24,Alignment=2";
  ff(["-i", upload, "-vf", `subtitles=${join(OUT, "captions_en.srt")}:fontsdir=${join(FILM, "public/fonts")}:force_style='${style}'`, "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", cap]);
  assertLength(cap, TL.duration, "captioned");
  await record("captioned_en", cap);
  for (const l of ["en", "es"]) {
    const f = join(OUT, `captions_${l}.srt`);
    report.outputs[`srt_${l}`] = { file: `film/out/captions_${l}.srt`, bytes: statSync(f).size, sha256: await sha256(f), cues: readFileSync(f, "utf8").split("\n\n").filter(Boolean).length };
    save();
  }
  report.renders.exports = { minutes: Number(((Date.now() - t0) / 60000).toFixed(2)), note: "ffmpeg: 60 to 30 fps by dropping alternate frames; captions burned with libass" };
  save();
}

async function vertical() {
  const v = await renderComp("Vertical", join(OUT, "parts/vertical_video.mp4"), { crf: 16 });
  const out = join(OUT, "cofire_vertical_1080x1920_30fps_45s.mp4");
  ff(["-i", v, "-i", MIX_V, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out]);
  assertLength(out, TL.vertical_duration, "vertical");
  await record("vertical", out, { loudness: loudness(out) });
}

// --- Film v2 (script/v2, scripts/v2/build.mjs) ----------------------------------------
const V2 = join(OUT, "v2");
const V2TL = () => JSON.parse(readFileSync(join(FILM, "script/v2/timeline.json"), "utf8"));
const V2MIX = join(V2, "audio/mix.wav");
// The scratch label stays on until every line is a real recording.
const v2Scratch = () => V2TL().lines.some((l) => l.kind !== "recorded");

async function v2animatic() {
  mkdirSync(join(V2, "parts"), { recursive: true });
  const v = await renderComp("AnimaticV2", join(V2, "parts/animatic.mp4"), { scale: 1 / 3, crf: 26, jpegQuality: 80, preset: "veryfast", inputProps: { scratch: true } });
  const out = join(V2, "cofire_v2_animatic_640x360_15fps_scratch.mp4");
  ff(["-i", v, "-i", V2MIX, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]);
  assertLength(out, V2TL().duration, "v2 animatic");
  await record("v2_animatic", out, { note: "scratch voices (macOS say), placeholder names where team.json is empty" });
}

async function v2master() {
  mkdirSync(join(V2, "parts"), { recursive: true });
  const v = await renderComp("FilmV2", join(V2, "parts/master_video.mp4"), { inputProps: { scratch: v2Scratch() } });
  const out = join(V2, "cofire_v2_master_1920x1080_60fps.mp4");
  ff(["-i", v, "-i", V2MIX, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", out]);
  assertLength(out, V2TL().duration, "v2 master");
  await record("v2_master", out, { loudness: loudness(out) });
}

async function v2exports() {
  const master = join(V2, "cofire_v2_master_1920x1080_60fps.mp4");
  if (!existsSync(master)) throw new Error("render v2master first");
  const D = V2TL().duration;
  const upload = join(V2, "cofire_v2_upload_1920x1080_30fps.mp4");
  ff(["-i", master, "-vf", "fps=30", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", upload]);
  assertLength(upload, D, "v2 upload");
  await record("v2_upload", upload, { loudness: loudness(upload) });
  const cap = join(V2, "cofire_v2_upload_1920x1080_30fps_captions_en.mp4");
  const style = "FontName=Outfit,FontSize=15,PrimaryColour=&H00EEF3F3,BackColour=&H26191A16,OutlineColour=&H26191A16,BorderStyle=4,Outline=6,Shadow=0,MarginV=24,Alignment=2";
  ff(["-i", upload, "-vf", `subtitles=${join(V2, "captions_en.srt")}:fontsdir=${join(FILM, "public/fonts")}:force_style='${style}'`, "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", cap]);
  assertLength(cap, D, "v2 captioned");
  await record("v2_captioned_en", cap);
}

async function v2vertical() {
  mkdirSync(join(V2, "parts"), { recursive: true });
  const v = await renderComp("VerticalV2", join(V2, "parts/vertical_video.mp4"), { crf: 16, inputProps: { scratch: v2Scratch() } });
  const len = duration(v);
  const out = join(V2, "cofire_v2_vertical_1080x1920_30fps.mp4");
  ff(["-i", v, "-i", V2MIX, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", `afade=t=out:st=${(len - 0.6).toFixed(2)}:d=0.6`, "-c:a", "aac", "-b:a", "256k", "-t", len.toFixed(3), "-movflags", "+faststart", out]);
  await record("v2_vertical", out, { loudness: loudness(out) });
}

try {
  if (what === "all") {
    run("node", ["scripts/prepare.mjs"]);
    run("node", ["scripts/check.mjs"]);
    run("node", ["scripts/audio.mjs"]);
    await animatic();
    await master();
    await exports();
    await vertical();
  } else if (what === "animatic") await animatic();
  else if (what === "master") await master();
  else if (what === "exports") await exports();
  else if (what === "vertical") await vertical();
  else if (what === "v2animatic") await v2animatic();
  else if (what === "v2master") await v2master();
  else if (what === "v2exports") await v2exports();
  else if (what === "v2vertical") await v2vertical();
  else if (what === "v2all") { await v2master(); await v2exports(); await v2vertical(); }
  else if (what === "prompter") {
    const out = await renderComp("Prompter", join(OUT, "cofire_prompter_1280x720.mp4"), { crf: 28, jpegQuality: 80, preset: "veryfast", inputProps: { draft: true } });
    await record("prompter", out, { note: "recording aid, silent; not the film" });
  }
  else if (TL.parts.some((p) => p.id === what)) await renderComp(what, join(OUT, "parts", `${what}.mp4`));
  else throw new Error(`unknown target ${what}`);
} finally {
  if (server) server.kill();
}
