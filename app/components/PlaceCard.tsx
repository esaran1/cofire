"use client";

import { X } from "@phosphor-icons/react";
import { useState } from "react";

import { Horizon, Place, Target } from "@/lib/api";
import { domainLabel } from "@/lib/domainNames";
import type { Bundle, DomainMeta } from "@/lib/schemas";
import { targetHorizon, targetLabel } from "@/lib/targets";
import { type Lang, locale, useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import { reasonEs } from "@/lib/i18n/reasons";
import { type CellState, type Explain, categoryOf, decompose, frequency, monthOf, weeksLikeThis } from "@/lib/explain";
import { IconArray, WeeksLikeThis, WhyChanged, eventPhrase, frequencySentence } from "./Explain";
import { LINKS } from "@/lib/links";
import { Disclosure } from "./ui/Controls";
import { WatershedPanel } from "./WatershedPanel";

const HCHIPS = ["2", "4", "8"] as const;

/**
 * How a number is shown is not decided here. It was decided in
 * docs/PREREGISTRATION_LOOK3.md before the sealed year was opened, stored per
 * target, horizon and domain in the export, and is read off the payload. This
 * component renders the decision and its reason; it never infers one.
 */

/**
 * A probability as a percentage, without asserting impossibility.
 *
 * Rounding 0.006% to "0%" says the event cannot happen, which is a stronger
 * claim than the forecast makes. A small non-zero probability reads as "<1%";
 * an exact zero, which these models do produce, still reads as "0%".
 */
function formatProbability(p: number): string {
  if (p <= 0) return "0%";
  if (p * 100 < 1) return "<1%";
  return `${(p * 100).toFixed(0)}%`;
}

/** Reason strings are generated as sentence fragments; show them as sentences. */
function sentence(text: string): string {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

/**
 * A reason in the reader's language. The export writes reasons in English; a
 * Spanish reader gets the template translation, or the English marked as
 * such when a reason has a clause the table does not know.
 */
function Reason({ text, lang }: { text: string | null | undefined; lang: Lang }) {
  if (lang === "es") {
    const es = reasonEs(text);
    if (es !== null) return <>{sentence(es)}</>;
    return <span lang="en">{sentence(text ?? "")} (en inglés)</span>;
  }
  return <>{sentence(text ?? "")}</>;
}


/**
 * The continuous ERC percentile, in whichever state the preregistration fixed.
 *
 * One sentence of plain meaning, then the band. The width-ratio arithmetic that
 * justifies which band is shown is real, but it is a methodological note, not
 * something a reader needs in order to read the number, so it sits behind a
 * disclosure.
 */
function formatWeek(iso: string, lang: Lang): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(locale(lang), { month: "long", day: "numeric" });
}

function ErcBlock({ hz, erc }: { hz: Horizon | undefined; erc?: number | null }) {
  const { lang, t } = useT();
  const point = hz?.point;
  const state = hz?.state;

  if (point === null || point === undefined) {
    return <p className="text-ink-soft mt-2 text-xs">{t("card.noForecast")}</p>;
  }

  const hasInterval =
    state === "interval" && hz?.lo !== null && hz?.lo !== undefined && hz?.hi !== null && hz?.hi !== undefined;
  const hasRange =
    state === "historical_range" &&
    hz?.range_lo !== null &&
    hz?.range_lo !== undefined &&
    hz?.range_hi !== null &&
    hz?.range_hi !== undefined;

  return (
    <>
      <p className="text-ember display text-5xl font-normal" data-testid="erc-point">
        {point.toFixed(0)}
      </p>

      {hasInterval ? (
        <div data-testid="erc-interval">
          <div className="bg-paper-sunk relative mt-3 h-2 rounded-full">
            <div
              className="bg-ember/60 absolute h-2 rounded-full"
              style={{ left: `${hz!.lo}%`, width: `${Math.max(2, hz!.hi! - hz!.lo!)}%` }}
            />
          </div>
          <p className="text-ink-soft mt-1.5 text-xs">
            {t("card.interval", { lo: hz!.lo!.toFixed(0), hi: hz!.hi!.toFixed(0) })}
          </p>
        </div>
      ) : null}

      {hasRange ? (
        <div data-testid="erc-historical-range">
          <div className="bg-paper-sunk relative mt-3 h-2 rounded-full">
            <div
              className="bg-ink/20 absolute h-2 rounded-full"
              style={{
                left: `${hz!.range_lo}%`,
                width: `${Math.max(2, hz!.range_hi! - hz!.range_lo!)}%` ,
              }}
            />
          </div>
          <p className="text-ink-soft mt-1.5 text-xs">
            {t("card.typical", { lo: hz!.range_lo!.toFixed(0), hi: hz!.range_hi!.toFixed(0) })}
          </p>
        </div>
      ) : null}

      {hz?.hist_lo !== null && hz?.hist_lo !== undefined && hz?.hist_hi !== null && hz?.hist_hi !== undefined ? (
        // History, in raw ERC units, kept apart from the percentile above so
        // the two scales are never drawn against each other.
        <div className="border-rule mt-3 border-l-2 pl-3" data-testid="erc-history">
          <p className="text-mute text-[11px] uppercase tracking-wide">{t("card.historyTitle")}</p>
          <p className="text-ink-soft mt-1 text-xs leading-relaxed">
            {t("card.historyLead", {
              years: hz.hist_years ?? t("card.historyYears"),
              week: hz.target_week ? formatWeek(hz.target_week, lang) : t("card.historyWeek"),
            })}{" "}
            <span className="text-ink tabular-nums">{t("card.range", { lo: hz.hist_lo.toFixed(0), hi: hz.hist_hi.toFixed(0) })}</span>.
            {erc !== null && erc !== undefined ? (
              <> {t("card.historyNow", { erc: erc.toFixed(0) })}</>
            ) : null}
          </p>
        </div>
      ) : null}

      {state === "uncalibrated" ? (
        <p className="text-ink-soft mt-3 text-xs" data-testid="erc-uncalibrated">
          {t("card.uncalibrated")}
        </p>
      ) : null}

      {hz?.reason ? (
        <div className="mt-2" data-testid="erc-reason">
          <Disclosure
            summary={<span className="text-mute text-[11px]">{state === "uncalibrated" ? t("card.whyNoBand") : t("card.howBand")}</span>}
            detail={t("card.show")}
          >
            <Reason text={hz.reason} lang={lang} />
          </Disclosure>
        </div>
      ) : null}
    </>
  );
}

/**
 * One probabilistic target: a per-cell probability, or the regional base rate.
 *
 * The reason is real and worth keeping, but it ran to about 30 words and was
 * printed on every row, so a card with nine targets repeated the same
 * paragraph nine times and buried the numbers. The number leads; the reason is
 * one click away. Base-rate rows keep a short inline marker, because "this is
 * a county-wide number" changes how the value should be read and cannot wait
 * for a click.
 */
const AREA: Record<string, MessageKey> = { county: "area.county", urban: "area.urban", watershed: "area.watershed" };

function TargetRow({ name, t: target, kind, place, prev, prevTarget, explain }: {
  name: string;
  t: Target;
  kind?: string | null;
  place: Place;
  prev?: Place | null;
  prevTarget?: Target | null;
  explain?: Explain | null;
}) {
  const { lang, t } = useT();
  const isBase = target.state === "base_rate";
  const hidden = target.p === null || target.p === undefined;
  // A drought target that did not pass its check has no number (the export
  // drops it: a historical rate beside the model's other drought odds could
  // contradict them). The row stays, so the reader sees what is missing and why.
  if (hidden && !isBase) return null;
  const area = t(AREA[kind ?? "county"] ?? "area.other");
  const marker = hidden ? t("card.notChecked") : t("card.usualRate", { area });
  const p = target.p as number;
  const event = eventPhrase(t, name, kind);
  const sentence = hidden ? "" : frequencySentence(t, p, event, isBase);
  const f = hidden ? null : frequency(p);
  const now: CellState = { issue: place.issue ?? "", usdm: place.usdm ?? null, erc_pct: place.erc_pct ?? null };
  const cases = explain && !isBase && !hidden ? weeksLikeThis(explain, name, now) : null;
  const before: CellState | null = prev ? { issue: prev.issue ?? "", usdm: prev.usdm ?? null, erc_pct: prev.erc_pct ?? null } : null;
  const pPrev = prevTarget?.p;
  const change =
    before && !hidden && pPrev !== null && pPrev !== undefined && prevTarget?.state === target.state
      ? decompose(explain ?? null, name, before, now, pPrev, p, isBase)
      : null;
  return (
    <li
      className="border-rule border-b py-2.5 last:border-b-0"
      data-testid={isBase ? "target-base-rate" : "target-probability"}
      data-target={name}
      data-p={hidden ? "" : p}
    >
      <Disclosure
        summary={
          <div>
            <div className="flex items-baseline justify-between gap-3">
              <span className="min-w-0">
                <span className="block text-sm">{targetLabel(name, kind, lang)}</span>
                {isBase ? <span className="text-mute block text-[11px]">{marker}</span> : null}
              </span>
              <span
                className={hidden ? "text-mute shrink-0 whitespace-nowrap text-xs" : "num text-ink shrink-0 text-sm"}
                data-testid={hidden ? "target-not-shown" : "target-percent"}
              >
                {hidden ? t("card.notShown") : formatProbability(p)}
              </span>
            </div>
            {sentence ? (
              <span className="text-ink-soft mt-0.5 block text-[11px] leading-relaxed" data-testid="frequency" data-n={f?.lessThanOne ? "<1" : f?.n}>
                {sentence}
              </span>
            ) : null}
            {change && prev?.issue ? (
              <WhyChanged change={change} prevIssue={prev.issue} fire={name.startsWith("f_")} regional={isBase} ercFrom={prev.erc_pct} ercTo={place.erc_pct} />
            ) : null}
          </div>
        }
      >
        {f ? <IconArray n={f.n} label={sentence} tone={name.startsWith("f_") ? "ember" : "ochre"} /> : null}
        {cases && explain ? (
          <WeeksLikeThis
            cases={cases}
            target={name}
            kind={kind}
            category={categoryOf(place.usdm ?? null) === 0 ? t("card.droughtNone") : `D${categoryOf(place.usdm ?? null)}`}
            month={monthOf(now.issue)}
            start={explain.train[0].slice(0, 4)}
            end={explain.train[1].slice(0, 4)}
          />
        ) : null}
        <div className="mt-2">
          <Reason text={target.reason} lang={lang} />
        </div>
      </Disclosure>
    </li>
  );
}

/** Share the page's address, which carries the area, cell, range and language. */
function ShareButton() {
  const { t } = useT();
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  async function share() {
    const url = window.location.href;
    try {
      if (navigator.share) {
        await navigator.share({ url, title: document.title });
        return;
      }
      await navigator.clipboard.writeText(url);
      setState("copied");
    } catch (e) {
      // A dismissed share sheet is not a failure.
      if (e instanceof DOMException && e.name === "AbortError") return;
      setState("failed");
    }
  }
  return (
    <div className="mt-3">
      <button type="button" onClick={share} data-testid="share-view" className="text-sm text-ink-soft underline underline-offset-4">
        {t("card.share")}
      </button>
      <span role="status" aria-live="polite" className="ml-2 text-xs text-mute" data-testid="share-status">
        {state === "copied" ? t("card.copied") : state === "failed" ? t("card.shareFailed") : ""}
      </span>
    </div>
  );
}

export function PlaceCard({
  place,
  horizon,
  onHorizon,
  onClose,
  onAdopt,
  adopted = false,
  onPredict,
  onReport,
  embedded = false,
  meta = null,
  sources = {},
  explain = null,
  prev = null,
}: {
  /** The tables behind the probabilities (cofire/v13/explain.py), when loaded. */
  explain?: Explain | null;
  /** The same cell at the previous issue, for "why did this change". */
  prev?: Place | null;
  place: Place;
  /** The area this cell belongs to: its name, kind and how it was evaluated. */
  meta?: DomainMeta | null;
  /** For Denver: the watersheds its water comes from. */
  sources?: Bundle["sources"];
  horizon: string;
  onHorizon: (h: string) => void;
  onClose?: () => void;
  onAdopt?: () => void;
  /** Whether this cell is adopted in this browser. */
  adopted?: boolean;
  onPredict?: () => void;
  onReport?: () => void;
  /**
   * Render inline, as a picture of the product inside the landing story,
   * rather than as the map's bottom sheet. Drops the close and action buttons,
   * which do nothing outside the map.
   */
  embedded?: boolean;
}) {
  const { lang, t } = useT();
  const hz: Horizon | undefined = place.horizons[horizon];
  const targets = Object.entries(place.targets ?? {})
    .filter(([name]) => targetHorizon(name) === horizon)
    .sort(([a], [b]) => a.localeCompare(b));

  return (
    <aside
      data-testid="place-card"
      /* In the reading panel at every width. On phones it used to be a sheet
         fixed over the bottom of the screen, which covered the map's horizon,
         layer and issue controls; the panel below the map already scrolls. */
      className={
        embedded
          ? "border-rule bg-paper-raised border p-5 md:p-6"
          : "border-rule bg-paper-raised border-t px-5 pb-8 pt-5 lg:px-6 lg:pt-6"
      }
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-ink-soft text-xs" data-testid="place-domain">
          {meta?.label ?? domainLabel(place.domain)}
          {place.issue ? ` · ${place.issue}` : ""}
        </p>
        {!embedded ? (
          <button
            onClick={onClose}
            className="text-ink-soft hover:bg-paper-sunk hover:text-ink -mr-2 inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs"
          >
            <X size={14} aria-hidden />
            {t("card.close")}
          </button>
        ) : null}
      </div>
      {meta?.evaluation === "validation" ? (
        <p className="text-mute mt-1 text-[11px] leading-relaxed" data-testid="validation-note">
          {t("card.validation")}
        </p>
      ) : null}
      <div className="mt-3 flex gap-2">
        {HCHIPS.map((h) => (
          <button
            key={h}
            onClick={() => onHorizon(h)}
            aria-pressed={horizon === h}
            aria-label={t("card.chipLabel", { h })}
            className={`rounded-full px-3 py-1 text-sm transition-colors ${horizon === h ? "bg-ink text-paper" : "bg-paper-sunk text-ink-soft hover:text-ink"}`}
          >
            {t("card.chip", { h })}
          </button>
        ))}
      </div>

      <h2 className="mt-4 text-xl font-semibold" data-testid="dryness-heading">
        {t("card.dryness", { h: horizon })}
      </h2>
      <p className="text-mute mt-1 text-[11px] leading-relaxed">{t("card.drynessHelp")}</p>
      <ErcBlock hz={hz} erc={place.erc} />

      {place.usdm !== null && place.usdm !== undefined ? (
        <p className="text-ink-soft mt-3 text-xs">
          {t("card.droughtNow", { cat: Math.round(place.usdm) === 0 ? t("card.droughtNone") : `D${Math.round(place.usdm)}` })}
        </p>
      ) : null}

      {targets.length > 0 ? (
        <>
          <h3 className="mt-5 text-lg">{t("card.whatCould", { h: horizon })}</h3>
          <p className="text-mute mt-1 text-[11px] leading-relaxed" data-testid="drought-note">
            {t("card.droughtNote")}
          </p>
          <ul className="mt-1">
            {targets.map(([name, t]) => (
              <TargetRow
                key={name}
                name={name}
                t={t}
                kind={meta?.kind}
                place={place}
                prev={prev}
                prevTarget={prev?.targets?.[name] ?? null}
                explain={explain}
              />
            ))}
          </ul>
        </>
      ) : null}

      <WatershedPanel sources={sources} horizon={horizon} />

      <section className="border-rule mt-6 border-t pt-4" data-testid="smoke-link">
        <h3 className="text-sm font-medium">{t("card.smokeTitle")}</h3>
        <p className="text-ink-soft mt-1 text-xs leading-relaxed">
          {t("card.smokeNote")}{" "}
          <a href={LINKS.smoke_map.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2" data-link="smoke_map">
            {LINKS.smoke_map[lang]}
          </a>
        </p>
      </section>

      {!embedded ? (
        <div className="mt-6 grid grid-cols-3 gap-2">
          <button
            onClick={onAdopt}
            aria-pressed={adopted}
            data-testid="adopt"
            className={`rounded-full border py-2.5 text-sm transition-colors ${
              adopted ? "border-ink bg-ink text-paper" : "border-rule text-ink hover:border-ink-soft"
            }`}
          >
            {adopted ? t("card.adopted") : t("card.adopt")}
          </button>
          <button onClick={onPredict} className="border-rule text-ink hover:border-ink-soft rounded-full border py-2.5 text-sm transition-colors">
            {t("card.predict")}
          </button>
          <button onClick={onReport} className="border-rule text-ink hover:border-ink-soft rounded-full border py-2.5 text-sm transition-colors">
            {t("card.report")}
          </button>
        </div>
      ) : null}
      {!embedded ? <ShareButton /> : null}
    </aside>
  );
}
