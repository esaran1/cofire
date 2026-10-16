/**
 * Capture every app shot the film uses, from the production static build.
 *
 *   node capture/capture.mjs            # all shots
 *   node capture/capture.mjs card brief  # only the named shots
 *
 * Deterministic by construction:
 * - The site is the production static build (app/out, scripts/build_static.sh)
 *   with its self-hosted basemap, served locally by scripts/serve_static.py exactly
 *   as GitHub Pages would serve it. Any request that is not to that local
 *   server is aborted, so nothing reaches the network.
 * - The issue, area, cell, horizon, layer and language are fixed in the URL
 *   (shots.json); the browser clock is installed and fixed, and advanced only
 *   by this script; animations wait on the map's own idle state; reduced
 *   motion is on, so no CSS transition is caught halfway.
 * - Desktop shots are 1920x1080 CSS pixels at device scale factor 2; phone
 *   shots 390x844 at 3; the printed brief a US Letter sheet (816 px wide) at 3. Stills are lossless PNG. Motion clips are lossless
 *   PNG frame sequences at 60 fps, the clock stepped one frame at a time.
 * - Every pointer movement and click is performed for real and logged with
 *   its time, so the film's synthetic cursor follows the recorded path
 *   (manifest.json, `cursor`), and the screen rectangles of the elements the
 *   camera moves to are saved with each shot (`rects`).
 *
 * Writes public/captures/ (gitignored) and public/captures/manifest.json.
 */
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const FILM = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = resolve(FILM, "..");
const OUT = join(FILM, "public", "captures");
const require = createRequire(join(REPO, "app", "package.json"));
const { chromium } = require("@playwright/test"); // the app's Playwright, already installed

const SHOTS = JSON.parse(readFileSync(join(FILM, "capture", "shots.json"), "utf8"));
const PORT = SHOTS.port;
const ORIGIN = `http://127.0.0.1:${PORT}`;
const SITE = `${ORIGIN}/cofire`;
const FPS = 60;
const only = new Set(process.argv.slice(2));
const want = (name) => only.size === 0 || only.has(name);

// --- The local server ------------------------------------------------------
async function up() {
  try { return (await fetch(`${SITE}/`)).ok; } catch { return false; }
}
let server = null;
if (!(await up())) {
  if (!existsSync(join(REPO, "app", "out", "index.html"))) throw new Error("app/out is missing: run scripts/build_static.sh first");
  server = spawn("python3", [join(REPO, "scripts", "serve_static.py"), "--port", String(PORT), "--root", join(REPO, "app", "out")], { stdio: "ignore" });
  for (let i = 0; i < 50 && !(await up()); i++) await new Promise((r) => setTimeout(r, 100));
  if (!(await up())) throw new Error("scripts/serve_static.py did not start");
}

const browser = await chromium.launch({ channel: "chrome" });
const manifest = existsSync(join(OUT, "manifest.json")) ? JSON.parse(readFileSync(join(OUT, "manifest.json"), "utf8")) : { shots: {} };
manifest.issue = SHOTS.issue;
manifest.clock = SHOTS.clock;
manifest.site = "app/out (production static build), served by scripts/serve_static.py";
mkdirSync(OUT, { recursive: true });
const save = () => writeFileSync(join(OUT, "manifest.json"), JSON.stringify(manifest, null, 1));

function url(q) {
  const p = new URLSearchParams({ issue: SHOTS.issue, horizon: SHOTS.horizon, layer: SHOTS.layer, lang: "en", ...q });
  const path = p.get("path") ?? "/";
  p.delete("path");
  return `${SITE}${path}?${p}`;
}

