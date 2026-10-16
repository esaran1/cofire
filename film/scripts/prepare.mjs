/**
 * Build the film's data from the project's own files. Nothing here is typed in.
 *
 *   node scripts/prepare.mjs
 *
 * Writes public/data/film.json, the only data the film reads:
 *
 * - `fields`: every number or date that appears in the narration, the captions
 *   or on screen, each with the file and key it came from. The render-time
 *   check (src/trace.ts) fails on any number not produced from this table.
 * - `drought`: the drought category of every cell in every published 2026
 *   issue, from the bundles the app serves (app/out/data/domains). These are
 *   the observed inputs the app displayed each week, not outcomes scored
 *   against a forecast; nothing is computed against 2026 outcomes.
 * - `areas`: the five areas' cells and labels; Denver's two source watersheds
 *   carry their USGS identifiers from artifacts/domains/footprints.json.
 * - `reservoirs`: Dillon and Strontia Springs reservoirs, located from the
 *   named water label points in the app's own basemap archive (OpenStreetMap data
 *   via Protomaps, credited on screen).
 * - `comparisons`: the 115 paired comparisons behind the survivor count
 *   (artifacts/v11/survivors_v11.csv).
 * - `intervals`: the interval audit as the app shows it (facts.json).
 * - `record`: the forecast record (app/lib/forward.json).
 *
 * Needs the production static build (scripts/build_static.sh), which also
 * holds the basemap archive.
 */
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync, openSync, readSync, closeSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { PMTiles } from "pmtiles";
import { VectorTile } from "@mapbox/vector-tile";
import { PbfReader } from "pbf";

const FILM = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = resolve(FILM, "..");
const OUT = join(FILM, "public", "data");
const r = (p) => join(REPO, p);
const json = (p) => JSON.parse(readFileSync(r(p), "utf8"));

const DOMAINS = ["denver", "upper_south_platte", "dillon", "larimer", "pueblo"];
const BUNDLES = r("app/out/data/domains");
const PMTILES = r("app/out/tiles/colorado.pmtiles");
for (const p of [BUNDLES, PMTILES]) {
  if (!existsSync(p)) throw new Error(`${p} is missing: run scripts/build_static.sh first`);
}

const facts = json("app/lib/facts.json");
const seal = json("app/lib/seal.json");
const forward = json("app/lib/forward.json");
const footprints = json("artifacts/domains/footprints.json");
const config = JSON.parse(readFileSync(join(FILM, "config.json"), "utf8"));

/** A field: the text shown, in English and Spanish where they differ, and its source. */
const fields = {};
function field(key, en, source, es) {
  if (en === undefined || en === null || en === "" || Number.isNaN(en)) throw new Error(`field ${key} from ${source} is empty`);
  fields[key] = { en: String(en), ...(es !== undefined ? { es: String(es) } : {}), source };
}
const pct = (x, d = 0) => `${(x * 100).toFixed(d)}%`;

