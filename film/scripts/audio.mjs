/**
 * The film's sound and captions, all local.
 *
 *   node scripts/audio.mjs
 *
 * 1. Narration. If film/audio/voice.wav exists, that is the narration (the
 *    student's recording, one file, starting at 0:00). Otherwise a SCRATCH
 *    track is made with macOS's built-in `say`, one clip per line of
 *    script/narration.json, each placed at its line's start time. Every line
 *    must end before the next begins; the script fails if one does not fit.
 * 2. UI sounds (Kenney, CC0; film/audio/sfx): a click at every click the
 *    capture recorded, a toggle for the language switch, and the cues in
 *    timeline.json. Mixed low.
 * 3. Music. If film/audio/music.wav exists (the student's track, from the
 *    YouTube Audio Library), it is used; otherwise a silent placeholder of the
 *    film's length. Either way the ducking automation is applied: the music
 *    dips under every line of narration. The automation is written to
 *    film/audio/ducking.json.
 * 4. The mix is normalized to -14 LUFS integrated (two-pass loudnorm,
 *    true peak -1 dBTP) and measured again (EBU R128).
 * 5. Captions: .srt in English and Spanish from the script text, filled from
 *    data, timed to the lines.
 *
 * Writes out/audio/ and out/captions_en.srt, out/captions_es.srt.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { AUDIO, clickTimes, data, duration, ff, fill, loudness, manifest, narration, OUT, timeline } from "./lib.mjs";

const TL = timeline();
const NAR = narration();
const FIELDS = data().fields;
const D = TL.duration;
const A = join(OUT, "audio");
const TMP = join(A, "tmp");
rmSync(TMP, { recursive: true, force: true });
mkdirSync(TMP, { recursive: true });
const SAY_VOICE = "Samantha";
const SAY_RATE = 168; // words per minute: a little slower than say's default, closer to a person reading
const report = { narration: null, lines: [], mixes: {} };

// --- 1. Narration ------------------------------------------------------------
const lines = NAR.lines.map((l, i) => {
  const next = NAR.lines[i + 1];
  return { ...l, text_en: fill(l.en, "en", FIELDS), text_es: fill(l.es, "es", FIELDS), slotEnd: next ? next.start : D - 1.0 };
});
const voice = join(AUDIO, "voice.wav");
const scratch = !existsSync(voice);
let narrationWav;
if (scratch) {
  const inputs = [], filters = [];
  lines.forEach((l, i) => {
    const aiff = join(TMP, `line_${String(l.id).padStart(2, "0")}.aiff`);
    const wav = aiff.replace(".aiff", ".wav");
    execFileSync("say", ["-v", SAY_VOICE, "-r", String(SAY_RATE), "-o", aiff, l.text_en]);
    ff(["-i", aiff, "-ar", "48000", "-ac", "1", wav]);
    l.dur = duration(wav);
    inputs.push("-i", wav);
    filters.push(`[${i}]adelay=${Math.round(l.start * 1000)}:all=1[n${i}]`);
  });
  const misfit = lines.filter((l) => l.start + l.dur > l.slotEnd - 0.15);
  if (misfit.length) throw new Error(`scratch lines that run into the next: ${misfit.map((l) => `${l.id} (${l.dur.toFixed(2)} s in a ${(l.slotEnd - l.start).toFixed(2)} s slot)`).join(", ")}`);
  narrationWav = join(A, "scratch_narration.wav");
  ff([...inputs, "-filter_complex", `${filters.join(";")};${lines.map((_, i) => `[n${i}]`).join("")}amix=inputs=${lines.length}:normalize=0,apad,atrim=0:${D}[out]`, "-map", "[out]", "-ar", "48000", "-ac", "1", narrationWav]);
  report.narration = { kind: "SCRATCH: macOS say (built in), replace with audio/voice.wav", voice: SAY_VOICE, rate_wpm: SAY_RATE };
} else {
  narrationWav = voice;
  // A person's reading is not timed line by line here; captions and ducking use each line's slot.
  lines.forEach((l) => { l.dur = l.slotEnd - l.start - 0.2; });
  report.narration = { kind: "the student's recording, audio/voice.wav", seconds: duration(voice) };
}
report.lines = lines.map((l) => ({ id: l.id, start: l.start, seconds: Number(l.dur.toFixed(2)), slot: Number((l.slotEnd - l.start).toFixed(2)), words: l.text_en.split(/\s+/).length }));

// --- 2. UI sounds ---------------------------------------------------------------
function sfxCues(vertical) {
  const sx = TL.sfx;
  if (vertical) return sx.vertical.map((c) => ({ ...c }));
  const cues = sx.cues.map((c) => ({ ...c }));
  for (const c of clickTimes()) {
    const toggle = c.shot === "product.es";
    cues.push({ t: c.t, file: (toggle ? sx.toggle_click : sx.click).file, gain: (toggle ? sx.toggle_click : sx.click).gain, why: `click in ${c.shot}` });
  }
  const wk = TL.shots.find((s) => s.id === sx.weekly_ticks.shot);
  // One tick per issue change, at the times the Weekly scene changes issue (src/scenes/Close.tsx).
  const n = (manifest().shots.weekly?.files ?? []).length;
  for (let k = 1; k < n; k++) cues.push({ t: wk.start + 0.3 + ((wk.end - wk.start - 0.8) * k) / n, file: sx.weekly_ticks.file, gain: sx.weekly_ticks.gain, why: "weekly issue changes" });
  return cues.sort((a, b) => a.t - b.t);
}

// --- 3. Music, ducked -----------------------------------------------------------------
const BASE_DB = -12, DUCK_DB = -24, RAMP = 0.35;
function duckSpans(ls) {
  const spans = [];
  for (const l of ls) {
    const a = Math.max(0, l.start - RAMP), b = l.start + l.dur + RAMP;
    if (spans.length && a <= spans[spans.length - 1][1]) spans[spans.length - 1][1] = Math.max(spans[spans.length - 1][1], b);
    else spans.push([a, b]);
  }
  return spans;
}
function volumeExpr(spans, len) {
  const base = 10 ** (BASE_DB / 20), duck = 10 ** (DUCK_DB / 20);
  const terms = spans.map(([a, b]) => `min(max((t-${a.toFixed(3)})/${RAMP},0),1)*min(max((${b.toFixed(3)}-t)/${RAMP},0),1)`).join("+");
  const fade = `min(min(t/2,1),min(max((${len.toFixed(3)}-t)/3,0),1))`;
  return `(${base.toFixed(5)}-${(base - duck).toFixed(5)}*(${terms || "0"}))*${fade}`;
}

function mix(name, len, ls, cues, narr) {
  const music = existsSync(join(AUDIO, "music.wav")) ? join(AUDIO, "music.wav") : null;
  let musicIn = music;
  if (!musicIn) {
    musicIn = join(A, `music_placeholder_${name}.wav`);
    ff(["-f", "lavfi", "-i", `anullsrc=r=48000:cl=stereo`, "-t", String(len), musicIn]);
  }
  const spans = duckSpans(ls);
  writeFileSync(join(name === "master" ? AUDIO : A, name === "master" ? "ducking.json" : `ducking_${name}.json`), JSON.stringify({
    note: "Music gain automation: the music bed sits at BASE_DB and dips to DUCK_DB under every line of narration, with RAMP-second ramps; it fades in over 2 s and out over the last 3 s. scripts/audio.mjs applies it to film/audio/music.wav, or to a silent placeholder of the film's length when that file is absent.",
    base_db: BASE_DB, duck_db: DUCK_DB, ramp_s: RAMP, length_s: len, duck_spans_s: spans.map(([a, b]) => [Number(a.toFixed(3)), Number(b.toFixed(3))]),
  }, null, 1));
  const inputs = ["-i", narr, "-i", musicIn];
  const parts = [`[0]aresample=48000,pan=stereo|c0=c0|c1=c0,atrim=0:${len}[v]`, `[1]aresample=48000,atrim=0:${len},asetnsamples=n=256,volume=eval=frame:volume='${volumeExpr(spans, len)}'[m]`];
  cues.forEach((c, i) => {
    inputs.push("-i", join(AUDIO, "sfx", c.file));
    parts.push(`[${i + 2}]aresample=48000,aformat=channel_layouts=stereo,volume=${c.gain}dB,adelay=${Math.round(c.t * 1000)}:all=1[s${i}]`);
  });
  const all = ["[v]", "[m]", ...cues.map((_, i) => `[s${i}]`)];
  const raw = join(A, `raw_${name}.wav`);
  ff([...inputs, "-filter_complex", `${parts.join(";")};${all.join("")}amix=inputs=${all.length}:normalize=0:duration=first,apad,atrim=0:${len}[out]`, "-map", "[out]", "-ar", "48000", "-ac", "2", raw]);
  // Two-pass loudness normalization to -14 LUFS.
  const target = { I: -14, TP: -1.0, LRA: 11 };
  const p1 = ff(["-i", raw, "-af", `loudnorm=I=${target.I}:TP=${target.TP}:LRA=${target.LRA}:print_format=json`, "-f", "null", "-"]);
  const m = JSON.parse(p1.slice(p1.lastIndexOf("{"), p1.lastIndexOf("}") + 1));
  const outWav = join(A, `mix_${name}.wav`);
  ff(["-i", raw, "-af", `loudnorm=I=${target.I}:TP=${target.TP}:LRA=${target.LRA}:measured_I=${m.input_i}:measured_TP=${m.input_tp}:measured_LRA=${m.input_lra}:measured_thresh=${m.input_thresh}:offset=${m.target_offset}:linear=true:print_format=summary`, "-ar", "48000", outWav]);
  const after = loudness(outWav);
  if (Math.abs(after.integrated_lufs - target.I) > 0.5) throw new Error(`${name}: integrated loudness ${after.integrated_lufs} LUFS, not within 0.5 LU of ${target.I}`);
  if (after.true_peak_dbtp > target.TP + 0.3) throw new Error(`${name}: true peak ${after.true_peak_dbtp} dBTP over ${target.TP}`);
  report.mixes[name] = { seconds: duration(outWav), music: music ? "film/audio/music.wav" : "silent placeholder (ducking applied)", cues: cues.length, before: { integrated_lufs: Number(m.input_i), true_peak_dbtp: Number(m.input_tp) }, after };
  return outWav;
}

const master = mix("master", D, lines, sfxCues(false), narrationWav);
const vlines = lines.filter((l) => l.start < 42.3);
const vnarr = join(A, "narration_vertical.wav");
ff(["-i", narrationWav, "-af", `atrim=0:${TL.vertical_duration},afade=t=out:st=${TL.vertical_duration - 0.6}:d=0.6`, vnarr]);
const vertical = mix("vertical", TL.vertical_duration, vlines, sfxCues(true), vnarr);

// --- 5. Captions -------------------------------------------------------------------------
// A caption holds at most two lines of 42 characters; pieces are kept to 74 so they always wrap.
const MAX = 74;
function chunks(text) {
  // At most two lines of 42 characters per caption; split at sentence ends, then commas, then words.
  const out = [];
  const sentences = text.match(/[^.?!:]+[.?!:]?/g).map((s) => s.trim()).filter(Boolean);
  for (const s of sentences) {
    if (s.length <= MAX) { out.push(s); continue; }
    const parts = s.split(/(?<=,)\s+/);
    let cur = "";
    for (const p of parts) {
      if ((cur + " " + p).trim().length > MAX && cur) { out.push(cur.trim()); cur = p; } else cur = (cur + " " + p).trim();
    }
    if (cur) out.push(cur);
  }
  // Anything still too long for two lines splits at the word nearest its middle.
  for (let i = 0; i < out.length; i++) {
    if (out[i].length <= MAX) continue;
    const w = out[i].split(" ");
    let cut = 1, best = Infinity;
    for (let k = 1; k < w.length; k++) {
      const d = Math.abs(w.slice(0, k).join(" ").length - w.slice(k).join(" ").length);
      if (d < best) { best = d; cut = k; }
    }
    out.splice(i, 1, w.slice(0, cut).join(" "), w.slice(cut).join(" "));
    i--;
  }
  // Merge short neighbours.
  const merged = [];
  for (const c of out) {
    if (merged.length && (merged[merged.length - 1] + " " + c).length <= MAX) merged[merged.length - 1] += " " + c;
    else merged.push(c);
  }
  return merged.map(wrap);
}
function wrap(s) {
  if (s.length <= 42) return s;
  const words = s.split(" ");
  let best = s, bestDiff = Infinity;
  for (let i = 1; i < words.length; i++) {
    const a = words.slice(0, i).join(" "), b = words.slice(i).join(" ");
    if (a.length <= 42 && b.length <= 42 && Math.abs(a.length - b.length) < bestDiff) { best = `${a}\n${b}`; bestDiff = Math.abs(a.length - b.length); }
  }
  if (bestDiff === Infinity) throw new Error(`caption too long to wrap in two lines of 42: "${s}"`);
  return best;
}
const ts = (s) => {
  const ms = Math.round(s * 1000);
  const h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000), sec = Math.floor((ms % 60000) / 1000), r = ms % 1000;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")},${String(r).padStart(3, "0")}`;
};
function srt(lang) {
  let n = 0;
  const blocks = [];
  for (const l of lines) {
    const text = lang === "es" ? l.text_es : l.text_en;
    const cs = chunks(text);
    // Spanish runs longer than the English voice it is timed to, so its cues
    // use the whole slot; English follows the voice.
    const end = lang === "es" ? l.slotEnd - 0.1 : Math.min(l.start + l.dur + 0.3, l.slotEnd - 0.05);
    // Time shared by length, but no cue under one second: a short piece takes
    // its second from the longer pieces of the same line.
    const span = end - l.start;
    let ds = cs.map((c) => (span * c.length) / cs.reduce((a, x) => a + x.length, 0));
    const MIN = Math.min(1.0, span / cs.length);
    const shortN = ds.filter((d) => d < MIN).length;
    if (shortN) {
      const rest = span - shortN * MIN;
      const longSum = ds.filter((d) => d >= MIN).reduce((a, d) => a + d, 0);
      ds = ds.map((d) => (d < MIN ? MIN : (d * rest) / longSum));
    }
    let t = l.start;
    for (const [k, c] of cs.entries()) {
      const d = ds[k];
      blocks.push(`${++n}\n${ts(t)} --> ${ts(t + d - 0.04)}\n${c}\n`);
      t += d;
    }
  }
  return blocks.join("\n");
}
writeFileSync(join(OUT, "captions_en.srt"), srt("en"));
writeFileSync(join(OUT, "captions_es.srt"), srt("es"));

rmSync(TMP, { recursive: true, force: true });
writeFileSync(join(A, "report.json"), JSON.stringify(report, null, 1));
console.log(JSON.stringify({ narration: report.narration.kind, mixes: Object.fromEntries(Object.entries(report.mixes).map(([k, v]) => [k, v.after])), master, vertical }, null, 1));
