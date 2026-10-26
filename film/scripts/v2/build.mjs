/**
 * Film v2: voice, timeline, mix, captions, line sheets and the rules check.
 *
 *   node scripts/v2/build.mjs           # scratch voices (macOS say), draft: placeholders allowed
 *   node scripts/v2/build.mjs --final   # fails on any placeholder or missing requirement
 *
 * Voices: if film/audio/vo/<line id>.(wav|m4a) exists it is used (trimmed of
 * leading and trailing silence and normalised); otherwise the line is a
 * scratch read in its speaker's macOS voice. ALL lines are the four voices
 * together, or audio/vo/<id>.wav when the team records it.
 *
 * Writes:
 *   script/v2/timeline.json   beats and line times, read by src/v2 (the picture)
 *   public/data/film.json     adds the timer fields (the number P4 reads)
 *   out/v2/audio/             P1 to P4 and ALL tracks, the narration, the mix
 *   out/v2/captions_en.srt, captions_es.srt
 *   LINES/P1.md to P4.md      what each person records, with timing targets
 *   RULES_CHECK.md            each CAC requirement and the time it is met
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { duration, ff, fill, FILM, loudness, OUT, read } from "../lib.mjs";

const FINAL = process.argv.includes("--final");
const RATE = 182; // scratch reading speed, words per minute
const GAP = 0.18; // least silence between two lines
const MIN_S = 60, MAX_S = 178; // CAC: 1:00 to 2:58 (the brief's cap, two seconds under the rule's 3:00)
const V2 = join(OUT, "v2");
const TMP = join(V2, "tmp");
mkdirSync(join(V2, "audio"), { recursive: true });
mkdirSync(TMP, { recursive: true });
mkdirSync(join(FILM, "LINES"), { recursive: true });

const { speakers, lines } = read(join(FILM, "script/v2/lines.json"));
const { beats } = read(join(FILM, "script/v2/beats.json"));
const dataPath = join(FILM, "public/data/film.json");
const data = read(dataPath);
const fields = data.fields;

// ---- number words, for the timer line ------------------------------------------
const ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"];
const TENS = ["", "", "twenty", "thirty", "forty", "fifty"];
const words = (n) => (n < 20 ? ONES[n] : TENS[Math.floor(n / 10)] + (n % 10 ? `-${ONES[n % 10]}` : ""));
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

// ---- one line's audio ---------------------------------------------------------
function sayWav(voice, text, out) {
  const aiff = out.replace(/\.wav$/, ".aiff");
  execFileSync("say", ["-v", voice, "-r", String(RATE), "-o", aiff, text]);
  ff(["-i", aiff, "-ar", "48000", "-ac", "1", out]);
}
function lineAudio(l, text) {
  const out = join(TMP, `${l.id}.wav`);
  for (const ext of ["wav", "m4a"]) {
    const rec = join(FILM, "audio/vo", `${l.id}.${ext}`);
    if (existsSync(rec)) {
      // A real read: trim silence at both ends, then normalise the line.
      ff(["-i", rec, "-af", "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,loudnorm=I=-18:TP=-2", "-ar", "48000", "-ac", "1", out]);
      return { file: out, kind: "recorded" };
    }
  }
  if (l.speaker === "ALL") {
    const parts = ["P1", "P2", "P3", "P4"].map((p) => {
      const f = join(TMP, `${l.id}_${p}.wav`);
      sayWav(speakers[p].voice, text, f);
      return f;
    });
    ff([...parts.flatMap((f) => ["-i", f]), "-filter_complex", `amix=inputs=4:normalize=0,volume=0.55`, "-ar", "48000", "-ac", "1", out]);
  } else {
    sayWav(speakers[l.speaker].voice, text, out);
  }
  return { file: out, kind: "scratch" };
}

// ---- lay out: beats in order, each line at its anchor, cut on the voice -------
// A beat lasts as long as its lines plus a short tail, so the next beat (and
// the next voice) comes in within half a second; `min` is only for the traces.
const AT = 0.12, TAIL = 0.3;
const byBeat = new Map(beats.map((b) => [b.id, []]));
for (const l of lines) {
  if (!byBeat.has(l.beat)) throw new Error(`line ${l.id}: no beat ${l.beat}`);
  byBeat.get(l.beat).push(l);
}
const HALVES = ["", "half a minute", "one minute", "a minute and a half", "two minutes", "two and a half minutes", "three minutes"];
const HALVES_ES = ["", "medio minuto", "un minuto", "un minuto y medio", "dos minutos", "dos minutos y medio", "tres minutos"];
/** Time left, in words, never rounded up: "just under" the next half minute, or "a little over" the last. */
function minutesPhrase(left) {
  const lo = Math.floor(left / 30), hi = lo + 1;
  if (hi * 30 - left <= 15) return { en: `just under ${HALVES[hi]}`, es: `poco menos de ${HALVES_ES[hi]}` };
  if (left - lo * 30 <= 4) return { en: `about ${HALVES[lo]}`, es: `unos ${HALVES_ES[lo]}` };
  return { en: `a little over ${HALVES[lo]}`, es: `un poco más de ${HALVES_ES[lo]}` };
}
const placed = [];
const laid = [];
let t = 0, prevEnd = 0;
const warnings = [];
const timerStart = () => laid.find((x) => x.id === "team1")?.start;
for (const b of beats) {
  const start = t;
  let need = b.min ?? 0;
  for (const l of byBeat.get(b.id)) {
    const when = Math.max(start + (l.at ?? AT), prevEnd + (l.gap ?? GAP));
    if (l.timer || l.timer_words) {
      // The timer shows 3:00 minus film time; a line that reads it says what it shows then.
      const left = Math.max(0, Math.floor(180 - when));
      if (l.timer) {
        fields.timer_left = { en: String(left), source: `film v2 timeline: 3:00 minus film time, at ${when.toFixed(2)} s` };
        fields.timer_spoken = { en: cap(words(left)), source: "as timer_left", es: String(left) };
      } else {
        const ph = minutesPhrase(left);
        fields.timer_minutes = { en: ph.en, es: ph.es, source: `film v2 timeline: ${left} s left on the timer at ${when.toFixed(2)} s, in words, not rounded up` };
      }
    }
    const en = fill(l.en, "en", fields);
    const es = fill(l.es, "es", fields);
    const a = lineAudio(l, en);
    const len = duration(a.file);
    const end = when + len;
    placed.push({ ...l, start: Number(when.toFixed(3)), end: Number(end.toFixed(3)), len: Number(len.toFixed(3)), text_en: en, text_es: es, audio: a.file, kind: a.kind });
    prevEnd = end;
    need = Math.max(need, end - start + (b.tail ?? TAIL));
  }
  const len = need;
  const row = { ...b, start: Number(start.toFixed(3)), end: Number((start + len).toFixed(3)) };
  if (b.v1s) {
    // Short shots from v1, played in order and time-remapped to fill the beat.
    // Shots play at true speed: retiming a 60 fps shot by a fraction repeats or
    // skips frames, which judders on every pan and cursor move. Each window
    // is trimmed to its share of the beat instead, from its start, middle
    // (default) or end. A capture name is a still plate (2.8 s natural).
    const dur = (w) => (typeof w === "string" ? 2.8 : w[1] - w[0]);
    const D = b.v1s.reduce((x, w) => x + dur(w), 0);
    const k = len / D;
    if (k > 1.001) throw new Error(`${b.id}: its shots run ${D.toFixed(2)} s but the beat needs ${len.toFixed(2)} s; add a window or a plate in beats.json`);
    let at = 0;
    row.shots = b.v1s.map((w) => {
      const shown = dur(w) * k;
      let a = 0;
      if (typeof w !== "string") {
        const [p, q, anchor = "mid"] = w;
        a = anchor === "start" ? p : anchor === "end" ? q - shown : p + (q - p - shown) / 2;
      }
      const sh = { ...(typeof w === "string" ? { plate: w } : {}), a: Number(a.toFixed(3)), at: Number(at.toFixed(3)), len: Number(shown.toFixed(3)), rate: 1 };
      at += shown;
      if (shown > 4.0) warnings.push(`${b.id}: a v1 shot runs ${shown.toFixed(2)} s (over 4 s)`);
      return sh;
    });
    delete row.v1s;
  }
  laid.push(row);
  t = start + len;
}
const total = Number(t.toFixed(3));
writeFileSync(dataPath, JSON.stringify(data));