// --- The drought record the app published, week by week. -------------------
const issues = readdirSync(join(BUNDLES, "denver")).filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f)).map((f) => f.slice(0, 10)).sort();
const cells = [];
const cellIndex = new Map();
const areas = {};
const latestBundle = {};
for (const d of DOMAINS) {
  const b = JSON.parse(readFileSync(join(BUNDLES, d, `${issues.at(-1)}.json`), "utf8"));
  latestBundle[d] = b;
  areas[d] = { label: d === "upper_south_platte" ? "Upper South Platte" : d[0].toUpperCase() + d.slice(1), first: cells.length, n: b.cells.length };
  for (const c of b.cells) {
    cellIndex.set(`${d}|${c.id}`, cells.length);
    cells.push([d, Number(c.lat.toFixed(5)), Number(c.lon.toFixed(5))]);
  }
}
const cat = [];
const d2 = [];
for (const issue of issues) {
  const row = new Array(cells.length).fill("x");
  for (const d of DOMAINS) {
    const b = JSON.parse(readFileSync(join(BUNDLES, d, `${issue}.json`), "utf8"));
    for (const c of b.cells) {
      const i = cellIndex.get(`${d}|${c.id}`);
      if (i === undefined) throw new Error(`${d} ${issue}: cell ${c.id} not in the latest issue`);
      // The app's rounding (PlaceCard: Math.round), clamped to D0-D4.
      if (c.usdm !== null && c.usdm !== undefined) row[i] = String(Math.min(4, Math.max(0, Math.round(c.usdm))));
    }
  }
  cat.push(row.join(""));
  d2.push(row.filter((x) => x !== "x" && Number(x) >= 2).length);
}
const peak = d2.indexOf(Math.max(...d2));
const year = issues[0].slice(0, 4);
if (!issues.every((i) => i.startsWith(year))) throw new Error("the drought sequence spans more than one year");
const dateEn = (iso) => new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const dateEs = (iso) => new Date(`${iso}T12:00:00Z`).toLocaleDateString("es-US", { month: "short", day: "numeric", timeZone: "UTC" });
field("year", year, "app/out/data/domains/*/<issue>.json: the year of the published 2026 issues");
field("n_cells", cells.length.toLocaleString("en-US"), "app/out/data/domains/*/<latest issue>.json: number of cells over the five areas");
field("d2_first", d2[0].toLocaleString("en-US"), `bundles ${issues[0]}: cells with usdm rounded to 2 or more`);
field("d2_peak", d2[peak].toLocaleString("en-US"), `bundles ${issues[peak]}: cells with usdm rounded to 2 or more (the year's most)`);
field("peak_date", dateEn(issues[peak]), `bundles: the issue with the most D2-or-worse cells (${issues[peak]})`, dateEs(issues[peak]));
for (let i = 0; i < issues.length; i++) {
  field(`issue_${i}`, dateEn(issues[i]), `bundle issue date ${issues[i]}`, dateEs(issues[i]));
  field(`d2_${i}`, d2[i].toLocaleString("en-US"), `bundles ${issues[i]}: cells in D2 or worse`);
}

// U.S. Drought Monitor category names, as the app labels them (PlaceCard: D${n}).
for (const [n, en, es] of [[1, "moderate", "moderada"], [2, "severe", "severa"], [3, "extreme", "extrema"], [4, "exceptional", "excepcional"]]) {
  field(`cat_${n}`, `D${n}`, "U.S. Drought Monitor category, as the app labels it (components/PlaceCard.tsx)");
  field(`cat_${n}_name`, en, "U.S. Drought Monitor category name (droughtmonitor.unl.edu)", es);
}

// --- Horizons, resolution, splits, the survivors, the seal. -----------------
const horizons = [...new Set(latestBundle.denver.targets.map((t) => Number(t.match(/_h(\d+)$/)[1])))].sort((a, b) => a - b);
field("h_min", horizons[0], "bundle targets: smallest horizon in weeks (the _hN suffix)");
field("h_max", horizons.at(-1), "bundle targets: largest horizon in weeks (the _hN suffix)");
field("cell_km", facts.resolution_m / 1000, "facts.json: resolution_m / 1000");
const [trainStart, trainEnd] = facts.split.train.match(/(\d{4})-\d{2}-\d{2} to (\d{4})-\d{2}-\d{2}/).slice(1);
field("train_start", trainStart, "facts.json: split.train (first year)");
field("train_end", trainEnd, "facts.json: split.train (last year)");
field("holdout", facts.split.holdout, "facts.json: split.holdout");
for (const [key, label] of [["validate", "val"], ["calibrate", "cal"]]) {
  const [a, b] = String(facts.split[key]).match(/(\d{4}) to (\d{4})/).slice(1);
  field(`${label}_start`, a, `facts.json: split.${key} (first year)`);
  field(`${label}_end`, b, `facts.json: split.${key} (last year)`);
}
if (String(seal.holdout_year) !== facts.split.holdout) throw new Error("seal.json and facts.json disagree about the holdout year");
field("n_survivors", facts.multiplicity.n_survivors, "facts.json: multiplicity.n_survivors");
field("n_comparisons", facts.multiplicity.n_comparisons, "facts.json: multiplicity.n_comparisons");
field("n_estimable", facts.multiplicity.n_estimable, "facts.json: multiplicity.n_estimable");
field("looks", facts.hindcast_looks, "facts.json: hindcast_looks");
field("freeze_short", facts.freeze_commit.slice(0, 7), "facts.json: freeze_commit (first 7 characters)");
field("prereg_short", facts.preregistration_sha256.slice(0, 12), "facts.json: preregistration_sha256 (first 12 characters)");
field("config_short", facts.config_hash.slice(0, 12), "facts.json: config_hash (first 12 characters)");
const unseal = new Date(`${seal.unseal_date}T12:00:00Z`);
field("unseal", unseal.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" }), "app/lib/seal.json: unseal_date",
  unseal.toLocaleDateString("es-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" }));

