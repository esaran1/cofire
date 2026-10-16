/**
 * What lies behind each live probability, from the tables in
 * artifacts/v13/explain (cofire/v13/explain.py), which reproduce the live
 * model exactly (tests/test_v13_explain.py).
 *
 * - frequency: the "in 100 weeks like this one" number, rounded exactly as
 *   the card rounds the percentage, so the two always agree;
 * - weeksLikeThis: the training-year cases behind a drought probability (the
 *   live model is a table of them), or similar weeks for fire (the live model
 *   is a smooth curve, so those counts illustrate rather than reproduce);
 * - decompose: a week-over-week change split into the part from the cell's
 *   own state, the part from the calendar, and, if the forecast method
 *   changed between the two issues, that part too. The parts sum to the total.
 */

export type { Explain } from "./explainSchema";
import type { Explain } from "./explainSchema";


export const CHANGE_THRESHOLD = 0.05; // five percentage points
const ROUNDING = 1e-3; // bundle probabilities carry four decimals
const SEASON_OF: Record<number, string> = { 12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON" };

/** The cell's state at an issue, as the live model conditions on it. */
export type CellState = { issue: string; usdm: number | null; erc_pct: number | null };

export function baseOf(target: string): string {
  return target.replace(/_h\d+$/, "");
}
export function horizonOf(target: string): number {
  return Number(target.match(/_h(\d+)$/)?.[1] ?? 0);
}
export function monthOf(issue: string): number {
  return Number(issue.slice(5, 7));
}
export function categoryOf(usdm: number | null): number {
  // JavaScript's Math.round, the same rounding the export uses for the current category.
  return Math.min(4, Math.max(0, Math.floor((usdm ?? 0) + 0.5)));
}

function eventMask(base: string, c: number): boolean[] {
  return [0, 1, 2, 3, 4].map((k) =>
    base === "d_ge2" ? k >= 2 : base === "d_ge3" ? k >= 3 : base === "d_improve1" ? k <= c - 1 : base === "d_intensify1" ? k >= c + 1 : base === "d_intensify2" ? k >= c + 2 : base === "d_nochange" ? k === c : false,
  );
}

const logit = (p: number) => {
  const q = Math.min(1 - 1e-4, Math.max(1e-4, p));
  return Math.log(q / (1 - q));
};
const sigmoid = (z: number) => 1 / (1 + Math.exp(-z));

function withLiveArm(ex: Explain, target: string, issue: string, p: number): number {
  const e = ex.live.find((l) => l.target === target && issue >= l.applies_from);
  return e ? sigmoid(e.a + e.b * logit(p)) : p;
}

/** The live probability for a target, from the tables; null when the tables cannot say. */
export function liveProbability(ex: Explain, target: string, s: CellState, method: "live" | "base" = "live"): number | null {
  const base = baseOf(target);
  const h = String(horizonOf(target));
  let p: number | null = null;
  if (base.startsWith("d_")) {
    const r = ex.drought[h]?.rows[`${categoryOf(s.usdm)},${monthOf(s.issue)}`];
    if (!r) return null;
    const mask = eventMask(base, categoryOf(s.usdm));
    p = r.row.reduce((a, v, k) => a + (mask[k] ? v : 0), 0);
  } else {
    const f = ex.fire[h]?.[base.replace("f_gt", "")];
    if (!f) return null;
    const x = s.erc_pct ?? f.fill;
    p = sigmoid(f.intercept + f.slope * x);
  }
  return method === "live" ? withLiveArm(ex, target, s.issue, p) : p;
}

/** The "N in 100" number, rounded exactly as the card's percentage. */
export function frequency(p: number): { n: number; lessThanOne: boolean } {
  if (p > 0 && p * 100 < 1) return { n: 0, lessThanOne: true };
  return { n: p <= 0 ? 0 : Number((p * 100).toFixed(0)), lessThanOne: false };
}

export type YearCases = { year: number; n: number; k: number };
export type Cases = { kind: "drought" | "fire"; key: string; season: string; band?: number; years: YearCases[]; total: { n: number; k: number } };

/** The training-year cases behind a probability, most recent first. */
export function weeksLikeThis(ex: Explain, target: string, s: CellState): Cases | null {
  const base = baseOf(target);
  const h = String(horizonOf(target));
  const month = monthOf(s.issue);
  let years: YearCases[] = [];
  let key = "";
  let band: number | undefined;
  if (base.startsWith("d_")) {
    const c = categoryOf(s.usdm);
    const r = ex.drought[h]?.rows[`${c},${month}`];
    if (!r || r.key === "persistence") return null;
    const mask = eventMask(base, c);
    key = r.key;
    years = Object.entries(r.cases).map(([y, counts]) => ({
      year: Number(y),
      n: counts.reduce((a, v) => a + v, 0),
      k: counts.reduce((a, v, i) => a + (mask[i] ? v : 0), 0),
    }));
  } else {
    if (s.erc_pct === null) return null;
    const f = ex.fire[h]?.[base.replace("f_gt", "")];
    band = Math.min(9, Math.max(0, Math.floor(s.erc_pct / 10)));
    const per = f?.cases[SEASON_OF[month]]?.[String(band)];
    if (!per) return null;
    key = "band";
    years = Object.entries(per).map(([y, [n, k]]) => ({ year: Number(y), n, k }));
  }
  years.sort((a, b) => b.year - a.year);
  const total = years.reduce((a, y) => ({ n: a.n + y.n, k: a.k + y.k }), { n: 0, k: 0 });
  return { kind: base.startsWith("d_") ? "drought" : "fire", key, season: SEASON_OF[month], band, years, total };
}

export type Change = { total: number; state: number; season: number; method: number };

/**
 * Split the change from last issue's probability to this issue's.
 *
 * Drought rows depend on (category, month): state = p(c_now, m_prev) -
 * p(c_prev, m_prev), season = p(c_now, m_now) - p(c_now, m_prev). The fire
 * model depends on the dryness percentile alone, so its change is all state.
 * A regional base rate depends on the calendar alone, so its change is all
 * season. Anything left (the live arm starting between the two issues) is the
 * method part. state + season + method = total, exactly.
 */
export function decompose(ex: Explain | null, target: string, prev: CellState, now: CellState, pPrev: number, pNow: number, regional: boolean): Change {
  const total = pNow - pPrev;
  if (regional) return { total, state: 0, season: total, method: 0 };
  if (!ex) return { total, state: 0, season: 0, method: total };
  // Every term under the method in use now; whatever the method itself changed is left over.
  const base = (s: CellState) => liveProbability(ex, target, s, "base");
  const current = (p: number | null) => (p === null ? null : withLiveArm(ex, target, now.issue, p));
  const a = current(base(prev));
  const c = current(base(now));
  if (a === null || c === null) return { total, state: 0, season: 0, method: total };
  let state = c - a;
  let season = 0;
  if (baseOf(target).startsWith("d_")) {
    const mid = current(base({ issue: prev.issue, usdm: now.usdm, erc_pct: now.erc_pct })); // now's category, last issue's month
    if (mid !== null) {
      state = mid - a;
      season = c - mid;
    }
  }
  // Published probabilities are rounded to four decimals, so a residue that
  // small is rounding, not a change of method: it goes to the state part,
  // keeping state + season + method equal to the total.
  let method = total - state - season;
  if (Math.abs(method) < ROUNDING) {
    state += method;
    method = 0;
  }
  return { total, state, season, method };
}
