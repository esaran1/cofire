/**
 * Checks the film before any full render. Fails on the first class of problem
 * with every instance listed.
 *
 *   node scripts/check.mjs [--draft]
 *
 * - narration: every line fills from data, no digit typed into a template,
 *   at most about 330 words (fails over 340);
 * - timeline: shots run end to end from 0 with no gap or overlap, sit inside
 *   their parts, last at most 6 s except the magic moment; the film runs
 *   2:30 to 2:55 and never over 3:00; narration lines start inside the film;
 * - scenes: no digit typed as on-screen text in src/ (parsed with the
 *   TypeScript compiler; the runtime guard in src/trace.ts is the full check,
 *   this catches it before a render; the Prompter is a recording aid, not
 *   the film, and is not checked);
 * - captures: every capture the scenes name is in the manifest, and its file
 *   exists; the open-data page is required unless --draft;
 * - assets: every sound in audio/sfx is a Kenney CC0 file, and the licence
 *   texts are in LICENSES/; the music is never committed;
 * - sources: every outside fact the film shows is listed in SOURCES.md;
 * - docs: SCRIPT.md and STORYBOARD.md match the data (scripts/docs.mjs).
 */
import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { data, DIGITS, fill, FILM, manifest, narration, REPO, timeline, words } from "./lib.mjs";

const draft = process.argv.includes("--draft");
const problems = [];
const fail = (msg) => problems.push(msg);
const TL = timeline(), NAR = narration(), F = data().fields;

// narration
let total = 0;
for (const l of NAR.lines) {
  for (const lang of ["en", "es"]) {
    try { const t = fill(l[lang], lang, F); if (lang === "en") total += words(t); } catch (e) { fail(`line ${l.id} (${lang}): ${e.message}`); }
  }
  if (l.start < 0 || l.start >= TL.duration) fail(`line ${l.id} starts outside the film`);
}
if (total > 340) fail(`narration is ${total} words; the limit is about 330`);

// timeline
const shots = [...TL.shots].sort((a, b) => a.start - b.start);
let t = 0;
for (const s of shots) {
  if (Math.abs(s.start - t) > 1e-6) fail(`gap or overlap before ${s.id}: ${t} to ${s.start}`);
  t = s.end;
  const part = TL.parts.find((p) => s.start >= p.start - 1e-6 && s.end <= p.end + 1e-6);
  if (!part) fail(`${s.id} crosses a part boundary`);
  if (s.end - s.start > 6 + 1e-6 && s.id !== "product.tap") fail(`${s.id} lasts ${(s.end - s.start).toFixed(1)} s (over 6 s)`);
}
if (Math.abs(t - TL.duration) > 1e-6) fail(`shots end at ${t}, the film at ${TL.duration}`);
if (TL.duration > 180) fail(`the film is ${TL.duration} s: over 3:00`);
if (TL.duration < 150 || TL.duration > 175) fail(`the film is ${TL.duration} s: outside 2:30 to 2:55`);

// scenes: digits typed as on-screen text, found by parsing the TSX
const ts = (await import("typescript")).default;
function scanTsx(file) {
  const src = readFileSync(file, "utf8");
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const where = (n) => `${file.replace(FILM + "/", "")}:${sf.getLineAndCharacterOfPosition(n.getStart()).line + 1}`;
  const visit = (n) => {
    if (ts.isJsxText(n) && /\d/.test(n.text)) fail(`${where(n)}: digits in on-screen text "${n.text.trim()}"`);
    if (ts.isJsxExpression(n) && n.expression && (ts.isStringLiteral(n.expression) || ts.isNoSubstitutionTemplateLiteral(n.expression)) && /\d/.test(n.expression.text) && ts.isJsxElement(n.parent)) fail(`${where(n)}: digits in on-screen text "${n.expression.text}"`);
    if (ts.isJsxExpression(n) && n.expression && ts.isTemplateExpression(n.expression) && ts.isJsxElement(n.parent)) {
      const lit = [n.expression.head.text, ...n.expression.templateSpans.map((x) => x.literal.text)].join("");
      if (/\d/.test(lit)) fail(`${where(n)}: digits in on-screen text template "${lit}"`);
    }
    if (ts.isJsxAttribute(n) && ["text", "title", "line", "label"].includes(n.name.getText()) && n.initializer && ts.isStringLiteral(n.initializer) && /\d/.test(n.initializer.text)) fail(`${where(n)}: digits in a text prop "${n.initializer.text}"`);
    ts.forEachChild(n, visit);
  };
  visit(sf);
}
for (const dir of ["src", "src/scenes", "src/components"]) {
  for (const f of readdirSync(join(FILM, dir)).filter((x) => x.endsWith(".tsx") && x !== "Prompter.tsx")) scanTsx(join(FILM, dir, f));
}