// --- The interval audit, as the app shows it. --------------------------------
const ia = facts.interval_audit;
field("cov_min", pct(facts.look3.pid.coverage_min, 1), "facts.json: look3.pid.coverage_min");
field("cov_max", pct(facts.look3.pid.coverage_max, 1), "facts.json: look3.pid.coverage_max");
const target = Number(String(facts.look3.by_test["3"].threshold).match(/of ([0-9.]+)$/)?.[1]);
if (!(target > 0 && target < 1)) throw new Error("cannot read the nominal coverage from facts.json look3.by_test.3.threshold");
field("coverage_target", pct(target, 0), "facts.json: look3.by_test.3.threshold (the nominal coverage the ranges aimed for)");
field("roll13_pct", Math.round(ia.real_time_roll13_min * 100), "facts.json: interval_audit.real_time_roll13_min x 100, rounded");
field("roll13_tested_min", pct(Math.min(...ia.as_tested.map((x) => x.roll13_min)), 1), "facts.json: interval_audit.as_tested[].roll13_min (lowest)");
const pairs = ia.as_tested.map((a) => {
  const rt = ia.real_time.find((x) => x.domain === a.domain && x.horizon === a.horizon);
  if (!rt) throw new Error(`no real-time row for ${a.domain} h${a.horizon}`);
  return { domain: a.domain, horizon: a.horizon, tested: a.roll13_min, realtime: rt.roll13_min, coverage_tested: a.coverage };
});
pairs.forEach((p, i) => {
  field(`pair_${i}_label`, `${p.domain[0].toUpperCase()}${p.domain.slice(1)} · ${p.horizon} wk`, `facts.json: interval_audit.as_tested[${i}] domain and horizon`, `${p.domain[0].toUpperCase()}${p.domain.slice(1)} · ${p.horizon} sem`);
  field(`pair_${i}_tested`, pct(p.tested, 0), `facts.json: interval_audit.as_tested[${i}].roll13_min`);
  field(`pair_${i}_realtime`, pct(p.realtime, 0), `facts.json: interval_audit.real_time[${i}].roll13_min`);
});

// --- The 115 paired comparisons. ---------------------------------------------
function parseCsv(text) {
  const rows = [];
  let row = [], cur = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"' && text[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') q = false; else cur += ch;
    } else if (ch === '"') q = true;
    else if (ch === ",") { row.push(cur); cur = ""; }
    else if (ch === "\n") { row.push(cur); rows.push(row); row = []; cur = ""; }
    else if (ch !== "\r") cur += ch;
  }
  if (cur || row.length) { row.push(cur); rows.push(row); }
  const [head, ...body] = rows;
  return body.filter((x) => x.length === head.length).map((x) => Object.fromEntries(head.map((h, i) => [h, x[i]])));
}
const surv = parseCsv(readFileSync(r("artifacts/v11/survivors_v11.csv"), "utf8"));
const truthy = (v) => v === "True" || v === "true" || v === "1";
const comparisons = surv.map((s) => ({
  domain: s.domain, target: s.target, horizon: Number(s.horizon), estimable: truthy(s.estimable),
  diff: s.paired_diff === "" ? null : Number(s.paired_diff), lo: s.paired_lo === "" ? null : Number(s.paired_lo),
  hi: s.paired_hi === "" ? null : Number(s.paired_hi), survivor: truthy(s.survivor),
}));
if (comparisons.length !== facts.multiplicity.n_comparisons) throw new Error(`survivors_v11.csv has ${comparisons.length} rows, facts.json says ${facts.multiplicity.n_comparisons}`);
if (comparisons.filter((c) => c.survivor).length !== facts.multiplicity.n_survivors) throw new Error("survivors_v11.csv and facts.json disagree on the survivor count");
if (comparisons.filter((c) => c.estimable).length !== facts.multiplicity.n_estimable) throw new Error("survivors_v11.csv and facts.json disagree on the estimable count");

