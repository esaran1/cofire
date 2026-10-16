"use client";

import forward from "@/lib/forward.json";
import seal from "@/lib/seal.json";
import { locale, useT } from "@/lib/i18n";

/**
 * The forecast record: every issued forecast with the time it was published
 * and the sha256 of the exact file (cofire/v12/forward.py). No score appears
 * here: the forecasts are for 2026, the sealed test year, and scoring opens
 * when the seal lifts.
 */
const UNSEAL = seal.unseal_date; // one source for the app, the film and the unseal script

type Entry = { issue: string; sha256: string; published_at: string; backfilled: boolean };

export default function ScoreboardPage() {
  const { lang, t } = useT();
  const entries = [...(forward as Entry[])].reverse();
  const day = (iso: string) =>
    new Date(`${iso.slice(0, 10)}T12:00:00Z`).toLocaleDateString(locale(lang), { year: "numeric", month: "long", day: "numeric" });
  const backfillDay = entries.find((e) => e.backfilled)?.published_at;
  return (
    <div className="reading px-6 pb-24 pt-12">
      <h1 className="display text-4xl" data-testid="score-title">{t("score.title")}</h1>
      <p className="mt-3 leading-relaxed text-ink-soft">{t("score.lede")}</p>

      <section className="mt-8 rounded border border-ochre/40 bg-ochre-soft p-4" data-testid="score-seal">
        <h2 className="text-base font-medium text-ochre">{t("score.sealTitle")}</h2>
        <p className="mt-1 text-sm leading-relaxed text-ochre">{t("score.seal", { date: day(UNSEAL) })}</p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium">{t("score.whatTitle")}</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-ink-soft">
          <li>{t("score.what1")}</li>
          <li>{t("score.what2")}</li>
          <li>{t("score.what3", { date: day(UNSEAL) })}</li>
        </ul>
      </section>

      {backfillDay ? (
        <section className="mt-8">
          <h2 className="text-lg font-medium">{t("score.backfillTitle")}</h2>
          <p className="mt-1 text-sm leading-relaxed text-ink-soft">{t("score.backfill", { date: day(backfillDay) })}</p>
        </section>
      ) : null}

      <p className="mt-8 text-sm text-mute" data-testid="score-count">{t("score.count", { n: entries.length })}</p>
      <div className="mt-2 overflow-x-auto" tabIndex={0} role="region" aria-label={t("score.title")}>
        <table className="w-full min-w-[30rem] text-sm" data-testid="score-table">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wide text-mute">
              <th className="pb-1 font-normal">{t("score.colIssue")}</th>
              <th className="pb-1 font-normal">{t("score.colPublished")}</th>
              <th className="pb-1 font-normal">{t("score.colHash")}</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.issue} className="border-t border-rule" data-issue={e.issue}>
                <td className="num py-1.5 pr-3">{e.issue}</td>
                <td className="py-1.5 pr-3 text-ink-soft">
                  {day(e.published_at)}
                  {e.backfilled ? <span className="ml-1 text-[11px] text-mute">({t("score.backfilled")})</span> : null}
                </td>
                <td className="num py-1.5 text-[11px] text-mute" title={e.sha256}>
                  {e.sha256.slice(0, 16)}…
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[11px] leading-relaxed text-mute">{t("score.verify")}</p>
    </div>
  );
}
