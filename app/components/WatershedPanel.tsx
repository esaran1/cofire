"use client";

import type { Bundle } from "@/lib/schemas";
import { useT } from "@/lib/i18n";
import { LINKS } from "@/lib/links";

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
  const { lang, t } = useT();
  const cite = (id: "denver_water_sources" | "denver_water_hayman") => (
    <a href={LINKS[id].url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2" data-link={id}>
      {LINKS[id][lang]}
    </a>
  );
  const entries = Object.entries(sources);
  if (entries.length === 0) return null;
  return (
    <section className="mt-6 border-t border-rule pt-5" data-testid="watershed-panel">
      <h3 className="text-lg">{t("ws.title")}</h3>
      <p className="mt-1 text-xs leading-relaxed text-ink-soft" data-testid="watershed-supply">
        {t("ws.supply")} <span className="text-mute">({cite("denver_water_sources")})</span>
      </p>
      <p className="mt-1 text-xs leading-relaxed text-ink-soft">
        {t("ws.lede", { h: horizon })}
      </p>
      <table className="mt-3 w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-mute">
            <th className="pb-1 font-normal">{t("ws.col")}</th>
            {THRESHOLDS.map((th) => (
              <th key={th} className="pb-1 text-right font-normal">
                {t("ws.above", { t: th })}
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
                {THRESHOLDS.map((th) => {
                  const o = blk[`f_gt${th}_h${horizon}`] as Odds | undefined;
                  const base = o?.state === "base_rate";
                  return (
                    <td key={th} className="num py-2 text-right" title={base ? t("ws.same") : undefined}>
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
        {t("ws.footnote")}
      </p>
      <p className="mt-3 text-xs leading-relaxed text-ink-soft">
        {t("ws.history")} <span className="text-mute">({cite("denver_water_hayman")})</span>
      </p>
    </section>
  );
}
