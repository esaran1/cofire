"use client";

import { useEffect, useState } from "react";
import { API, FiresPayload, HindcastSummary, getParsed } from "@/lib/api";
import { FiresPayloadSchema, HindcastSummarySchema } from "@/lib/schemas";

function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? "-" : v.toFixed(1);
}

export default function HindcastPage() {
  const [sum, setSum] = useState<HindcastSummary | null>(null);
  const [fp, setFp] = useState<FiresPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getParsed("/hindcast/summary", HindcastSummarySchema)
      .then(setSum)
      .catch((e: Error) => setErr(e.message));
    getParsed("/hindcast/fires", FiresPayloadSchema)
      .then(setFp)
      .catch(() => setFp(null));
  }, []);

  const h4 = (sum?.coverage_rows ?? []).filter((r) => r.horizon === 4);
  const nominal = sum?.nominal ?? 0.9;

  return (
    <div className="px-4 pt-6 max-w-xl mx-auto pb-10">
      <h1 className="display text-4xl font-normal">Hindcast 2026</h1>
      <p className="text-ink-soft mt-2">
        Replay of weekly issue dates. The overlay shows forecast fire-spread conditions, then 2026
        perimeters if any qualifying NIFC fires (&gt; {fp?.threshold_acres ?? 1000} acres) intersect the
        view. This is not a forecast of ignitions.
      </p>

      {sum?.contaminated && (
        <div className="mt-4 border border-ember/60 rounded-lg p-3 bg-ember/10">
          <p className="text-ember font-medium text-sm">
            Contaminated - look {sum.look_index} at a locked holdout
          </p>
          <p className="text-ink-soft text-sm mt-1">{sum.contamination_note}</p>
        </div>
      )}

      <a
        href="/?issue=2026-05-05&horizon=4"
        className="inline-block mt-4 bg-ochre text-ink px-4 py-2 rounded-lg font-medium"
      >
        Replay May 1 (issue 2026-05-05)
      </a>

      <h2 className="text-xl mt-8">Coverage: conformal vs bootstrap</h2>
      <p className="text-ink-soft text-sm mt-1">
        4-week ERC percentile, overall stratum. Target {nominal.toFixed(2)}.
      </p>
      {h4.length > 0 && (
        <table className="w-full text-sm mt-3">
          <thead>
            <tr className="text-ink-soft text-left">
              <th className="py-1">Split</th>
              <th>Method</th>
              <th>Coverage</th>
              <th>Mean width</th>
            </tr>
          </thead>
          <tbody>
            {h4.map((r) => {
              const miss = Math.abs(r.coverage - nominal) > 0.05;
              return (
                <tr key={`${r.split}-${r.method}`} className="border-t border-rule">
                  <td className="py-1">{r.split}</td>
                  <td>{r.method}</td>
                  <td className={miss ? "text-ember" : "text-paper"}>{r.coverage.toFixed(3)}</td>
                  <td className="text-ink-soft">{r.width.toFixed(1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      <p className="text-ink-soft text-sm mt-2">
        Conformal holds on the 2024-2025 calibration split and falls apart on the 2026 shift, with{" "}
        <em>narrower</em> intervals. The residual bootstrap holds. Reported, not retuned.
      </p>
      <img
        src={`${API}/hindcast/coverage.png`}
        alt="2026 coverage over weeks for conformal and bootstrap against the 0.90 line"
        className="mt-3 w-full rounded-lg bg-black"
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = "none";
        }}
      />
      {err && <p className="text-ember mt-2">{err}</p>}

      <h2 className="text-xl mt-8">Fires vs pre-discovery ranks</h2>
      {fp && fp.n_in_domain === 0 && (
        <div className="mt-2 border border-rule rounded-lg p-3">
          <p className="text-paper text-sm font-medium">
            {fp.fires.length} qualifying 2026 perimeters, 0 inside the current domain.
          </p>
          <p className="text-ink-soft text-sm mt-1">{fp.note}</p>
        </div>
      )}
      {fp?.control?.mean_pct_rank && (
        <p className="text-ink-soft text-sm mt-2">
          Control ({fp.control.n ?? 200} random non-fire cells, same issue dates): mean percentile rank
          h2 {pct(fp.control.mean_pct_rank.h2)}, h4 {pct(fp.control.mean_pct_rank.h4)}, h8{" "}
          {pct(fp.control.mean_pct_rank.h8)}. Fire ranks near these values are unremarkable.
        </p>
      )}
      <table className="w-full text-sm mt-3">
        <thead>
          <tr className="text-ink-soft text-left">
            <th className="py-1">Fire</th>
            <th>Discovery</th>
            <th>2w</th>
            <th>4w</th>
            <th>8w</th>
          </tr>
        </thead>
        <tbody>
          {(!fp || fp.fires.length === 0) && (
            <tr>
              <td colSpan={5} className="py-3 text-mute">
                No qualifying 2026 perimeters. Run `make hindcast`.
              </td>
            </tr>
          )}
          {(fp?.fires ?? []).map((f) => (
            <tr key={`${f.name}-${f.discovery}`} className="border-t border-rule">
              <td className="py-1">
                {f.name}
                {!f.in_domain && (
                  <span className="text-ink-soft" title="nearest-cell only">
                    {" "}
                    ·&nbsp;out
                  </span>
                )}
              </td>
              <td className="text-ink-soft">{f.discovery}</td>
              <td>{pct(f.h2_pct_rank)}</td>
              <td>{pct(f.h4_pct_rank)}</td>
              <td>{pct(f.h8_pct_rank)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className="text-xl mt-8">Full comparison</h2>
      <pre className="mt-2 text-xs text-mute whitespace-pre-wrap">{(sum?.comparison ?? "").slice(0, 2500)}</pre>
    </div>
  );
}
