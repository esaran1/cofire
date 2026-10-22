"use client";

import { type Lang, locale, useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import { type Cases, type Change, CHANGE_THRESHOLD, baseOf, frequency, horizonOf } from "@/lib/explain";

/** The event a target describes, as a phrase for "in 100 weeks like this one, about N ...". */
export function eventPhrase(t: (k: MessageKey, v?: Record<string, string | number>) => string, target: string, kind?: string | null): string {
  const base = baseOf(target);
  const key = (kind === "urban" && base.startsWith("f_") ? `ev.urban.${base}` : `ev.${base}`) as MessageKey;
  return t(key, { h: horizonOf(target) });
}

/** "In 100 weeks like this one, about N ..." for a per-cell or regional probability. */
export function frequencySentence(t: (k: MessageKey, v?: Record<string, string | number>) => string, p: number, event: string, regional: boolean): string {
  const f = frequency(p);
  if (f.lessThanOne) return t(regional ? "freq.regionalFew" : "freq.cellFew", { event });
  return t(regional ? "freq.regional" : "freq.cell", { n: f.n, event });
}

/** A 10 x 10 icon array: N filled squares in 100. One image to assistive technology, read as its sentence. */
export function IconArray({ n, label, tone = "ember", segments }: { n: number; label: string; tone?: "ember" | "ochre"; segments?: { n: number; cls: string }[] }) {
  const fills: string[] = [];
  if (segments) {
    for (const s of segments) for (let i = 0; i < s.n && fills.length < 100; i++) fills.push(s.cls);
  } else {
    for (let i = 0; i < Math.min(100, n); i++) fills.push(tone === "ember" ? "bg-ember" : "bg-ochre");
  }
  return (
    <div role="img" aria-label={label} data-testid="icon-array" data-filled={fills.length} className="inline-grid shrink-0 grid-cols-[repeat(10,7px)] gap-[2px]">
      {Array.from({ length: 100 }, (_, i) => (
        <span key={i} aria-hidden className={`h-[7px] w-[7px] rounded-[1px] ${fills[i] ?? "bg-paper-sunk border border-rule/70"}`} />
      ))}
    </div>
  );
}

const dayLabel = (iso: string, lang: Lang) =>
  new Date(`${iso}T12:00:00Z`).toLocaleDateString(locale(lang), { month: "long", day: "numeric" });

/** The training-year cases behind a probability. */
export function WeeksLikeThis({ cases, target, kind, category, month, start, end }: { cases: Cases; target: string; kind?: string | null; category: string; month: number; start: string; end: string }) {
  const { lang, t } = useT();
  const event = eventPhrase(t, target, kind);
  const monthName = new Date(Date.UTC(2020, month - 1, 15)).toLocaleDateString(locale(lang), { month: "long" });
  const season = t(`season.${cases.season}` as MessageKey);
  const when = cases.key === "month" ? t("cases.inMonth", { month: monthName }) : cases.key === "season" ? t("cases.inSeason", { season }) : t("cases.anyTime");
  const intro =
    cases.kind === "drought"
      ? t("cases.drought", { start, end, cat: category, when, event })
      : t("cases.fire", { start, end, lo: (cases.band ?? 0) * 10, hi: (cases.band ?? 0) * 10 + 9, season, event });
  return (
    <div className="mt-3" data-testid="weeks-like-this" data-total-n={cases.total.n} data-total-k={cases.total.k}>
      <p className="text-ink-soft text-xs font-medium">{t("cases.title")}</p>
      <p className="mt-1 text-[11px] leading-relaxed">{intro}</p>
      <table className="mt-2 w-full text-[11px]">
        <thead>
          <tr className="text-mute text-left">
            <th className="font-normal">{t("cases.year")}</th>
            <th className="text-right font-normal">{t("cases.weeks")}</th>
            <th className="text-right font-normal">{t("cases.events")}</th>
          </tr>
        </thead>
        <tbody>
          {cases.years.slice(0, 5).map((y) => (
            <tr key={y.year} className="border-rule border-t">
              <td className="num">{y.year}</td>
              <td className="num text-right">{y.n.toLocaleString(locale(lang))}</td>
              <td className="num text-right">{y.k.toLocaleString(locale(lang))}</td>
            </tr>
          ))}
          <tr className="border-rule border-t font-medium">
            <td>{t("cases.all", { start, end })}</td>
            <td className="num text-right">{cases.total.n.toLocaleString(locale(lang))}</td>
            <td className="num text-right">{cases.total.k.toLocaleString(locale(lang))}</td>
          </tr>
        </tbody>
      </table>
      <p className="text-mute mt-1 text-[11px]">{t("cases.unit")}</p>
    </div>
  );
}

const pts = (x: number) => Math.round(Math.abs(x) * 100);

/** Why a probability moved since the last issue; shown only past the threshold. */
export function WhyChanged({ change, prevIssue, fire, regional, ercFrom, ercTo }: { change: Change; prevIssue: string; fire: boolean; regional: boolean; ercFrom?: number | null; ercTo?: number | null }) {
  const { lang, t } = useT();
  if (Math.abs(change.total) < CHANGE_THRESHOLD) return null;
  const head = t(change.total > 0 ? "change.up" : "change.down", { pts: pts(change.total), date: dayLabel(prevIssue, lang) });
  const signed = (x: number) => `${x >= 0 ? "+" : "−"}${pts(x)}`;
  let detail: string;
  if (regional) detail = t("change.regional");
  else if (fire && change.method === 0) detail = t("change.fire", { a: ercFrom?.toFixed(0) ?? "", b: ercTo?.toFixed(0) ?? "" });
  else {
    const parts = [t("change.state", { pts: signed(change.state) }), t("change.season", { pts: signed(change.season) })];
    if (change.method !== 0) parts.push(t("change.method", { pts: signed(change.method) }));
    detail = t("change.parts", { parts: parts.join(", ") });
  }
  return (
    <p className="text-ink-soft mt-1 text-[11px] leading-relaxed" data-testid="why-changed" data-total={change.total} data-state={change.state} data-season={change.season} data-method={change.method}>
      {head} {detail}
    </p>
  );
}
