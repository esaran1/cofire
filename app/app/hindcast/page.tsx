"use client";

import { useEffect, useState } from "react";
import { API, getJson } from "@/lib/api";

export default function HindcastPage() {
  const [md, setMd] = useState("");
  const [fires, setFires] = useState<Array<Record<string, unknown>>>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getJson<{ comparison: string }>("/hindcast/summary")
      .then((d) => setMd(d.comparison || "Run `make calibrate` to write the 2026 coverage comparison."))
      .catch((e: Error) => setErr(e.message));
    getJson<Array<Record<string, unknown>>>("/hindcast/fires")
      .then(setFires)
      .catch(() => setFires([]));
  }, []);

  return (
    <div className="px-4 pt-6 max-w-xl mx-auto">
      <h1 className="text-3xl font-semibold">Hindcast 2026</h1>
      <p className="text-mute mt-2">
        Replay of weekly issue dates. Overlay shows forecast fire-spread conditions, then June perimeters
        if any qualifying NIFC fires (&gt; 1,000 acres) intersect the view. This is not a forecast of ignitions.
      </p>
      <a
        href="/?issue=2026-05-05&horizon=4"
        className="inline-block mt-4 bg-drought text-ink px-4 py-2 rounded-lg font-medium"
      >
        Replay May 1 (issue 2026-05-05)
      </a>
      <h2 className="text-xl mt-8">Coverage: conformal vs bootstrap</h2>
      <img
        src={`${API}/hindcast/coverage.png`}
        alt="2026 coverage over weeks for conformal and bootstrap against the 0.90 line"
        className="mt-3 w-full rounded-lg bg-black"
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = "none";
        }}
      />
      {err && <p className="text-fire mt-2">{err}</p>}
      <pre className="mt-4 text-xs text-mute whitespace-pre-wrap">{md.slice(0, 2500)}</pre>
      <h2 className="text-xl mt-8">Fires vs pre-discovery ranks</h2>
      <table className="w-full text-sm mt-2">
        <thead>
          <tr className="text-mute text-left">
            <th>Fire</th>
            <th>4w rank</th>
            <th>8w rank</th>
          </tr>
        </thead>
        <tbody>
          {fires.length === 0 && (
            <tr>
              <td colSpan={3} className="py-3 text-mute">
                No qualifying 2026 perimeters in the current domain.
              </td>
            </tr>
          )}
          {fires.map((f) => (
            <tr key={String(f.name)}>
              <td className="py-1">{String(f.name)}</td>
              <td>{String(f.h4_pct_rank ?? "—")}</td>
              <td>{String(f.h8_pct_rank ?? "—")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
