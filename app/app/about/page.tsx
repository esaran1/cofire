"use client";

import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";

type Meta = {
  shipping_arm: string;
  shipping_arm_basis: string;
  resolution_m: number;
  resolution_note: string;
  disclaimer: string;
  manifest: { sources?: Array<{ name: string; state: string; note: string; optional?: boolean }> };
  manifest_hash: string | null;
  git_sha: string | null;
  status: string;
  hindcast_looks: Array<{ config_hash: string; look_index: number; timestamp: string }>;
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
        COFIRE forecasts drought and fire-spread conditions across Colorado 2 to 8 weeks ahead,
        states how uncertain each forecast is, says when that uncertainty itself cannot be trusted,
        and turns the result into a decision: predict (Beat the Model), observe (Observer Streaks),
        and harden (Ember Score).
      </p>
      <p className="mt-4 text-mute">{meta?.disclaimer}</p>
      {err && <p className="text-fire mt-2">{err}</p>}
      <h2 className="text-xl mt-8">Shipping model</h2>
      <p className="mt-1">
        <span className="text-paper font-medium">{meta?.shipping_arm ?? "-"}</span> - {meta?.shipping_arm_basis ?? "chosen on validation"}.
      </p>
      {meta?.status && (
        <p className="mt-2 text-sm">
          Build status:{" "}
          <span className={meta.status === "No-go" ? "text-fire font-medium" : "text-paper font-medium"}>
            {meta.status}
          </span>
          {meta.status === "No-go" && (
            <span className="text-mute">
              {" "}- on this domain and record, no trained arm improves on a persistence baseline at
              4 or 8 weeks. That negative result is reported in artifacts/metrics.md rather than
              hidden. Statewide is not started. See STATUS.md.
            </span>
          )}
        </p>
      )}
      {(meta?.hindcast_looks ?? []).length > 0 && (
        <p className="mt-2 text-sm text-mute">
          Locked 2026 holdout: {meta!.hindcast_looks.length} look
          {meta!.hindcast_looks.length === 1 ? "" : "s"} at config{" "}
          <code className="text-xs">{meta!.hindcast_looks[meta!.hindcast_looks.length - 1].config_hash}</code>
          {meta!.hindcast_looks.length > 1 && " - repeat looks are reported as contaminated"}.
        </p>
      )}

      <h2 className="text-xl mt-8">Provenance</h2>
      <dl className="mt-1 text-sm space-y-1">
        <div>
          <dt className="text-mute inline">Git commit: </dt>
          <dd className="inline"><code className="text-xs break-all">{meta?.git_sha ?? "-"}</code></dd>
        </div>
        <div>
          <dt className="text-mute inline">MANIFEST hash: </dt>
          <dd className="inline"><code className="text-xs break-all">{meta?.manifest_hash ?? "-"}</code></dd>
        </div>
      </dl>
      <p className="text-mute text-xs mt-1">
        The MANIFEST hash covers the input data sources. Metrics on this build were produced from
        exactly these inputs at exactly this commit.
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
            {s.state === "source unavailable" ? " - source unavailable" : ""}
            <span className="text-mute"> {s.note}</span>
          </li>
        ))}
      </ul>
      <h2 className="text-xl mt-8">Why the intervals are hidden</h2>
      <p className="text-mute text-sm mt-1 leading-relaxed">
        Every year held out of training carries the same ~2.4x inflation in forecast error: the
        years the model trained on sit at a 90th-percentile error of 20 to 26 ERC points, while
        held-out 2023, 2024 and 2025 all sit at 59 to 63. A three-part leakage audit ruled out
        contamination. Because that inflation is constant across the pool years, no reweighting of
        those years can recover it, which is why all six pre-registered calibration variants
        returned no improvement at all. COFIRE therefore suppresses the interval rather than drawing
        one the record cannot back.
      </p>

      <h2 className="text-xl mt-8">Prior art</h2>
      <p className="text-mute text-sm mt-1">
        A separate 2020-2025 science-fair project (Beyond the Forecast) is cited in docs/PRIOR_ART.md as
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