// --- The forecast record. ------------------------------------------------------
field("n_issues", forward.length, "app/lib/forward.json: number of entries");
const rec = forward.slice(-6).map((e) => ({ issue: e.issue, sha: e.sha256.slice(0, 16) }));
rec.forEach((e, i) => {
  field(`rec_${i}_issue`, e.issue, `app/lib/forward.json: issue of entry ${forward.length - rec.length + i}`);
  field(`rec_${i}_sha`, e.sha, `app/lib/forward.json: sha256 of entry ${forward.length - rec.length + i} (first 16 characters)`);
});

// --- The reservoirs, from the basemap archive. -----------------------------------
class FileSource {
  constructor(path) { this.path = path; this.fd = openSync(path, "r"); this.size = statSync(path).size; }
  getKey() { return this.path; }
  async getBytes(offset, length) {
    const n = Math.max(0, Math.min(length, this.size - offset));
    const buf = Buffer.alloc(n);
    readSync(this.fd, buf, 0, n, offset);
    return { data: buf.buffer.slice(buf.byteOffset, buf.byteOffset + n) };
  }
}
const src = new FileSource(PMTILES);
const archive = new PMTiles(src);
const lon2x = (lon, z) => Math.floor(((lon + 180) / 360) * 2 ** z);
const lat2y = (lat, z) => Math.floor(((1 - Math.log(Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)) / Math.PI) / 2) * 2 ** z);
// Protomaps keeps water polygons unnamed and puts each name on a label point
// inside its polygon (water or pois layer, point features). The reservoir's position
// is that label point, the same place the basemap prints its name.
async function findWater(name, bbox) {
  for (const z of [12, 13]) {
    const found = await findWaterAt(name, bbox, z);
    if (found) return found;
  }
  throw new Error(`${name}: no label point in the basemap archive at zoom 12 or 13`);
}
async function findWaterAt(name, bbox, z) {
  const hits = [];
  for (let x = lon2x(bbox[0], z); x <= lon2x(bbox[2], z); x++) {
    for (let y = lat2y(bbox[3], z); y <= lat2y(bbox[1], z); y++) {
      const t = await archive.getZxy(z, x, y);
      if (!t) continue;
      const vt = new VectorTile(new PbfReader(new Uint8Array(t.data)));
      for (const layer of [vt.layers.water, vt.layers.pois]) {
      if (!layer) continue;
      for (let i = 0; i < layer.length; i++) {
        const f = layer.feature(i);
        if (f.properties.name !== name || f.type !== 1) continue;
        const pt = f.loadGeometry()[0][0];
        if (pt.x < 0 || pt.y < 0 || pt.x > layer.extent || pt.y > layer.extent) continue; // buffer copies of a neighbour's point
        const lon = ((x + pt.x / layer.extent) / 2 ** z) * 360 - 180;
        const n = Math.PI - (2 * Math.PI * (y + pt.y / layer.extent)) / 2 ** z;
        hits.push([lon, (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)))]);
      }
      }
    }
  }
  // A lake can carry the same label point in the water and the pois layers.
  const uniq = hits.filter((h, i) => hits.findIndex((g) => Math.abs(g[0] - h[0]) < 1e-4 && Math.abs(g[1] - h[1]) < 1e-4) === i);
  hits.length = 0;
  hits.push(...uniq);
  if (hits.length === 0) return null;
  if (hits.length !== 1) throw new Error(`${name}: expected one label point at zoom ${z}, found ${hits.length}`);
  return { lon: Number(hits[0][0].toFixed(5)), lat: Number(hits[0][1].toFixed(5)) };
}
const header = await archive.getHeader();
const reservoirs = {
  dillon: { name: "Dillon Reservoir", ...(await findWater("Dillon Reservoir", footprints.dillon.bbox)), source: "OpenStreetMap via the app's Protomaps extract (app/public/tiles/colorado.pmtiles)" },
  strontia: { name: "Strontia Springs Reservoir", ...(await findWater("Strontia Springs Reservoir", footprints.upper_south_platte.bbox)), source: "OpenStreetMap via the app's Protomaps extract" },
};
closeSync(src.fd);
// The tunnel's line is drawn schematically: from Dillon Reservoir's label point
// to the nearest Upper South Platte cell, the watershed it empties into. The
// portal's exact place is not in the project's sources, so the film says
// "route schematic".
{
  const usp = cells.filter((c) => c[0] === "upper_south_platte");
  const d = reservoirs.dillon;
  const near = usp.reduce((a, c) => ((c[2] - d.lon) ** 2 + (c[1] - d.lat) ** 2 < (a[2] - d.lon) ** 2 + (a[1] - d.lat) ** 2 ? c : a));
  reservoirs.tunnel_end = { name: "Upper South Platte (nearest cell to Dillon Reservoir)", lon: near[2], lat: near[1], source: "schematic: the Upper South Platte cell nearest Dillon Reservoir" };
}
for (const d of ["denver", "upper_south_platte", "dillon"]) {
  areas[d].bbox = footprints[d].bbox;
  areas[d].kind = footprints[d].kind;
  areas[d].source = footprints[d].source;
}