const timeline = {
  note: "Built by scripts/v2/build.mjs from script/v2/lines.json and beats.json. Do not edit by hand.",
  duration: total,
  timer: { start: timerStart(), end: total },
  beats: laid,
  lines: placed.map(({ audio, ...l }) => l),
};
writeFileSync(join(FILM, "script/v2/timeline.json"), JSON.stringify(timeline, null, 1));

// ---- pacing: dead air and shot length ------------------------------------------
// The open is scored (tap, tone, hits) and the turn's silence is the point;
// everywhere else the voice never stops for more than half a second.
const exempt = new Set(["open", "turn", "endcard"]);
const pacing = [];
for (let i = 1; i < placed.length; i++) {
  const gap = placed[i].start - placed[i - 1].end;
  const where = placed[i].beat;
  if (gap > 0.5 + 1e-6 && !(exempt.has(where) || exempt.has(placed[i - 1].beat))) pacing.push(`dead air ${gap.toFixed(2)} s before \`${placed[i].id}\` at ${placed[i].start.toFixed(2)} s`);
}
const held = new Set(["Logo", "Clock", "Glance", "Third", "EndCard"]);
for (const b of laid) if (held.has(b.scene) && !b.plates && b.end - b.start > 4.0 + 1e-6 && b.id !== "endcard") pacing.push(`shot \`${b.id}\` runs ${(b.end - b.start).toFixed(2)} s (over 4 s)`);
const B = (id) => laid.find((x) => x.id === id);
const L = (id) => placed.find((x) => x.id === id);