async function newPage(kind) {
  const base = { reducedMotion: "reduce", colorScheme: "light", locale: "en-US", timezoneId: "America/Denver" };
  const ctx = await browser.newContext(
    kind === "phone" ? { ...base, viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true }
    // A US Letter sheet at 96 CSS px per inch, for the printed brief.
    : kind === "paper" ? { ...base, viewport: { width: 816, height: 1056 }, deviceScaleFactor: 3 }
    : { ...base, viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
  // Nothing leaves this machine: only the local server answers.
  await ctx.route("**/*", (route) => (route.request().url().startsWith(ORIGIN) ? route.continue() : route.abort()));
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error" && !/net::ERR_FAILED/.test(m.text())) errors.push(m.text()); });
  let pending = 0;
  page.on("request", () => pending++);
  page.on("requestfinished", () => pending--);
  page.on("requestfailed", () => pending--);
  await page.clock.install({ time: new Date(SHOTS.clock) });
  const t0 = new Date(SHOTS.clock).getTime();
  let now = 0; // ms of page time since the clock was installed
  const tick = async (ms) => { await page.clock.runFor(ms); now += ms; };
  /** Advance page time until the network is quiet, fonts are in and the map (if any) is idle. */
  const settle = async (minMs = 600, maxReal = 20000) => {
    const start = Date.now();
    let quiet = 0;
    while (Date.now() - start < maxReal) {
      await tick(50);
      await page.waitForTimeout(25);
      const ready = await page.evaluate(() => {
        const m = window.__cofireMap;
        // The map loads on its own (next/dynamic): wait while its placeholder is up.
        if (document.querySelector('[data-testid="map-loading"]')) return false;
        const mapOk = !m || (m.loaded() && m.areTilesLoaded() && !m.isMoving());
        return document.fonts.status === "loaded" && mapOk;
      });
      quiet = ready && pending <= 0 ? quiet + 1 : 0;
      if (quiet >= 4 && Date.now() - start > minMs) return;
    }
    throw new Error(`page did not settle: pending=${pending}`);
  };
  const cursor = [];
  /** Move the real pointer along an eased path and click, logging every position with its page time. */
  const moveTo = async (x, y, ms = 700, click = false) => {
    const from = cursor.length ? cursor.at(-1) : { x: x - 220, y: y + 140 };
    const steps = Math.max(2, Math.round((ms / 1000) * FPS));
    for (let i = 1; i <= steps; i++) {
      const u = i / steps;
      const e = u < 0.5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2; // ease in-out cubic
      const px = from.x + (x - from.x) * e, py = from.y + (y - from.y) * e;
      await page.mouse.move(px, py);
      await tick(ms / steps);
      cursor.push({ t: now, x: Number(px.toFixed(1)), y: Number(py.toFixed(1)) });
    }
    if (click) {
      await page.mouse.down();
      await tick(60);
      await page.mouse.up();
      cursor.push({ t: now, x, y, click: true });
    }
  };
  const rect = async (selector) => {
    const r = await page.locator(selector).first().boundingBox();
    if (!r) throw new Error(`no box for ${selector}`);
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  };
  const shoot = async (name, extra = {}) => {
    const file = `${name}.png`;
    // No loading state, error, or debug value may be on screen in a shot.
    const bad = await page.evaluate(() => (document.body.innerText.match(/\b(Loading|Cargando|Error|NaN|undefined)\b/) ?? [])[0] ?? null);
    if (bad) throw new Error(`${name}: "${bad}" is on screen`);
    await page.screenshot({ path: join(OUT, file), fullPage: !!extra.fullPage, animations: "disabled", caret: "hide" });
    if (errors.length) throw new Error(`${name}: page errors: ${errors.join(" | ")}`);
    const vp = page.viewportSize();
    manifest.shots[name] = { file, kind, viewport: vp, scale: kind === "desktop" ? 2 : 3, url: page.url().replace(ORIGIN, ""), at: new Date(t0 + now).toISOString(), ...extra };
    save(); // after every shot, so a failure later keeps what was captured
    console.log(`  ${name}`);
  };
  return { ctx, page, settle, tick, moveTo, rect, shoot, cursor, errors, get now() { return now; } };
}

/** The point on screen of a map coordinate. */
async function project(page, lon, lat) {
  return page.evaluate(([lon, lat]) => {
    const m = window.__cofireMap;
    const r = m.getContainer().getBoundingClientRect();
    const p = m.project([lon, lat]);
    return { x: r.left + p.x, y: r.top + p.y };
  }, [lon, lat]);
}
const camera = (page) => page.evaluate(() => { const m = window.__cofireMap; const c = m.getCenter(); return { center: [c.lng, c.lat], zoom: m.getZoom(), bearing: m.getBearing(), pitch: m.getPitch() }; });
/** Frame i of n of an eased camera move (ease in and out; centre in Web Mercator, zoom linear). */
async function glide(page, from, to, i, n) {
  const u = Math.min(1, i / n);
  const e = u < 0.5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2;
  const merc = ([lon, lat]) => [lon, Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))];
  const unmerc = ([x, y]) => [x, (360 / Math.PI) * Math.atan(Math.exp(y)) - 90];
  const a = merc(from.center), b = merc(to.center);
  const center = unmerc([a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e]);
  const zoom = from.zoom + (to.zoom - from.zoom) * e;
  await page.evaluate(([center, zoom]) => window.__cofireMap.jumpTo({ center, zoom }), [center, zoom]);
  await page.clock.runFor(1000 / 60); // one frame for the map to draw
}
const cardScroller = (page, top) => page.evaluate((top) => {
  let el = document.querySelector('[data-testid="place-card"]');
  while (el && el.scrollHeight <= el.clientHeight + 2) el = el.parentElement;
  if (el) el.scrollTop = top;
}, top);
const scrollIntoCard = (page, selector, offset = 90) => page.evaluate(([sel, offset]) => {
  const t = document.querySelector(sel);
  let el = document.querySelector('[data-testid="place-card"]');
  while (el && el.scrollHeight <= el.clientHeight + 2) el = el.parentElement;
  if (t && el) el.scrollTop += t.getBoundingClientRect().top - el.getBoundingClientRect().top - offset;
}, [selector, offset]);