// --- The site's address, for the end card. ----------------------------------------
let siteUrl = config.site_url;
let siteSource = "film/config.json: site_url";
if (!siteUrl) {
  const remote = execFileSync("git", ["-C", REPO, "remote", "get-url", "origin"], { encoding: "utf8" }).trim();
  const m = remote.match(/github\.com[:/]([^/]+)\/([^/.]+)/);
  if (!m) throw new Error(`cannot derive the GitHub Pages address from ${remote}; set site_url in film/config.json`);
  siteUrl = `${m[1].toLowerCase()}.github.io/${m[2]}`;
  siteSource = `git remote origin (${m[1]}/${m[2]}), as GitHub Pages serves it; set site_url in film/config.json after the repository moves`;
}
field("site_url", siteUrl, siteSource);

// --- Fonts: the app's own OFL files. -----------------------------------------------
mkdirSync(join(FILM, "public", "fonts"), { recursive: true });
for (const f of readdirSync(r("app/fonts")).filter((x) => x.endsWith(".woff2") || x === "OFL.txt")) copyFileSync(r(`app/fonts/${f}`), join(FILM, "public", "fonts", f));

const data = {
  note: "Generated by film/scripts/prepare.mjs from the project's files. Do not edit; rerun it.",
  inputs: Object.fromEntries(["app/lib/facts.json", "app/lib/seal.json", "app/lib/forward.json", "artifacts/domains/footprints.json", "artifacts/v11/survivors_v11.csv"].map((p) => [p, createHash("sha256").update(readFileSync(r(p))).digest("hex")])),
  basemap: { file: "app/out/tiles/colorado.pmtiles", bounds: [header.minLon, header.minLat, header.maxLon, header.maxLat], maxZoom: header.maxZoom },
  fields,
  drought: { issues, cells, cat, d2, peak },
  areas,
  reservoirs,
  comparisons,
  intervals: { pairs, retraction: ia.retraction.summary },
  record: rec,
};
mkdirSync(OUT, { recursive: true });
writeFileSync(join(OUT, "film.json"), JSON.stringify(data));
console.log(`film.json: ${Object.keys(fields).length} fields, ${issues.length} issues x ${cells.length} cells, ${comparisons.length} comparisons; Dillon at ${reservoirs.dillon.lon}, ${reservoirs.dillon.lat}; Strontia at ${reservoirs.strontia.lon}, ${reservoirs.strontia.lat}`);
