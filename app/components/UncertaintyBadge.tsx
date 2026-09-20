"use client";

import { UncertaintyStatus } from "@/lib/api";

const STYLES: Record<UncertaintyStatus["status"], { chip: string; label: string }> = {
  calibrated: { chip: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40", label: "Calibrated" },
  extrapolating: { chip: "bg-amber-500/20 text-amber-300 border-amber-500/40", label: "Extrapolating" },
  uncalibrated: { chip: "bg-fire/20 text-fire border-fire/40", label: "Uncalibrated" },
};

const BLURB: Record<UncertaintyStatus["status"], string> = {
  calibrated: "Current conditions fall inside the range the interval was calibrated on.",
  extrapolating: "Conditions run past the calibration range. The interval is widened and should be read as a floor, not a bound.",
  uncalibrated: "Conditions are outside anything in the record. The interval is hidden rather than shown misleadingly. The point forecast and drivers still apply.",
};

/** Compact chip. Use in the map legend and anywhere space is tight. */
export function UncertaintyChip({ status }: { status: UncertaintyStatus["status"] }) {
  const s = STYLES[status];
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded border text-[10px] uppercase tracking-wide ${s.chip}`}>
      {s.label}
    </span>
  );
}

/** Full panel with the machine-stated reason. Use on the Place Card. */
export function UncertaintyBadge({ u }: { u: UncertaintyStatus }) {
  const s = STYLES[u.status];
  return (
    <div className={`mt-3 rounded-lg border p-3 ${s.chip}`}>
      <div className="flex items-center gap-2">
        <span className="text-xs uppercase tracking-wide font-semibold">{s.label}</span>
        {u.status === "extrapolating" && u.widen_factor > 1 && (
          <span className="text-[11px] opacity-80">interval widened {u.widen_factor.toFixed(2)}×</span>
        )}
      </div>
      <p className="text-[11px] mt-1 opacity-90 leading-snug">{BLURB[u.status]}</p>
      <p className="text-[11px] mt-1 opacity-70 leading-snug">{u.reason}</p>
    </div>
  );
}