async function frames(s, name, steps, fn) {
  const dir = join(OUT, name);
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  const cams = [];
  for (let i = 0; i < steps; i++) {
    await fn(i);
    // Hold the frame until every tile at this camera position has arrived.
    for (let k = 0; k < 400; k++) {
      const ok = await s.page.evaluate(() => { const m = window.__cofireMap; return !m || m.areTilesLoaded(); });
      if (ok) break;
      await s.page.waitForTimeout(15);
    }
    await s.page.clock.runFor(0);
    await s.page.screenshot({ path: join(dir, `${String(i).padStart(4, "0")}.png`), animations: "disabled", caret: "hide" });
    cams.push(await camera(s.page));
  }
  return cams;
}

const DENVER_CELL = SHOTS.cell;
const T0 = Date.now();

// --- Desktop: pick an area, fly in, tap a square, read the card. -------------
if (["pick", "flyin", "denver", "card", "card_why", "card_change", "card_ws", "card_es", "noband", "final"].some(want)) {
  const s = await newPage("desktop");
  const { page } = s;
  await page.goto(url({ domain: SHOTS.start_domain }));
  await s.settle(1500);
  const close = page.getByRole("button", { name: /^close$/i });
  if (await close.count()) { await close.first().click(); await s.settle(); }
  const startCam = await camera(page);
  const sw = await s.rect('[data-testid="domain-switcher"]');
  await s.moveTo(sw.x + sw.w * 0.7, sw.y + sw.h / 2, 900, true);
  if (want("pick")) await s.shoot("pick", { rects: { switcher: sw, map: await s.rect('[data-testid="map"]') }, camera: startCam, cursor: [...s.cursor] });
  const cursorBeforePick = s.cursor.length;

  // Choose Denver. The app fits the map to the area at once (reduced motion).
  // The move from the first area's camera to the app's own fit is then set
  // frame by frame (glide): MapLibre animates on the real clock, which a
  // frame-stepped capture cannot follow, so each frame places the camera
  // itself and waits for the map to draw it.
  await page.locator('[data-testid="domain-switcher"]').selectOption("denver");
  await s.settle(1200);
  const close2 = page.getByRole("button", { name: /^close$/i });
  if (await close2.count()) { await close2.first().click(); await s.settle(); }
  const denverCam = await camera(page);
  if (want("flyin")) {
    await page.evaluate((c) => window.__cofireMap.jumpTo(c), startCam);
    await s.settle(400);
    const n = Math.round((SHOTS.flyin_ms / 1000) * FPS) + 6;
    const cams = await frames(s, "flyin", n, (i) => glide(page, startCam, denverCam, i, n - 6));
    manifest.shots.flyin = { dir: "flyin", kind: "desktop", frames: n, fps: FPS, viewport: { width: 1920, height: 1080 }, scale: 2, from: startCam, to: denverCam, cameras: cams.filter((_, i) => i % 6 === 0) };
    save();
    console.log(`  flyin (${n} frames)`);
    await s.settle();
  }
  if (want("denver")) await s.shoot("denver", { camera: denverCam, rects: { map: await s.rect('[data-testid="map"]'), card: await s.rect("aside") } });

  // Tap the square.
  const c = SHOTS.cell_lonlat;
  const at = await project(page, c[0], c[1]);
  s.cursor.length = 0;
  s.cursor.push({ t: s.now, x: sw.x + sw.w * 0.7, y: sw.y + sw.h / 2 });
  await s.moveTo(at.x, at.y, 1100, true);
  await s.settle(800);
  const tapPath = [...s.cursor];
  if (want("card")) {
    await s.shoot("card", {
      cursor: tapPath, cell: DENVER_CELL,
      rects: {
        card: await s.rect('[data-testid="place-card"]'), aside: await s.rect("aside"), map: await s.rect('[data-testid="map"]'),
        firstRow: await s.rect('[data-testid="frequency"]'), dryness: await s.rect('[data-testid="dryness-heading"]'),
        cellOnMap: { x: Math.round(at.x - 40), y: Math.round(at.y - 50), w: 80, h: 100 },
      },
    });
  }

  // The first drought row's disclosure: icon array and the weeks behind it.
  if (want("card_why") || want("card_change") || want("card_row")) {
    const firstFreq = page.locator('[data-testid="frequency"]').first();
    await firstFreq.scrollIntoViewIfNeeded();
    await scrollIntoCard(page, '[data-testid="frequency"]', 160);
    await s.settle(300);
    const why = page.locator('[data-testid="frequency"]').first().locator("xpath=ancestor::*[.//button or .//summary][1]").getByText(/^why$/i).first();
    const wb = await why.boundingBox();
    // The same scroll position before the click, so the film can dissolve between the two exactly.
    await s.shoot("card_row", { rects: { aside: await s.rect("aside"), frequency: await s.rect('[data-testid="frequency"]'), why: { x: Math.round(wb.x), y: Math.round(wb.y), w: Math.round(wb.width), h: Math.round(wb.height) } } });
    s.cursor.length = 0;
    s.cursor.push({ t: s.now, x: at.x, y: at.y });
    await s.moveTo(wb.x + wb.width / 2, wb.y + wb.height / 2, 900, true);
    await s.settle(500);
    const whyPath = [...s.cursor];
    if (want("card_why")) {
      await s.shoot("card_why_open", { cursor: whyPath, rects: { aside: await s.rect("aside"), frequency: await s.rect('[data-testid="frequency"]'), icons: await s.rect('[data-testid="icon-array"]') } });
      await scrollIntoCard(page, '[data-testid="weeks-like-this"]', 120);
      await s.settle(300);
      await s.shoot("card_weeks", { rects: { aside: await s.rect("aside"), weeks: await s.rect('[data-testid="weeks-like-this"]'), icons: await s.rect('[data-testid="icon-array"]') } });
    }
    if (want("card_change") && (await page.locator('[data-testid="why-changed"]').count())) {
      await scrollIntoCard(page, '[data-testid="why-changed"]', 300);
      await s.settle(300);
      await s.shoot("card_change", { rects: { aside: await s.rect("aside"), change: await s.rect('[data-testid="why-changed"]') } });
    }
  }
  if (want("card_ws")) {
    await scrollIntoCard(page, '[data-testid="watershed-panel"]', 40);
    await s.settle(300);
    await s.shoot("card_ws", { rects: { aside: await s.rect("aside"), panel: await s.rect('[data-testid="watershed-panel"]') } });
  }
  if (want("noband")) {
    await cardScroller(page, 0);
    await s.settle(200);
    const show = page.locator('[data-testid="place-card"]').getByText(/^show$/i).first();
    await show.scrollIntoViewIfNeeded();
    const sb = await show.boundingBox();
    s.cursor.length = 0;
    s.cursor.push({ t: s.now, x: sb.x - 160, y: sb.y + 120 });
    await s.moveTo(sb.x + sb.width / 2, sb.y + sb.height / 2, 800, true);
    await s.settle(400);
    await s.shoot("noband", { cursor: [...s.cursor], rects: { aside: await s.rect("aside"), reason: await s.rect('[data-testid="erc-reason"]') } });
  }
  if (want("card_es")) {
    await cardScroller(page, 0);
    await s.settle(200);
    await s.shoot("card_en_top", { rects: { aside: await s.rect("aside") } });
    const es = page.getByRole("button", { name: "Español" }).first();
    const eb = await es.boundingBox();
    s.cursor.length = 0;
    s.cursor.push({ t: s.now, x: eb.x - 300, y: eb.y + 260 });
    await s.moveTo(eb.x + eb.width / 2, eb.y + eb.height / 2, 800, true);
    await s.settle(600);
    await cardScroller(page, 0);
    await s.settle(200);
    await s.shoot("card_es", { cursor: [...s.cursor], rects: { aside: await s.rect("aside"), toggle: { x: Math.round(eb.x), y: Math.round(eb.y), w: Math.round(eb.width), h: Math.round(eb.height) } } });
  }
  if (want("final")) {
    await page.goto(url({ domain: "denver", lang: "en" }));
    await s.settle(1500);
    const cl = page.getByRole("button", { name: /^close$/i });
    if (await cl.count()) { await cl.first().click(); await s.settle(); }
    await s.shoot("final", { rects: { map: await s.rect('[data-testid="map"]') }, camera: await camera(page) });
  }
  await s.ctx.close();
}

