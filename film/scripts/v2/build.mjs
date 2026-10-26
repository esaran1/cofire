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

// ---- lay out: beats in order, each line at its anchor, never overlapping -------
const byBeat = new Map(beats.map((b) => [b.id, []]));
for (const l of lines) {
  if (!byBeat.has(l.beat)) throw new Error(`line ${l.id}: no beat ${l.beat}`);
  byBeat.get(l.beat).push(l);
}
const placed = [];
const laid = [];
let t = 0, prevEnd = 0, timerStart = null;
const warnings = [];
for (const b of beats) {
  const start = t;
  if (b.id === "card1") timerStart = start;
  let need = b.min;
  for (const l of byBeat.get(b.id)) {
    let when = Math.max(start + l.at, prevEnd + GAP);
    let template = l.en;
    if (l.timer) {
      // The timer counts real film time down from 3:00, starting at the first intro card.
      const left = Math.max(0, Math.floor(180 - (when - timerStart)));
      fields.timer_left = { en: String(left), source: `film v2 timeline: 3:00 minus film time since the first intro card, at ${when.toFixed(2)} s` };
      fields.timer_spoken = { en: cap(words(left)), source: "as timer_left", es: String(left) };
    }
    const en = fill(template, "en", fields);
    const es = fill(l.es, "es", fields);
    const a = lineAudio(l, en);
    const len = duration(a.file);
    const end = when + len;
    placed.push({ ...l, start: Number(when.toFixed(3)), end: Number(end.toFixed(3)), len: Number(len.toFixed(3)), text_en: en, text_es: es, audio: a.file, kind: a.kind });
    prevEnd = end;
    need = Math.max(need, end - start + 0.45);
  }
  let len = b.min;
  if (need > b.min) {
    if (b.stretch) len = need;
    else {
      len = need;
      const over = need - b.min;
      warnings.push(`${b.id}: the line runs ${over.toFixed(2)} s past the v1 window; it holds its last frame for that long${over > 2 ? " (OVER the 2 s static limit: shorten the line or the beat before it)" : ""}`);
    }
  }
  laid.push({ ...b, start: Number(start.toFixed(3)), end: Number((start + len).toFixed(3)) });
  t = start + len;
}
const total = Number(t.toFixed(3));
writeFileSync(dataPath, JSON.stringify(data));

const timeline = {
  note: "Built by scripts/v2/build.mjs from script/v2/lines.json and beats.json. Do not edit by hand.",
  duration: total,
  timer: { start: timerStart, end: laid.find((b) => b.id === "endcard").end },
  beats: laid,
  lines: placed.map(({ audio, ...l }) => l),
};
writeFileSync(join(FILM, "script/v2/timeline.json"), JSON.stringify(timeline, null, 1));

// ---- audio: one track per speaker, ALL, the narration and the mix ---------------
function track(sel, out) {
  const ls = placed.filter(sel);
  if (!ls.length) { ff(["-f", "lavfi", "-i", `anullsrc=r=48000:cl=mono`, "-t", String(total), out]); return; }
  const inputs = ls.flatMap((l) => ["-i", l.audio]);
  const f = ls.map((l, i) => `[${i}]adelay=${Math.round(l.start * 1000)}:all=1[d${i}]`);
  ff([...inputs, "-filter_complex", `${f.join(";")};${ls.map((_, i) => `[d${i}]`).join("")}amix=inputs=${ls.length}:normalize=0,apad,atrim=0:${total}[o]`, "-map", "[o]", "-ar", "48000", "-ac", "1", out]);
}
for (const p of ["P1", "P2", "P3", "P4", "ALL"]) track((l) => l.speaker === p, join(V2, "audio", `${p}.wav`));
const narration = join(V2, "audio", "narration.wav");
track(() => true, narration);

