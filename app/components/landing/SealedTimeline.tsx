"use client";

import { useT } from "@/lib/i18n";
import { LockSimpleOpen } from "@phosphor-icons/react";
import facts from "@/lib/facts.json";

/**
 * The record as a timeline: what each stretch of years was used for, and the
 * one year nothing was allowed to touch.
 *
 * This is the picture of the project's discipline. Fifteen years to learn from,
 * two to choose between methods, two to tune the uncertainty, and 2026 kept
 * sealed until every decision was frozen, then opened once.
 *
 * Years are parsed from `facts.split`, so the bar cannot disagree with the
 * configuration that actually ran.
 */

function years(span: string): [number, number] {
  const ys = (span.match(/\d{4}/g) ?? []).map(Number);
  return [ys[0], ys[ys.length - 1]];
}

export function SealedTimeline() {
  const { t } = useT();
  const segs = [
    { key: "train", label: t("land.seg.train"), span: years(facts.split.train), tone: "bg-ink" },
    { key: "validate", label: t("land.seg.validate"), span: years(facts.split.validate), tone: "bg-ink-soft" },
    { key: "calibrate", label: t("land.seg.calibrate"), span: years(facts.split.calibrate), tone: "bg-mute" },
    { key: "holdout", label: t("land.seg.holdout"), span: years(facts.split.holdout), tone: "bg-spruce" },
  ];
  const first = segs[0].span[0];
  const last = segs[segs.length - 1].span[1];
  const total = last - first + 1;

  return (
    <figure className="w-full">
      <div className="flex w-full gap-1">
        {segs.map((s) => {
          const n = s.span[1] - s.span[0] + 1;
          return (
            <div key={s.key} style={{ flexGrow: n, flexBasis: 0 }} className="min-w-0">
              <div className={`h-14 md:h-20 ${s.tone} ${s.key === "holdout" ? "relative" : ""}`}>
                {s.key === "holdout" ? (
                  <LockSimpleOpen
                    size={26}
                    weight="bold"
                    className="text-paper absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 md:block"
                    aria-hidden
                  />
                ) : null}
              </div>
              <div className="mt-3 hidden truncate md:block">
                <span
                  className={`block text-sm font-medium md:text-base ${s.key === "holdout" ? "text-spruce" : "text-ink"}`}
                >
                  {s.label}
                </span>
                <span className="num text-mute block text-xs md:text-sm">
                  {s.span[0] === s.span[1] ? s.span[0] : `${s.span[0]} to ${s.span[1]}`}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      {/* On a phone the short segments are too narrow to label, so the labels
          move into a legend instead of truncating to "Choo" and "Se". */}
      <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 md:hidden">
        {segs.map((s) => (
          // A <dl> may hold only dt and dd groups (axe: definition-list), so
          // the colour swatch sits inside the term.
          <div key={s.key}>
            <dt className={`flex items-start gap-3 text-sm font-medium ${s.key === "holdout" ? "text-spruce" : "text-ink"}`}>
              <span className={`mt-1 h-3 w-3 shrink-0 ${s.tone}`} aria-hidden />
              {s.label}
            </dt>
            <dd className="num text-mute pl-6 text-xs">
              {s.span[0] === s.span[1] ? s.span[0] : `${s.span[0]} to ${s.span[1]}`}
            </dd>
          </div>
        ))}
      </dl>
      <figcaption className="sr-only">
        {t("land.timeline", { total, a: segs[0].span[0], b: segs[0].span[1], last })}
      </figcaption>
    </figure>
  );
}
