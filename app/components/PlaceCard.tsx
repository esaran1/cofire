"use client";

import { Horizon, Place, Target } from "@/lib/api";
import { targetHorizon, targetLabel } from "@/lib/targets";
import { Disclosure } from "./ui/Controls";
import { UncertaintyBadge } from "./UncertaintyBadge";
import { WhyBars } from "./WhyBars";

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
function ErcBlock({ hz }: { hz: Horizon | undefined }) {
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

      {state === "uncalibrated" ? (
        <p className="text-ink-soft mt-3 text-xs" data-testid="erc-uncalibrated">
          No band shown: this range did not hold its coverage on the sealed year.
        </p>
      ) : null}

      {hz?.reason ? (
        <div className="mt-2" data-testid="erc-reason">
          <Disclosure
            summary={<span className="text-mute text-[11px]">How this band was chosen</span>}
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
function TargetRow({ name, t }: { name: string; t: Target }) {
  if (t.p === null || t.p === undefined) return null;
  const isBase = t.state === "base_rate";
  return (
    <li
      className="border-rule border-b py-2.5 last:border-b-0"
      data-testid={isBase ? "target-base-rate" : "target-probability"}
    >
      <Disclosure
        summary={
          <div className="flex items-baseline justify-between gap-3">
            <span className="min-w-0">
              <span className="block text-sm">{targetLabel(name)}</span>
              {isBase ? (
                <span className="text-mute block text-[11px]">same for the whole county</span>
              ) : null}
            </span>
            <span className="num text-ink text-sm">{formatProbability(t.p)}</span>
          </div>
        }
      >
        {isBase
          ? `The same number for every cell in this county. ${sentence(t.reason ?? "")}`
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
}: {
  place: Place;
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
  const u = place.uncertainty;
  const targets = Object.entries(place.targets ?? {})
    .filter(([name]) => targetHorizon(name) === horizon)
    .sort(([a], [b]) => a.localeCompare(b));

  return (
    <aside
      data-testid="place-card"
      /* Mobile: a bottom sheet over the map. Desktop: it is rendered inside the
         reading panel, so it must be a plain block there and not cover the map. */
      className={
        embedded
          ? "border-rule bg-paper-raised border p-5 md:p-6"
          : "border-rule bg-paper-raised fixed inset-x-0 bottom-0 z-30 max-h-[70dvh] overflow-y-auto border-t p-5 shadow-[0_-2px_24px_rgba(23,24,27,0.12)] lg:static lg:max-h-none lg:border-0 lg:border-t lg:px-6 lg:pb-8 lg:pt-6 lg:shadow-none"
      }
    >
      {!embedded ? (
        <button className="text-ink-soft text-sm" onClick={onClose}>
          Close
        </button>
      ) : null}
      <p className="text-ink-soft mt-1 text-xs">
        {place.domain ? `${place.domain.charAt(0).toUpperCase()}${place.domain.slice(1)} · ` : ""}
        {place.issue}
      </p>
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
      <ErcBlock hz={hz} />

      {place.usdm !== null && place.usdm !== undefined ? (
        <p className="text-ink-soft mt-3 text-xs">
          Drought now: D{Math.round(place.usdm)}.
        </p>
      ) : null}

      {targets.length > 0 ? (
        <>
          <h3 className="mt-5 text-lg">What could happen in {horizon} weeks</h3>
          <ul className="mt-1">
            {targets.map(([name, t]) => (
              <TargetRow key={name} name={name} t={t} />
            ))}
          </ul>
        </>
      ) : null}

      {u && <UncertaintyBadge u={u} />}
      {(place.why ?? []).length > 0 ? (
        <>
          <h3 className="mb-2 mt-5 text-lg">Why</h3>
          <WhyBars bars={place.why ?? []} />
        </>
      ) : null}
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