// Sounds: Kenney CC0 only. The cold open's low hit is Kenney's drop sound pitched down an octave.
const SFX = join(FILM, "audio/sfx");
const cues = [];
for (const id of ["cold1", "cold2", "cold3"]) {
  const l = placed.find((x) => x.id === id);
  cues.push({ file: "kenney-interface-sounds_drop_003.ogg", t: Math.max(0, l.start - 0.12), gain: -4, low: true });
}
for (const b of laid.filter((x) => ["card1", "card2", "card3", "card4", "logo", "slide1", "slide2", "slide3", "slide4"].includes(x.id))) {
  cues.push({ file: "kenney-interface-sounds_switch_002.ogg", t: b.start, gain: -14 });
}
const raw = join(TMP, "mix_raw.wav");
const inputs = ["-i", narration, ...cues.flatMap((c) => ["-i", join(SFX, c.file)])];
const parts = [`[0]aresample=48000,pan=stereo|c0=c0|c1=c0,atrim=0:${total}[v]`];
cues.forEach((c, i) => {
  const pitch = c.low ? `asetrate=48000*0.5,aresample=48000,lowpass=f=400,` : "aresample=48000,";
  parts.push(`[${i + 1}]${pitch}aformat=channel_layouts=stereo,volume=${c.gain}dB,adelay=${Math.round(c.t * 1000)}:all=1[s${i}]`);
});
ff([...inputs, "-filter_complex", `${parts.join(";")};[v]${cues.map((_, i) => `[s${i}]`).join("")}amix=inputs=${cues.length + 1}:normalize=0:duration=first,apad,atrim=0:${total}[out]`, "-map", "[out]", "-ar", "48000", "-ac", "2", raw]);
// Music: a silent placeholder slot (no music is downloaded); the mix is narration first.
const mix = join(V2, "audio", "mix.wav");
const target = { I: -14, TP: -1.5, LRA: 11 };
const p1 = ff(["-i", raw, "-af", `loudnorm=I=${target.I}:TP=${target.TP}:LRA=${target.LRA}:print_format=json`, "-f", "null", "-"]);
const m = JSON.parse(p1.slice(p1.lastIndexOf("{"), p1.lastIndexOf("}") + 1));
ff(["-i", raw, "-af", `loudnorm=I=${target.I}:TP=${target.TP}:LRA=${target.LRA}:measured_I=${m.input_i}:measured_TP=${m.input_tp}:measured_LRA=${m.input_lra}:measured_thresh=${m.input_thresh}:offset=${m.target_offset}:linear=true`, "-ar", "48000", mix]);

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
    const next = placed[i + 1]?.start ?? total;
    const end = lang === "es" ? Math.min(next - 0.05, l.end + 1.2) : l.end;
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
  { rule: "Functionality shown with real app captures", ok: beatsFor("functionality").length >= 5 && beatsFor("functionality").every((b) => b.v1), at: [`${mmss(beatsFor("functionality")[0].start)} to ${mmss(beatsFor("functionality").at(-1).end)}`] },
  { rule: `Duration between 1:00 and 2:58`, ok: total >= MIN_S && total <= MAX_S, at: [mmss(total)] },
];
const failed = checks.filter((c) => !c.ok);
const draftOnly = failed.every((c) => /participant/.test(c.rule)) && failed.length > 0;
writeFileSync(join(FILM, "RULES_CHECK.md"), `# Film v2: CAC demonstration-video requirements

Written by \`scripts/v2/build.mjs\` (${FINAL ? "final" : "draft"} build), from the timeline it lays out. The build fails if any row fails${FINAL ? "" : ", except names still being placeholders in a draft"}.

| Requirement | Pass | Where (film time) | Note |
|---|---|---|---|
${checks.map((c) => `| ${c.rule} | ${c.ok ? "PASS" : "**FAIL**"} | ${c.at.join(", ")} | ${c.note ?? ""} |`).join("\n")}

Duration: ${mmss(total)} (${total.toFixed(1)} s). Voices: ${placed.filter((l) => l.kind === "recorded").length} recorded, ${placed.filter((l) => l.kind === "scratch").length} scratch (macOS say).
${warnings.length ? `\n## Timing warnings\n\n${warnings.map((w) => `- ${w}`).join("\n")}\n` : ""}`);

const mixL = loudness(mix);
console.log(`v2: ${mmss(total)} (${total.toFixed(2)} s), ${placed.length} lines (${placed.filter((l) => l.kind === "recorded").length} recorded), mix ${mixL.integrated_lufs} LUFS`);
for (const w of warnings) console.log("WARN", w);
for (const c of checks) console.log(`${c.ok ? "PASS" : "FAIL"} ${c.rule}: ${c.at.join(", ")}`);
if (failed.length && (FINAL || !draftOnly)) {
  console.error(`RULES CHECK FAILED: ${failed.map((c) => c.rule).join("; ")}`);
  process.exit(1);
}