// --- The weekly refresh: the same area, issue by issue. ------------------------
if (want("weekly")) {
  const s = await newPage("desktop");
  const weeks = SHOTS.weekly_issues;
  manifest.shots.weekly = { kind: "desktop", viewport: { width: 1920, height: 1080 }, scale: 2, issues: weeks, files: [] };
  for (const issue of weeks) {
    await s.page.goto(url({ domain: SHOTS.weekly_domain, issue, layer: SHOTS.weekly_layer }));
    await s.settle(1200);
    const cl = s.page.getByRole("button", { name: /^close$/i });
    if (await cl.count()) { await cl.first().click(); await s.settle(); }
    const file = `weekly_${issue}.png`;
    await s.page.screenshot({ path: join(OUT, file), animations: "disabled", caret: "hide" });
    manifest.shots.weekly.files.push(file);
    manifest.shots.weekly.scrubber = await s.rect('[data-testid="time-scrubber"]');
  }
  save();
  console.log(`  weekly (${weeks.length} issues)`);
  await s.ctx.close();
}

// --- Pages: the brief, the record, the method's correction, the data page. -----
for (const [name, path, opts] of [
  ["brief", "/brief/", { print: true }],
  ["scoreboard", "/scoreboard/", {}],
  ["datadict", "/data/", { optional: true }],
]) {
  if (!want(name)) continue;
  const s = await newPage(opts.print ? "paper" : "desktop");
  if (opts.print) await s.page.emulateMedia({ media: "print", reducedMotion: "reduce" });
  const res = await s.page.goto(url({ path, domain: "denver" }));
  if (!res || res.status() >= 400) {
    if (opts.optional) { console.log(`  ${name}: ${path} not built yet, skipped`); await s.ctx.close(); continue; }
    throw new Error(`${path} returned ${res?.status()}`);
  }
  await s.settle(1200);
  const rects = {};
  for (const id of ["score-seal", "score-table", "score-count", "brief-title", "brief-frequency", "brief-fire", "data-title", "data-latest", "data-endpoint", "data-dictionary"]) {
    if (await s.page.locator(`[data-testid="${id}"]`).count()) rects[id] = await s.rect(`[data-testid="${id}"]`);
  }
  await s.shoot(name, { fullPage: true, rects, height: await s.page.evaluate(() => document.documentElement.scrollHeight) });
  await s.ctx.close();
}

