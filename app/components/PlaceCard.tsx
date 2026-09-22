"use client";

import { Horizon, Place, Target } from "@/lib/api";
import { UncertaintyBadge } from "./UncertaintyBadge";
import { WhyBars } from "./WhyBars";

const HCHIPS = ["2", "4", "8"] as const;

/**
 * How a number is shown is not decided here. It was decided in
 * docs/PREREGISTRATION_LOOK3.md before the sealed year was opened, stored per
 * target, horizon and domain in the export, and is read off the payload. This
 * component renders the decision and its reason; it never infers one.
 */

/** Human labels for the probabilistic target names in the export. */
const TARGET_LABELS: Record<string, string> = {
  d_ge2: "Drought reaching D2 or worse",
  d_ge3: "Drought reaching D3 or worse",
  d_improve1: "Drought easing by a category",
  d_intensify1: "Drought worsening by a category",
  d_intensify2: "Drought worsening by two categories",
  d_nochange: "Drought staying where it is",
  f_gt80: "Fire-spread conditions above the 80th percentile",
  f_gt90: "Fire-spread conditions above the 90th percentile",
  f_gt97: "Fire-spread conditions above the 97th percentile",
};

function labelFor(name: string): string {
  const base = name.replace(/_h\d+$/, "");
  return TARGET_LABELS[base] ?? base.replace(/_/g, " ");
}

function horizonOf(name: string): string {
  const m = name.match(/_h(\d+)$/);
  return m ? m[1] : "";
}

/** The continuous ERC percentile, in whichever state the preregistration fixed. */
function ErcBlock({ hz }: { hz: Horizon | undefined }) {
  const point = hz?.point;
  const state = hz?.state;

  if (point === null || point === undefined) {
    return <p className="text-ink-soft mt-2 text-xs">No forecast for this cell and range.</p>;
  }

  return (
    <>
      <p className="text-ember display text-4xl font-normal">{point.toFixed(0)}</p>

      {state === "interval" && hz?.lo !== null && hz?.lo !== undefined && hz?.hi !== null && hz?.hi !== undefined ? (
        <>
          <div className="bg-paper-sunk relative mt-2 h-2 rounded-full">
            <div
              className="bg-ember/60 absolute h-2 rounded-full"
              style={{ left: `${hz.lo}%`, width: `${Math.max(2, hz.hi - hz.lo)}%` }}
            />
          </div>
          <p className="text-ink-soft mt-1 text-xs" data-testid="erc-interval">
            Forecast interval {hz.lo.toFixed(0)} to {hz.hi.toFixed(0)}, on the 0 to 100 scale of how
            dry this cell is for the time of year. Not an ignition forecast.
          </p>
        </>
      ) : null}

      {state === "historical_range" && hz?.range_lo !== null && hz?.range_lo !== undefined && hz?.range_hi !== null && hz?.range_hi !== undefined ? (
        <>
          <div className="bg-paper-sunk relative mt-2 h-2 rounded-full">
            <div
              className="bg-ink/20 absolute h-2 rounded-full"
              style={{ left: `${hz.range_lo}%`, width: `${Math.max(2, hz.range_hi - hz.range_lo)}%` }}
            />
          </div>
          <p className="text-ink-soft mt-1 text-xs" data-testid="erc-historical-range">
            {hz.range_label ?? "Historical range for this week of year"}:{" "}
            {hz.range_lo.toFixed(0)} to {hz.range_hi.toFixed(0)}. A forecast interval is not shown
            at this range because it is no narrower than this band. Not an ignition forecast.
          </p>
        </>
      ) : null}

      {state === "uncalibrated" ? (
        <p className="text-ink-soft mt-2 text-xs" data-testid="erc-uncalibrated">
          Interval not shown: this range did not hold its coverage on the sealed year, so no band is
          drawn. The point forecast still applies. Not an ignition forecast.
        </p>
      ) : null}

      {hz?.reason ? (
        <p className="text-mute mt-1 text-[11px] leading-relaxed" data-testid="erc-reason">
          {hz.reason}
        </p>
      ) : null}
    </>
  );
}

/** One probabilistic target: a per-cell probability, or the regional base rate. */
function TargetRow({ name, t }: { name: string; t: Target }) {
  if (t.p === null || t.p === undefined) return null;
  const isBase = t.state === "base_rate";
  return (
    <li className="border-rule border-t py-2" data-testid={isBase ? "target-base-rate" : "target-probability"}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm">
          {labelFor(name)}
          <span className="text-mute text-xs"> · {horizonOf(name)} weeks</span>
        </span>
        <span className="num text-ink text-sm">{(t.p * 100).toFixed(0)}%</span>
      </div>
      <p className="text-mute mt-1 text-[11px] leading-relaxed">
        {isBase
          ? `This is the rate across the whole county, the same number for every cell here. ${t.reason ?? ""}`
          : t.reason}
      </p>
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
}: {
  place: Place;
  horizon: string;
  onHorizon: (h: string) => void;
  onClose: () => void;
  onAdopt: () => void;
  onPredict: () => void;
  onReport: () => void;
}) {
  const hz: Horizon | undefined = place.horizons[horizon];
  const u = place.uncertainty;
  const targets = Object.entries(place.targets ?? {})
    .filter(([name]) => horizonOf(name) === horizon)
    .sort(([a], [b]) => a.localeCompare(b));

  return (
    <aside
      data-testid="place-card"
      /* Mobile: a bottom sheet over the map. Desktop: it is rendered inside the
         reading panel, so it must be a plain block there and not cover the map. */
      className="border-rule bg-paper-raised fixed inset-x-0 bottom-0 z-30 max-h-[70dvh] overflow-y-auto border-t p-5 shadow-[0_-2px_24px_rgba(23,24,27,0.12)] lg:static lg:max-h-none lg:border-0 lg:border-t lg:px-6 lg:pb-8 lg:pt-6 lg:shadow-none"
    >
      <button className="text-ink-soft text-sm" onClick={onClose}>
        Close
      </button>
      <p className="text-ink-soft mt-1 text-xs">
        {place.lat.toFixed(3)}, {place.lon.toFixed(3)} · {place.resolution_m} m cells · {place.issue}
        {place.domain ? ` · ${place.domain}` : ""}
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

      <h2 className="mt-4 text-2xl font-semibold">How dry, for the time of year</h2>
      <ErcBlock hz={hz} />

      {place.usdm !== null && place.usdm !== undefined ? (
        <p className="text-ink-soft mt-3 text-xs">
          Current drought category on this cell: D{Math.round(place.usdm)}.
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
    </aside>
  );
}
