"use client";

import { Horizon, Place } from "@/lib/api";
import { UncertaintyBadge } from "./UncertaintyBadge";
import { WhyBars } from "./WhyBars";

const HCHIPS = ["2", "4", "8"] as const;

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
  const cats = ["None/D0", "D0", "D1", "D2", "D3/D4"];
  const point = hz?.drought_point ?? 0;
  const set = new Set(hz?.drought_set ?? []);
  const fire = hz?.fire_index ?? 0;
  const u = place.uncertainty;
  // An uncalibrated regime suppresses the interval entirely: showing a band the
  // record cannot support is worse than showing none. Widen when extrapolating.
  const showInterval = u ? u.show_interval : true;
  const widen = u?.status === "extrapolating" ? u.widen_factor : 1;
  const rawLo = hz?.fire_lo ?? fire;
  const rawHi = hz?.fire_hi ?? fire;
  const mid = (rawLo + rawHi) / 2;
  const half = ((rawHi - rawLo) / 2) * widen;
  const lo = Math.max(0, mid - half);
  const hi = Math.min(100, mid + half);
  return (
    <aside
      data-testid="place-card"
      className="absolute inset-x-0 bottom-16 z-30 max-h-[70vh] overflow-y-auto rounded-t-2xl bg-[#14161c] p-4 shadow-2xl"
    >
      <button className="text-mute text-sm" onClick={onClose}>
        Close
      </button>
      <p className="text-mute text-xs mt-1">
        {place.lat.toFixed(3)}, {place.lon.toFixed(3)} · {place.resolution_m} m cells · {place.issue}
      </p>
      <div className="flex gap-2 mt-3">
        {HCHIPS.map((h) => (
          <button
            key={h}
            onClick={() => onHorizon(h)}
            className={`px-3 py-1 rounded-full text-sm ${horizon === h ? "bg-paper text-ink" : "bg-white/10"}`}
          >
            {h}w
          </button>
        ))}
      </div>
      <h2 className="text-2xl mt-4 font-semibold">Drought category</h2>
      <div className="flex gap-1 mt-2">
        {[0, 1, 2, 3, 4].map((c) => (
          <span
            key={c}
            className={`px-2 py-1 text-xs rounded ${Math.round(point) === c ? "bg-drought text-ink" : set.has(c) ? "bg-drought/30" : "bg-white/10"}`}
          >
            {c}
          </span>
        ))}
      </div>
      <p className="text-mute text-xs mt-1">Point {point.toFixed(1)} · conformal set highlighted · {cats[Math.round(point)] ?? ""}</p>
      <h2 className="text-2xl mt-4 font-semibold">Fire-spread condition</h2>
      <p className="text-fire text-3xl font-semibold">{fire.toFixed(0)}</p>
      {showInterval ? (
        <>
          <div className="h-2 bg-white/10 rounded-full mt-2 relative">
            <div
              className="absolute h-2 bg-fire/60 rounded-full"
              style={{ left: `${lo}%`, width: `${Math.max(2, hi - lo)}%` }}
            />
          </div>
          <p className="text-mute text-xs mt-1">
            Interval {lo.toFixed(0)}-{hi.toFixed(0)} (ERC percentile index, 0-100)
            {widen > 1 ? ` · widened ${widen.toFixed(2)}×` : ""}. Not an ignition forecast.
          </p>
        </>
      ) : (
        <p className="text-mute text-xs mt-2">
          Interval hidden: the calibration record does not support one for these conditions. The
          point forecast and the drivers below still apply. Not an ignition forecast.
        </p>
      )}
      {u && <UncertaintyBadge u={u} />}
      <h3 className="text-lg mt-5 mb-2">Why</h3>
      <WhyBars bars={place.why ?? []} />
      <div className="grid grid-cols-3 gap-2 mt-5">
        <button onClick={onAdopt} className="bg-white/10 rounded-lg py-3 text-sm">
          Adopt
        </button>
        <button onClick={onPredict} className="bg-white/10 rounded-lg py-3 text-sm">
          Predict here
        </button>
        <button onClick={onReport} className="bg-white/10 rounded-lg py-3 text-sm">
          Report here
        </button>
      </div>
    </aside>
  );
}