// --- Phone: the same flow at phone size, for the device frame and the vertical cut.
if (["m_pick", "m_flyin", "m_card", "m_card_es"].some(want)) {
  const s = await newPage("phone");
  const { page } = s;
  await page.goto(url({ domain: SHOTS.start_domain }));
  await s.settle(1500);
  const startCam = await camera(page);
  if (want("m_pick")) await s.shoot("m_pick", { camera: startCam });
  await page.locator('[data-testid="domain-switcher"]').selectOption("denver");
  await s.settle(1200);
  const close = page.getByRole("button", { name: /^close$/i });
  if (await close.count()) { await close.first().click(); await s.settle(); }
  const denverCam = await camera(page);
  if (want("m_flyin")) {
    await page.evaluate((c) => window.__cofireMap.jumpTo(c), startCam);
    await s.settle(400);
    const n = Math.round((SHOTS.flyin_ms / 1000) * FPS) + 6;
    await frames(s, "m_flyin", n, (i) => glide(page, startCam, denverCam, i, n - 6));
    manifest.shots.m_flyin = { dir: "m_flyin", kind: "phone", frames: n, fps: FPS, viewport: { width: 390, height: 844 }, scale: 3 };
    save();
    console.log(`  m_flyin (${n} frames)`);
    await s.settle();
  }
  const c = SHOTS.cell_lonlat;
  const at = await project(page, c[0], c[1]);
  await page.touchscreen.tap(at.x, at.y);
  s.cursor.length = 0;
  s.cursor.push({ t: s.now, x: at.x, y: at.y, click: true });
  await s.settle(800);
  if (want("m_card")) {
    await s.shoot("m_map_tapped", { cursor: [...s.cursor] });
    // Down to the odds and their frequency sentence, where the card says the most.
    await scrollIntoCard(page, '[data-testid="frequency"]', 300);
    await s.settle(300);
    await s.shoot("m_card", { rects: { card: await s.rect('[data-testid="place-card"]') } });
  }
  if (want("m_card_es")) {
    await page.goto(url({ domain: "denver", lang: "es", cell: DENVER_CELL }));
    await s.settle(1500);
    await scrollIntoCard(page, '[data-testid="frequency"]', 300);
    await s.settle(300);
    await s.shoot("m_card_es", {});
  }
  await s.ctx.close();
}

manifest.captured_in_s = Math.round((Date.now() - T0) / 1000);
writeFileSync(join(OUT, "manifest.json"), JSON.stringify(manifest, null, 1));
await browser.close();
if (server) server.kill();
console.log(`captures in ${manifest.captured_in_s} s -> ${OUT}`);
