"use client";

import { Horizon, Place, Target } from "@/lib/api";
import { domainLabel } from "@/lib/domainNames";
import type { Bundle, DomainMeta } from "@/lib/schemas";
import { targetHorizon, targetLabel } from "@/lib/targets";
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
 * The continuous ERC percentile, in whichever state the preregistration fixed.
 *
 * One sentence of plain meaning, then the band. The width-ratio arithmetic that
 * justifies which band is shown is real, but it is a methodological note, not
 * something a reader needs in order to read the number, so it sits behind a
 * disclosure.
 */
function formatWeek(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("en-US", { month: "long", day: "numeric" });
}

function ErcBlock({ hz, erc }: { hz: Horizon | undefined; erc?: number | null }) {
  const point = hz?.point;
  const state = hz?.state;

  if (point === null || point === undefined) {
    return <p className="text-ink-soft mt-2 text-xs">No forecast for this cell and range.</p>;
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
      <p className="text-ember display text-5xl font-normal">{point.toFixed(0)}</p>

      {hasInterval ? (
        <div data-testid="erc-interval">
          <div className="bg-paper-sunk relative mt-3 h-2 rounded-full">
            <div
              className="bg-ember/60 absolute h-2 rounded-full"
              style={{ left: `${hz!.lo}%`, width: `${Math.max(2, hz!.hi! - hz!.lo!)}%` }}
            />
          </div>
          <p className="text-ink-soft mt-1.5 text-xs">
            Forecast range {hz!.lo!.toFixed(0)} to {hz!.hi!.toFixed(0)} out of 100.
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
            Typical for this week: {hz!.range_lo!.toFixed(0)} to {hz!.range_hi!.toFixed(0)}. No
            forecast band, because it would be no narrower than this.
          </p>
        </div>
      ) : null}

      {hz?.hist_lo !== null && hz?.hist_lo !== undefined && hz?.hist_hi !== null && hz?.hist_hi !== undefined ? (
        // History, in raw ERC units, kept apart from the percentile above so
        // the two scales are never drawn against each other.
        <div className="border-rule mt-3 border-l-2 pl-3" data-testid="erc-history">
          <p className="text-mute text-[11px] uppercase tracking-wide">History, not a forecast</p>
          <p className="text-ink-soft mt-1 text-xs leading-relaxed">
            In {hz.hist_years ?? "past years"}, raw ERC in this cell around{" "}
            {hz.target_week ? formatWeek(hz.target_week) : "this week"} was usually{" "}
            <span className="num text-ink">
              {hz.hist_lo.toFixed(0)} to {hz.hist_hi.toFixed(0)}
            </span>
            {erc !== null && erc !== undefined ? (
              <>
                . It is <span className="num text-ink">{erc.toFixed(0)}</span> now.
              </>
            ) : (
              "."
            )}
          </p>
        </div>
      ) : null}

      {state === "uncalibrated" ? (
        <p className="text-ink-soft mt-3 text-xs" data-testid="erc-uncalibrated">
          No forecast band: the range method we shipped did not hold up in real time, so none is drawn.
        </p>
      ) : null}

      {hz?.reason ? (
        <div className="mt-2" data-testid="erc-reason">
          <Disclosure
            summary={<span className="text-mute text-[11px]">{state === "uncalibrated" ? "Why there is no band" : "How this band was chosen"}</span>}
            detail="Show"
          >
            {sentence(hz.reason)}
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
const AREA: Record<string, string> = { county: "county", urban: "city", watershed: "watershed" };

function TargetRow({ name, t, kind }: { name: string; t: Target; kind?: string | null }) {
  if (t.p === null || t.p === undefined) return null;
  const isBase = t.state === "base_rate";
  const area = AREA[kind ?? "county"] ?? "area";
  return (
    <li
      className="border-rule border-b py-2.5 last:border-b-0"
      data-testid={isBase ? "target-base-rate" : "target-probability"}
    >
      <Disclosure
        summary={
          <div className="flex items-baseline justify-between gap-3">
            <span className="min-w-0">
              <span className="block text-sm">{targetLabel(name, kind)}</span>
              {isBase ? (
                <span className="text-mute block text-[11px]">same for the whole {area}</span>
              ) : null}
            </span>
            <span className="num text-ink text-sm">{formatProbability(t.p)}</span>
          </div>
        }
      >
        {isBase
          ? `The same number for every cell in this ${area}. ${sentence(t.reason ?? "")}`
          : sentence(t.reason ?? "")}
      </Disclosure>
    </li>
  );
}

export function PlaceCard({
  place,
  horizon,
  onHorizon,
  onClose,
  onAdopt,
  onPredict,
  onReport,
  embedded = false,
  meta = null,
  sources = {},
}: {
  place: Place;
  /** The area this cell belongs to: its name, kind and how it was evaluated. */
  meta?: DomainMeta | null;
  /** For Denver: the watersheds its water comes from. */
  sources?: Bundle["sources"];
  horizon: string;
  onHorizon: (h: string) => void;
  onClose?: () => void;
  onAdopt?: () => void;
  onPredict?: () => void;
  onReport?: () => void;
  /**
   * Render inline, as a picture of the product inside the landing story,
   * rather than as the map's bottom sheet. Drops the close and action buttons,
   * which do nothing outside the map.
   */
  embedded?: boolean;
}) {
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
      {!embedded ? (
        <button className="text-ink-soft text-sm" onClick={onClose}>
          Close
        </button>
      ) : null}
      <p className="text-ink-soft mt-1 text-xs" data-testid="place-domain">
        {meta?.label ?? domainLabel(place.domain)}
        {place.issue ? ` · ${place.issue}` : ""}
      </p>
      {meta?.evaluation === "validation" ? (
        <p className="text-mute mt-1 text-[11px] leading-relaxed" data-testid="validation-note">
          Added after the sealed 2026 test, so these numbers were checked on 2022 and 2023 only.
        </p>
      ) : null}
      <div className="mt-3 flex gap-2">
        {HCHIPS.map((h) => (
          <button
            key={h}
            onClick={() => onHorizon(h)}
            className={`rounded-full px-3 py-1 text-sm ${horizon === h ? "bg-paper text-ink" : "bg-paper-sunk"}`}
          >
            {h}w
          </button>
        ))}
      </div>

      <h2 className="mt-4 text-xl font-semibold">Dryness for this week</h2>
      <ErcBlock hz={hz} erc={place.erc} />

      {place.usdm !== null && place.usdm !== undefined ? (
        <p className="text-ink-soft mt-3 text-xs">
          Drought now: {Math.round(place.usdm) === 0 ? "none or D0" : `D${Math.round(place.usdm)}`}.
        </p>
      ) : null}

      {targets.length > 0 ? (
        <>
          <h3 className="mt-5 text-lg">What could happen in {horizon} weeks</h3>
          <ul className="mt-1">
            {targets.map(([name, t]) => (
              <TargetRow key={name} name={name} t={t} kind={meta?.kind} />
            ))}
          </ul>
        </>
      ) : null}

      <WatershedPanel sources={sources} horizon={horizon} />

      {!embedded ? (
        <div className="mt-5 grid grid-cols-3 gap-2">
          <button onClick={onAdopt} className="bg-paper-sunk rounded-lg py-3 text-sm">
            Adopt
          </button>
          <button onClick={onPredict} className="bg-paper-sunk rounded-lg py-3 text-sm">
            Predict here
          </button>
          <button onClick={onReport} className="bg-paper-sunk rounded-lg py-3 text-sm">
            Report here
          </button>
        </div>
      ) : null}
    </aside>
  );
}