// ---- audio: one track per speaker, ALL, the narration and the mix ---------------
function track(sel, out) {
  const ls = placed.filter(sel);
  if (!ls.length) { ff(["-f", "lavfi", "-i", `anullsrc=r=48000:cl=mono`, "-t", String(total), out]); return; }
  const inputs = ls.flatMap((l) => ["-i", l.audio]);
  const f = ls.map((l, i) => `[${i}]adelay=${Math.round(l.start * 1000)}:all=1[d${i}]`);
  ff([...inputs, "-filter_complex", `${f.join(";")};${ls.map((_, i) => `[d${i}]`).join("")}amix=inputs=${ls.length}:normalize=0,apad=whole_dur=${total}[o]`, "-map", "[o]", "-t", String(total), "-ar", "48000", "-ac", "1", out]);
}
for (const p of ["P1", "P2", "P3", "P4", "ALL"]) track((l) => l.speaker === p, join(V2, "audio", `${p}.wav`));
const narration = join(V2, "audio", "narration.wav");
track(() => true, narration);

// Sound: synthesised here with ffmpeg (no downloads), plus Kenney CC0 sounds.
const SYN = join(TMP, "syn");
mkdirSync(SYN, { recursive: true });
const gen = (name, expr, d, post = "") => {
  const out = join(SYN, `${name}.wav`);
  ff(["-f", "lavfi", "-i", `aevalsrc=exprs='${expr}':s=48000:d=${d.toFixed(3)}`, ...(post ? ["-af", post] : []), "-ac", "2", "-ar", "48000", out]);
  return out;
};
const open = B("open");
const tap1 = L("tap1"), tap2 = L("tap2"), tap3 = L("tap3");
const dropHit = tap1.start - 0.3; // Trace.tsx: the drop lands 0.3 s before the first line
// The tap: filtered pink noise, close and quiet, gone before the tone peaks.
const runEnd = tap2.start + 1.2;
const tapRun = join(SYN, "tap.wav");
ff(["-f", "lavfi", "-i", `anoisesrc=color=pink:amplitude=0.6:d=${runEnd.toFixed(3)}:r=48000`, "-af", `highpass=f=700,lowpass=f=5200,tremolo=f=6:d=0.25,afade=t=in:d=0.5,afade=t=out:st=${(runEnd - 1.6).toFixed(3)}:d=1.6`, "-ac", "2", tapRun]);
const drip = gen("drip", "sin(2*PI*(650*t+5600*t*t))*exp(-t*26)", 0.4, "aecho=0.8:0.5:70|140:0.3|0.18");
// The rising tone: three partials sweeping up an octave, growing, cut hard on "This year".
const t0 = tap2.start - 0.6, t1 = tap3.start - 0.03, DT = t1 - t0;
const tone = gen("tone", `(0.55*sin(2*PI*(55*t+27.5*t*t/${DT.toFixed(3)}))+0.3*sin(2*PI*(82.5*t+41.25*t*t/${DT.toFixed(3)}))+0.12*sin(2*PI*(220*t+110*t*t/${DT.toFixed(3)})))*pow(t/${DT.toFixed(3)},1.7)`, DT, `lowpass=f=1400,afade=t=out:st=${(DT - 0.012).toFixed(3)}:d=0.012`);
// Low hits: a falling sub thump.
const thump = gen("thump", "sin(2*PI*(62*t-34*t*t))*exp(-t*6.5)", 0.9);
// Music: a soft pad, four chords on a 32-second loop, synthesised here.
const CHORDS = [[73.42, 110, 185, 277.18, 329.63], [61.74, 92.5, 146.83, 220, 329.63], [49, 73.42, 123.47, 185, 220], [55, 82.41, 146.83, 185, 246.94]];
const chordFiles = CHORDS.map((fs, i) => gen(`chord${i}`, fs.map((f, j) => `${(0.16 / (1 + j * 0.35)).toFixed(3)}*(sin(2*PI*${f}*t)+sin(2*PI*${(f * 1.004).toFixed(3)}*t+${j}))*(1+0.18*sin(2*PI*0.21*t+${j}))`).join("+"), 9.4, "lowpass=f=1600,afade=t=in:d=1.4,afade=t=out:st=7.6:d=1.8"));
const loop = join(SYN, "pad_loop.wav");
ff([...chordFiles.flatMap((f) => ["-i", f]), "-filter_complex", `${chordFiles.map((_, i) => `[${i}]adelay=${i * 8000}:all=1[c${i}]`).join(";")};${chordFiles.map((_, i) => `[c${i}]`).join("")}amix=inputs=4:normalize=0,atrim=0:32,aecho=0.8:0.7:180|310:0.25|0.15[o]`, "-map", "[o]", "-ar", "48000", "-ac", "2", loop]);
// The bed comes in on the hard cut to the team, drops out for the turn, holds
// silence a half-beat past the last word, returns, and fades on the end card.
const team1 = B("team1"), turn = B("turn"), endc = B("endcard");
const turnLast = L("turn2");
const back = turn.end; // the turn's tail is the half-beat
const env = `min(1,max(0,(t-${team1.start.toFixed(3)})/0.12))*(1-min(1,max(0,(t-${turn.start.toFixed(3)})/0.1))*(1-min(1,max(0,(t-${back.toFixed(3)})/0.6))))*(1-min(1,max(0,(t-${(total - 1.8).toFixed(3)})/1.7)))`;
const music = join(V2, "audio", "music.wav");
ff(["-stream_loop", "-1", "-i", loop, "-i", narration, "-filter_complex", `[0]atrim=0:${total},asetpts=N/SR/TB,volume=-17dB,volume='${env}':eval=frame[m];[1]aresample=48000,pan=stereo|c0=c0|c1=c0,asplit=2[k][unused];[unused]anullsink;[m][k]sidechaincompress=threshold=0.03:ratio=5:attack=25:release=350:makeup=1[o]`, "-map", "[o]", "-ar", "48000", "-ac", "2", "-t", String(total), music]);