// captures
const M = manifest().shots;
const named = new Set();
for (const dir of ["src/scenes", "src/components"]) {
  for (const f of readdirSync(join(FILM, dir))) {
    const src = readFileSync(join(FILM, dir, f), "utf8");
    for (const m of src.matchAll(/(?:cap|rect)\("([a-z_]+)"/g)) named.add(m[1]);
    for (const m of src.matchAll(/name="([a-z_]+)"/g)) named.add(m[1]);
    for (const m of src.matchAll(/crossTo=\{\{ name: "([a-z_]+)"/g)) named.add(m[1]);
  }
}
for (const s of TL.shots) if (s.cursor) named.add(s.cursor.capture);
named.delete("datadict");
for (const n of named) {
  const s = M[n];
  if (!s) { fail(`capture "${n}" is not in public/captures/manifest.json`); continue; }
  const files = s.dir ? [join(s.dir, "0000.png")] : s.files ?? [s.file];
  for (const f of files) if (!f || !existsSync(join(FILM, "public/captures", f))) fail(`capture "${n}": ${f} is missing`);
}
if (!draft && !M.datadict) fail("the open-data page is not captured; the film says the data is open");

// assets and licences
for (const f of readdirSync(join(FILM, "audio/sfx"))) if (!/^kenney-(interface-sounds|ui-audio)_[a-z0-9_]+\.ogg$/.test(f)) fail(`audio/sfx/${f} is not a recorded Kenney file`);
for (const f of ["REMOTION.md", "CC0-1.0.txt", "KENNEY_interface-sounds_License.txt", "KENNEY_ui-audio_License.txt"]) if (!existsSync(join(FILM, "LICENSES", f))) fail(`LICENSES/${f} is missing`);
const tracked = execFileSync("git", ["-C", REPO, "ls-files", "film"], { encoding: "utf8" }).split("\n");
for (const f of tracked) if (/film\/audio\/(music|voice)\.wav$/.test(f)) fail(`${f} is committed; the student's music and voice stay out of the repository`);

// sources
const sources = readFileSync(join(FILM, "SOURCES.md"), "utf8");
const links = readFileSync(join(REPO, "app/lib/links.ts"), "utf8");
const used = new Set([...NAR.lines.map((l) => l.source).filter(Boolean)]);
for (const m of readFileSync(join(FILM, "src/scenes/MapAct.tsx"), "utf8").matchAll(/src\("([a-z_]+)"\)/g)) used.add(m[1]);
for (const id of used) {
  const url = links.match(new RegExp(`${id}: \\{[\\s\\S]*?url: "([^"]+)"`))?.[1];
  if (!url) fail(`source ${id} is not in app/lib/links.ts`);
  else if (!sources.includes(url)) fail(`SOURCES.md does not list ${url} (${id})`);
}

// docs
try { execFileSync("node", [join(FILM, "scripts/docs.mjs"), "--check"], { stdio: "pipe" }); } catch (e) { fail(String(e.stderr || e.message).trim().split("\n").pop()); }

if (problems.length) {
  console.error(`film check: ${problems.length} problem(s)\n- ${problems.join("\n- ")}`);
  process.exit(1);
}
console.log(`film check ok: ${TL.shots.length} shots, ${TL.duration} s, ${total} words, ${named.size} captures`);
