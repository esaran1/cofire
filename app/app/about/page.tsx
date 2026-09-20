"use client";

import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";

type Meta = {
  shipping_arm: string;
  resolution_m: number;
  resolution_note: string;
  disclaimer: string;
  manifest: { sources?: Array<{ name: string; state: string; note: string; optional?: boolean }> };
};

export default function AboutPage() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getJson<Meta>("/meta")
      .then(setMeta)
      .catch((e: Error) => setErr(e.message));
  }, []);

  return (
    <div className="px-4 pt-6 max-w-xl mx-auto pb-10">
      <h1 className="text-3xl font-semibold">About COFIRE</h1>
      <p className="mt-4 text-lg leading-relaxed">
        COFIRE forecasts drought and fire-spread conditions across Colorado 2 to 8 weeks ahead at
        grid-cell scale with calibrated uncertainty, and turns the forecast into three actions: predict
        (Beat the Model), observe (Observer Streaks), and harden (Ember Score).
      </p>
      <p className="mt-4 text-mute">{meta?.disclaimer}</p>
      {err && <p className="text-fire mt-2">{err}</p>}
      <h2 className="text-xl mt-8">Shipping model</h2>
      <p className="mt-1">
        {meta?.shipping_arm ?? "—"} — chosen by validation ERC-percentile MAE. See artifacts/metrics.md.
      </p>
      <h2 className="text-xl mt-8">Resolution</h2>
      <p className="mt-1">
        Displayed layer: {meta?.resolution_m ?? 4000} m. {meta?.resolution_note}
      </p>
      <h2 className="text-xl mt-8">Data sources</h2>
      <ul className="mt-2 space-y-2 text-sm">
        {(meta?.manifest.sources ?? []).length === 0 && <li className="text-mute">Run `make data` to fill MANIFEST.json.</li>}
        {(meta?.manifest.sources ?? []).map((s) => (
          <li key={s.name}>
            <span className="text-paper">{s.name}</span> · {s.state}
            {s.state === "source unavailable" ? " — source unavailable" : ""}
            <span className="text-mute"> {s.note}</span>
          </li>
        ))}
      </ul>
      <h2 className="text-xl mt-8">Prior art</h2>
      <p className="text-mute text-sm mt-1">
        A separate 2020–2025 science-fair project (Beyond the Forecast) is cited in docs/PRIOR_ART.md as
        precedent for a physics-informed ConvLSTM loss and an anti-leakage protocol. Nothing from it is
        copied. COFIRE&apos;s models are implemented from scratch on Colorado data, with a fuel-moisture
        constraint, conformal calibration, and this public app.
      </p>
      <h2 className="text-xl mt-8">AI usage</h2>
      <p className="text-mute text-sm mt-1">
        See AI_USAGE.md. Feature engineering, conformal calibration, model training, and the
        physics-informed ConvLSTM are marked for student rewrite.
      </p>
    </div>
  );
}
