/**
 * The weekly brief's numbers, from the bundles alone: Denver's drought now and
 * its 4-week odds, dryness and fire-spread odds where its water comes from,
 * and what changed since the previous issue. Pure, so the page and the test
 * read the same thing. Nothing here is a new estimate: every number is a value
 * in a bundle, a count of cells, or a difference between two issues.
 */
import type { Bundle } from "./schemas";

export const BRIEF_HORIZON = "4";

export type Odds = { mean: number | null; state: string | null };

export type DroughtRow = {
  cat: number;
  cells: number;
  cellsPrev: number | null;
  // null: not checked for this area, so not shown. "impossible": the move
  // cannot happen from this category (no easing from none, no worsening from D4).
  stay: number | null;
  ease: number | null | "impossible";
  worsen: number | null | "impossible";
};

export type AreaBrief = {
  id: string;
  label: string;
  cells: number;
  dryNow: number | null;
  dryNowPrev: number | null;
  dryAhead: number | null;
  f80: Odds | null;
  f90: Odds | null;
  f80Prev: number | null;
  rows: DroughtRow[];
};

export type Brief = { issue: string; prevIssue: string | null; denver: AreaBrief; water: AreaBrief[] };

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function odds(summary: Bundle["summary"], key: string): Odds | null {
  const blk = summary[BRIEF_HORIZON] as Record<string, unknown> | undefined;
  const o = blk?.[`${key}_h${BRIEF_HORIZON}`] as { mean?: unknown; state?: unknown } | undefined;
  return o ? { mean: num(o.mean), state: typeof o.state === "string" ? o.state : null } : null;
}

function counts(b: Bundle): Map<number, number> {
  const m = new Map<number, number>();
  for (const c of b.cells) {
    if (c.usdm === null || c.usdm === undefined) continue;
    const k = Math.round(c.usdm);
    m.set(k, (m.get(k) ?? 0) + 1);
  }
  return m;
}

function droughtRows(b: Bundle, prev: Bundle | null): DroughtRow[] {
  const now = counts(b);
  const before = prev ? counts(prev) : null;
  const at = (t: string) => b.targets.indexOf(`${t}_h${BRIEF_HORIZON}`);
  const rows: DroughtRow[] = [];
  for (const cat of [...now.keys()].sort((x, y) => y - x)) {
    // Drought odds depend on the current category and the season only, so
    // every cell in a category carries the same numbers; read the first.
    const cell = b.cells.find((c) => c.usdm !== null && c.usdm !== undefined && Math.round(c.usdm) === cat);
    const p = (t: string) => (cell && at(t) >= 0 ? num(cell.p[at(t)]) : null);
    rows.push({
      cat,
      cells: now.get(cat) ?? 0,
      cellsPrev: before ? (before.get(cat) ?? 0) : null,
      stay: p("d_nochange"),
      ease: cat === 0 ? "impossible" : p("d_improve1"),
      worsen: cat === 4 ? "impossible" : p("d_intensify1"),
    });
  }
  return rows;
}

function area(id: string, label: string, b: Bundle, prev: Bundle | null): AreaBrief {
  const blk = b.summary[BRIEF_HORIZON] as Record<string, unknown> | undefined;
  return {
    id,
    label,
    cells: b.cells.length,
    dryNow: num(b.summary.erc_pct_now_median),
    dryNowPrev: prev ? num(prev.summary.erc_pct_now_median) : null,
    dryAhead: num(blk?.erc_pct_median),
    f80: odds(b.summary, "f_gt80"),
    f90: odds(b.summary, "f_gt90"),
    f80Prev: prev ? (odds(prev.summary, "f_gt80")?.mean ?? null) : null,
    rows: droughtRows(b, prev),
  };
}

/** The brief for one issue. `prev*` are the previous issue's bundles, when there is one. */
export function buildBrief(
  denver: Bundle,
  water: { id: string; label: string; bundle: Bundle }[],
  prevDenver: Bundle | null,
  prevWater: Record<string, Bundle | null>,
): Brief {
  return {
    issue: denver.issue,
    prevIssue: prevDenver?.issue ?? null,
    denver: area("denver", "Denver", denver, prevDenver),
    water: water.map((w) => area(w.id, w.label, w.bundle, prevWater[w.id] ?? null)),
  };
}