const SFX = join(FILM, "audio/sfx");
const cues = [
  { file: tapRun, t: open.start, gain: -24 },
  { file: drip, t: dropHit - 0.02, gain: -9 },
  { file: tone, t: t0, gain: -9 },
];
for (const id of ["num1", "num2", "num3"]) {
  const l = L(id);
  cues.push({ file: thump, t: Math.max(0, l.start - 0.05), gain: -3 });
  cues.push({ file: join(SFX, "kenney-interface-sounds_drop_003.ogg"), t: Math.max(0, l.start - 0.05), gain: -8, low: true });
}
for (const b of laid.filter((x) => /^slide/.test(x.id))) cues.push({ file: join(SFX, "kenney-interface-sounds_switch_002.ogg"), t: b.start, gain: -18 });
const forward = B("close");
cues.push({ file: drip, t: L("close3").end - 0.15, gain: -12 });
const raw = join(TMP, "mix_raw.wav");
const inputs = ["-i", narration, "-i", music, ...cues.flatMap((c) => ["-i", c.file])];
const parts = [`[0]aresample=48000,pan=stereo|c0=c0|c1=c0,atrim=0:${total}[v]`, `[1]aresample=48000[mu]`];
cues.forEach((c, i) => {
  const pitch = c.low ? `asetrate=48000*0.5,aresample=48000,lowpass=f=400,` : "aresample=48000,";
  parts.push(`[${i + 2}]${pitch}aformat=channel_layouts=stereo,volume=${c.gain}dB,adelay=${Math.round(c.t * 1000)}:all=1[s${i}]`);
});
ff([...inputs, "-filter_complex", `${parts.join(";")};[v][mu]${cues.map((_, i) => `[s${i}]`).join("")}amix=inputs=${cues.length + 2}:normalize=0:duration=first,apad=whole_dur=${total}[out]`, "-map", "[out]", "-t", String(total), "-ar", "48000", "-ac", "2", raw]);
const mix = join(V2, "audio", "mix.wav");
const target = { I: -14, TP: -1.5, LRA: 11 };
const p1 = ff(["-i", raw, "-af", `loudnorm=I=${target.I}:TP=${target.TP}:LRA=${target.LRA}:print_format=json`, "-f", "null", "-"]);
const m = JSON.parse(p1.slice(p1.lastIndexOf("{"), p1.lastIndexOf("}") + 1));
ff(["-i", raw, "-af", `loudnorm=I=${target.I}:TP=${target.TP}:LRA=${target.LRA}:measured_I=${m.input_i}:measured_TP=${m.input_tp}:measured_LRA=${m.input_lra}:measured_thresh=${m.input_thresh}:offset=${m.target_offset}:linear=true`, "-ar", "48000", mix]);
// The turn must be silent apart from the voice: measure the music there.
const turnMusic = ff(["-ss", String(turn.start + 0.15), "-t", String(Math.max(0.2, back - turn.start - 0.2)), "-i", music, "-af", "volumedetect", "-f", "null", "-"]);
const turnMax = Number((/max_volume: (-?[\d.]+|-inf) dB/.exec(turnMusic) ?? [])[1] ?? -999);
if (!(turnMax < -60 || Number.isNaN(turnMax))) pacing.push(`music is not silent during the turn (max ${turnMax} dB)`);
void turnLast; void forward;

