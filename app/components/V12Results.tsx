"use client";

import v12 from "@/lib/facts_v12.json";
import { domainLabel } from "@/lib/domainNames";
import { useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import { targetLabel } from "@/lib/targets";

/**
 * The v1.2 stages on the Method page, from app/lib/facts_v12.json
 * (cofire/v12/facts.py, generated from the stage artifacts). No number here is
 * typed by hand.
 */
type Row = { stage: number; arm: string; family?: string; shippable?: boolean; pairs: number; mean_brier_A: number;
  mean_brier_arm: number; estimable: number; beat_A_paired: number; qualifying: number; adopted: number };

function family(r: Row): string {
  if (r.family) return r.family;
  if (r.arm.startsWith("S2+S1")) return "S2+S1";
  if (r.arm.startsWith("S2-offset")) return "S2-offset";
  return r.arm;
}

export function V12Results() {
  const { lang, t } = useT();
  const rows = v12.stages as Row[];
  const live = v12.live;
  const nPairs = live.pairs;
  const intervals = v12.intervals as { pairs: number; band_allowed: number } | null;
  return (
    <div data-testid="v12-results">
      <p className="text-ink-soft mt-2 max-w-[58ch] text-sm leading-relaxed">{t("v12.lede", { n: rows[0]?.estimable ?? nPairs })}</p>
      <div className="mt-4 overflow-x-auto" tabIndex={0} role="region" aria-label={t("v12.title")}>
        <table className="w-full min-w-[34rem] text-sm" data-testid="v12-table">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wide text-mute">
              <th className="pb-1 font-normal">{t("v12.colChange")}</th>
              <th className="pb-1 text-right font-normal">{t("v12.colBrier")}</th>
              <th className="pb-1 text-right font-normal">{t("v12.colBeat")}</th>
              <th className="pb-1 text-right font-normal">{t("v12.colAdopted")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.stage}-${r.arm}`} className="border-t border-rule align-top">
                <td className="py-2 pr-3">
                  <span className="text-mute">{r.stage}. </span>
                  {t(`v12.arm.${family(r)}` as MessageKey)}
                  {r.stage === 1 && r.shippable === false ? (
                    <span className="block text-[11px] text-mute">{t("v12.notEligible")}</span>
                  ) : null}
                </td>
                <td className="num py-2 text-right">
                  {r.mean_brier_A.toFixed(4)} → {r.mean_brier_arm.toFixed(4)}
                </td>
                <td className="num py-2 text-right">{t("v12.beatOf", { n: r.beat_A_paired, m: r.estimable })}</td>
                <td className="num py-2 text-right">{r.adopted}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="mt-6 text-base font-medium">{t("v12.liveTitle")}</h3>
      {live.changed.length === 0 ? (
        <p className="text-ink-soft mt-1 text-sm" data-testid="v12-live">{t("v12.liveAll", { n: nPairs })}</p>
      ) : (
        <div className="text-ink-soft mt-1 text-sm" data-testid="v12-live">
          <p>{t("v12.liveSome", { a: live.on_configuration_A, n: nPairs, date: live.changed[0].applies_from })}</p>
          <ul className="mt-1 list-disc pl-5">
            {live.changed.map((c) => {
              const rec = live.survivor_recheck.find((x: { domain: string; target: string }) => x.domain === c.domain && x.target === c.target) as
                | { survivor_with_configuration_A: boolean; survivor_with_live_arm: boolean }
                | undefined;
              return (
                <li key={`${c.domain}-${c.target}`}>
                  {t("v12.liveItem", { area: domainLabel(c.domain), target: targetLabel(c.target, c.domain === "denver" ? "urban" : null, lang) })}
                  {rec && rec.survivor_with_configuration_A ? (
                    <span className="block text-xs text-mute">
                      {rec.survivor_with_live_arm ? t("v12.survivorKept") : t("v12.survivorLost")}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
          <p className="mt-1 text-xs text-mute">
            {t("v12.liveNote", {
              pct: (() => {
                const r = rows.find((x) => x.arm === live.changed[0].arm);
                return r ? Math.max(0.1, (100 * (r.mean_brier_A - r.mean_brier_arm)) / r.mean_brier_A).toFixed(1) : "0.1";
              })(),
            })}
          </p>
        </div>
      )}

      <h3 className="mt-6 text-base font-medium">{t("v12.whyTitle")}</h3>
      <p className="text-ink-soft mt-1 max-w-[58ch] text-sm leading-relaxed">{t("v12.why", { n: rows[0]?.estimable ?? nPairs })}</p>

      <h3 className="mt-6 text-base font-medium">{t("v12.intTitle")}</h3>
      <p className="text-ink-soft mt-1 max-w-[58ch] text-sm leading-relaxed" data-testid="v12-intervals">
        {!intervals
          ? t("v12.intNotRun")
          : intervals.band_allowed > 0
            ? t("v12.intAllowed", { n: intervals.band_allowed, m: intervals.pairs })
            : t("v12.intNone", { m: intervals.pairs })}
      </p>
      <p className="mt-3 text-[11px] text-mute">{t("v12.prereg", { sha: `${v12.prereg_sha256.slice(0, 12)}…` })}</p>
    </div>
  );
}
