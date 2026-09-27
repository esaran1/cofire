"use client";

import type { Bundle } from "@/lib/schemas";

const THRESHOLDS = ["80", "90", "97"] as const;

type Odds = { mean: number | null; min: number | null; max: number | null; state: string | null };

function pct(p: number | null | undefined): string {
  if (p === null || p === undefined) return "n/a";
  if (p <= 0) return "0%";
  if (p * 100 < 1) return "<1%";
  return `${(p * 100).toFixed(0)}%`;
}

/**
 * Fire-spread odds where Denver's water comes from.
 *
 * Denver Water collects from the Upper South Platte above Strontia Springs and
 * the Blue River above Dillon. A fire there is a water problem for the city
 * long after it is out, so the Denver card carries both watersheds' odds.
 * Each number is the average over the watershed's cells; a base-rate target
 * shows the same number everywhere and is marked.
 */
export function WatershedPanel({ sources, horizon }: { sources: Bundle["sources"]; horizon: string }) {
  const entries = Object.entries(sources);
  if (entries.length === 0) return null;
  return (
    <section className="mt-6 border-t border-rule pt-5" data-testid="watershed-panel">
      <h3 className="text-lg">Where Denver&apos;s water comes from</h3>
      <p className="mt-1 text-xs leading-relaxed text-ink-soft">
        Chance of fire-spread conditions in {horizon} weeks, averaged over each watershed.
      </p>
      <table className="mt-3 w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-mute">
            <th className="pb-1 font-normal">Watershed</th>
            {THRESHOLDS.map((t) => (
              <th key={t} className="pb-1 text-right font-normal">
                Above {t}th
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entries.map(([id, s]) => {
            const blk = (s.summary[horizon] ?? {}) as Record<string, Odds | number | null>;
            return (
              <tr key={id} className="border-t border-rule" data-testid={`watershed-${id}`}>
                <td className="py-2 pr-2">{s.label}</td>
                {THRESHOLDS.map((t) => {
                  const o = blk[`f_gt${t}_h${horizon}`] as Odds | undefined;
                  const base = o?.state === "base_rate";
                  return (
                    <td key={t} className="num py-2 text-right" title={base ? "Same for the whole watershed" : undefined}>
                      {pct(o?.mean)}
                      {base ? <sup className="ml-0.5 text-mute">*</sup> : null}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] leading-relaxed text-mute">
        * The watershed&apos;s usual rate for this time of year, shown where a per-cell number could not be
        checked.
      </p>
      <p className="mt-3 text-xs leading-relaxed text-ink-soft">
        After the 1996 Buffalo Creek and 2002 Hayman fires, sediment washed into Strontia Springs Reservoir for
        years.
      </p>
    </section>
  );
}