// ---- captions: at most 42 characters a line, two lines a cue, a second at least -----
const stamp = (s) => {
  const ms = Math.round(s * 1000), h = Math.floor(ms / 3600000), mi = Math.floor(ms / 60000) % 60, se = Math.floor(ms / 1000) % 60;
  return `${String(h).padStart(2, "0")}:${String(mi).padStart(2, "0")}:${String(se).padStart(2, "0")},${String(ms % 1000).padStart(3, "0")}`;
};
function wrap(text, max = 42) {
  const out = []; let cur = "";
  for (const w of text.split(/\s+/)) {
    if ((cur + " " + w).trim().length > max) { out.push(cur.trim()); cur = w; } else cur += " " + w;
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}
function srt(lang) {
  const cues = [];
  placed.forEach((l, i) => {
    const text = lang === "es" ? l.text_es : l.text_en;
    const rows = wrap(text);
    const chunks = [];
    for (let k = 0; k < rows.length; k += 2) chunks.push(rows.slice(k, k + 2));
    // Spanish runs longer than the English read: it may use the time up to the next line.
    // A cue may run into the pause after its line (Spanish, which runs longer, a
    // little further), never into the next line.
    const next = placed[i + 1]?.start ?? total;
    const end = Math.min(next - 0.05, l.end + (lang === "es" ? 1.2 : 0.6));
    const span = Math.max(end - l.start, chunks.length * 1.0);
    const totalChars = chunks.reduce((a, c) => a + c.join(" ").length, 0);
    let at = l.start;
    for (const c of chunks) {
      const d = Math.max(1.0, span * (c.join(" ").length / totalChars));
      const label = l.speaker === "ALL" ? "" : "";
      cues.push({ a: at, b: Math.min(at + d, end > at + 1.0 ? end : at + d), text: label + c.join("\n") });
      at += d;
    }
  });
  for (let i = 0; i < cues.length - 1; i++) cues[i].b = Math.min(cues[i].b, cues[i + 1].a - 0.04);
  return cues.map((c, i) => `${i + 1}\n${stamp(c.a)} --> ${stamp(c.b)}\n${c.text}\n`).join("\n");
}
writeFileSync(join(V2, "captions_en.srt"), srt("en"));
writeFileSync(join(V2, "captions_es.srt"), srt("es"));

// ---- line sheets ----------------------------------------------------------------
const mmss = (s) => `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, "0")}`;
for (const p of ["P1", "P2", "P3", "P4"]) {
  const mine = placed.filter((l) => l.speaker === p || l.speaker === "ALL");
  const nWords = mine.reduce((a, l) => a + l.text_en.split(/\s+/).length, 0);
  const rows = mine.map((l) => {
    // Room before the next line, whoever says it, or the end of the line's beat.
    const next = Math.min(placed.find((x) => x.start > l.start)?.start ?? total, laid.find((x) => x.id === l.beat).end);
    const slot = Math.max(l.len, next - l.start - GAP);
    return `| \`${l.id}\` | ${mmss(l.start)} | ${l.speaker === "ALL" ? "ALL (together)" : p} | ${l.text_en.replace(/\|/g, "/")} | ${l.text_en.split(/\s+/).length} | ${slot.toFixed(1)} s |`;
  });
  writeFileSync(join(FILM, "LINES", `${p}.md`), `# ${p}: lines to record

${fields[`name_${p.toLowerCase()}`].en} (${fields[`role_${p.toLowerCase()}`].en}). ${mine.length} lines, ${nWords} words.
Generated by \`scripts/v2/build.mjs\`; the times are where each line sits in the current cut.

| File name | Starts at | Who | Line | Words | Fits in |
|---|---|---|---|---|---|
${rows.join("\n")}

## How to record

1. A quiet, soft room (a closet of clothes is ideal). No fans, no open windows.
2. Phone about 15 cm (a hand's width) from your mouth, a little to the side so breath does not hit it.
3. Say each line three times, with a short pause between takes. Natural pace, like explaining to a friend.
4. Keep each line inside its "Fits in" time. If it runs long, speed up a little rather than cutting words.
5. Lines marked ALL: everyone records their own take of it; we layer them.
6. Export WAV (best) or M4A. Name the file with the line's file name, e.g. \`${mine[0]?.id ?? "line"}.wav\`, keeping only your best take, and put it in \`film/audio/vo/\`.
7. Numbers: say them exactly as written. The timer line (\`glance\`) reads whatever the timer shows; the number is set when the final cut is timed.
`);
}

// ---- rules check -----------------------------------------------------------------
const placeholder = (s) => /\[(Name|Role)[^\]]*\]/.test(s);
const linesFor = (rule) => placed.filter((l) => (l.rules ?? []).includes(rule));
const beatsFor = (rule) => laid.filter((b) => (b.rules ?? []).includes(rule));
const names = ["p1", "p2", "p3", "p4"].map((k) => fields[`name_${k}`].en);
const checks = [
  { rule: "Name of every participant (four), spoken", ok: linesFor("participants").length >= 4 && !names.some(placeholder), at: linesFor("participants").map((l) => mmss(l.start)), note: names.some(placeholder) ? "names are placeholders until film/team/team.json is filled in" : "" },
  { rule: "Name of every participant (four), on screen", ok: beatsFor("participants").length >= 5 && !names.some(placeholder), at: beatsFor("participants").map((b) => mmss(b.start)) },
  { rule: "Name of the app, spoken", ok: linesFor("app_name").length > 0, at: linesFor("app_name").map((l) => mmss(l.start)) },
  { rule: "Name of the app, on screen", ok: beatsFor("app_name").length > 0, at: beatsFor("app_name").map((b) => mmss(b.start)) },
  { rule: "Purpose in one sentence, spoken", ok: linesFor("purpose").length === 1, at: linesFor("purpose").map((l) => mmss(l.start)) },
  { rule: "Purpose in one sentence, on screen verbatim", ok: beatsFor("purpose").length === 1 && linesFor("purpose").length === 1, at: beatsFor("purpose").map((b) => mmss(b.start)), note: "the Purpose scene sets the same text the line speaks (both from script/v2/lines.json)" },
  { rule: "Target audience, spoken", ok: linesFor("audience").length > 0, at: linesFor("audience").map((l) => mmss(l.start)) },
  { rule: "Tools and coding languages, spoken", ok: linesFor("tools").length > 0, at: linesFor("tools").map((l) => mmss(l.start)) },
  { rule: "Tools and coding languages, on screen", ok: beatsFor("tools").length > 0, at: beatsFor("tools").map((b) => mmss(b.start)) },
  { rule: "Open-source libraries and AI-assisted development disclosed on screen", ok: beatsFor("ai_disclosure").length > 0, at: beatsFor("ai_disclosure").map((b) => mmss(b.start)) },
  { rule: "Functionality shown with real app captures", ok: beatsFor("functionality").length >= 5 && beatsFor("functionality").every((b) => b.shots), at: [`${mmss(beatsFor("functionality")[0].start)} to ${mmss(beatsFor("functionality").at(-1).end)}`] },
  { rule: `Duration between 1:00 and 2:58`, ok: total >= MIN_S && total <= MAX_S, at: [mmss(total)] },
];
const failed = checks.filter((c) => !c.ok);
if (pacing.length) failed.push({ rule: `pacing: ${pacing.join("; ")}` });
const draftOnly = failed.every((c) => /participant/.test(c.rule)) && failed.length > 0;
writeFileSync(join(FILM, "RULES_CHECK.md"), `# Film v2: CAC demonstration-video requirements

Written by \`scripts/v2/build.mjs\` (${FINAL ? "final" : "draft"} build), from the timeline it lays out. The build fails if any row fails${FINAL ? "" : ", except names still being placeholders in a draft"}.

| Requirement | Pass | Where (film time) | Note |
|---|---|---|---|
${checks.map((c) => `| ${c.rule} | ${c.ok ? "PASS" : "**FAIL**"} | ${c.at.join(", ")} | ${c.note ?? ""} |`).join("\n")}

Duration: ${mmss(total)} (${total.toFixed(1)} s). Voices: ${placed.filter((l) => l.kind === "recorded").length} recorded, ${placed.filter((l) => l.kind === "scratch").length} scratch (macOS say).

## Pacing (the quality brief)

No dead air over 0.5 s outside the scored open, the turn and the end card; no held shot over 4 s outside the two traces and the turn (v1 shots, plates and slide framings are cut at 4 s or less). Music is silent for the turn, back ${(back - turnLast.end).toFixed(2)} s after its last word.

${pacing.length ? pacing.map((x) => `- **${x}**`).join("\n") : "- All pass."}
${warnings.length ? `\n## Timing warnings\n\n${warnings.map((w) => `- ${w}`).join("\n")}\n` : ""}`);

const mixL = loudness(mix);
console.log(`v2: ${mmss(total)} (${total.toFixed(2)} s), ${placed.length} lines (${placed.filter((l) => l.kind === "recorded").length} recorded), mix ${mixL.integrated_lufs} LUFS`);
for (const w of warnings) console.log("WARN", w);
for (const w of pacing) console.log("PACING", w);
for (const c of checks) console.log(`${c.ok ? "PASS" : "FAIL"} ${c.rule}: ${c.at.join(", ")}`);
if (failed.length && (FINAL || !draftOnly)) {
  console.error(`RULES CHECK FAILED: ${failed.map((c) => c.rule).join("; ")}`);
  process.exit(1);
}
