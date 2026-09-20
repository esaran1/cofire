"use client";

import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { API } from "@/lib/api";
import { deviceId } from "@/lib/device";
import { Suspense } from "react";

function BeatInner() {
  const params = useSearchParams();
  const [cell, setCell] = useState(params.get("cell") ?? "40.5417_-105.0833");
  const [cat, setCat] = useState(2);
  const [band, setBand] = useState("high");
  const [locked, setLocked] = useState<string>("");
  const [mine, setMine] = useState<Array<Record<string, string | number>>>([]);
  const [board, setBoard] = useState<Array<{ device_id: string; picks: number }>>([]);
  const [err, setErr] = useState<string | null>(null);

  function refresh() {
    const id = deviceId();
    fetch(`${API}/predictions/me?device_id=${id}`)
      .then((r) => r.json())
      .then(setMine)
      .catch((e: Error) => setErr(e.message));
    fetch(`${API}/leaderboard`)
      .then((r) => r.json())
      .then(setBoard)
      .catch(() => undefined);
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await fetch(`${API}/predictions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_id: deviceId(),
        cell_id: cell,
        horizon: 4,
        drought_category: cat,
        fire_band: band,
      }),
    });
    const body = await res.json();
    setLocked(JSON.stringify(body.locked_model ?? {}, null, 2));
    refresh();
  }

  return (
    <div className="px-4 pt-6 max-w-xl mx-auto">
      <h1 className="text-3xl font-semibold">Beat the Model</h1>
      <p className="text-mute mt-2">
        Lock a drought category and a fire-spread condition band for this week. The model&apos;s number is
        revealed after you submit. Scoring uses realized USDM and ERC once those weeks exist.
      </p>
      {err && <p className="text-fire mt-2">{err}</p>}
      <form onSubmit={onSubmit} className="mt-6 space-y-3">
        <label className="block text-sm">
          Cell
          <input className="w-full bg-white/10 rounded p-2 mt-1" value={cell} onChange={(e) => setCell(e.target.value)} />
        </label>
        <label className="block text-sm">
          Drought 0–4
          <input
            type="number"
            min={0}
            max={4}
            className="w-full bg-white/10 rounded p-2 mt-1"
            value={cat}
            onChange={(e) => setCat(Number(e.target.value))}
          />
        </label>
        <label className="block text-sm">
          Fire-spread band
          <select className="w-full bg-white/10 rounded p-2 mt-1" value={band} onChange={(e) => setBand(e.target.value)}>
            <option value="low">low</option>
            <option value="moderate">moderate</option>
            <option value="high">high</option>
            <option value="very_high">very high</option>
          </select>
        </label>
        <button className="bg-fire text-ink font-medium px-4 py-2 rounded-lg">Submit pick</button>
      </form>
      {locked && (
        <pre className="mt-4 text-xs bg-white/5 p-3 rounded" data-testid="locked-model">
          {locked}
        </pre>
      )}
      <h2 className="text-xl mt-8">Your picks · streak {mine.length}</h2>
      <ul className="text-sm text-mute mt-2 space-y-1">
        {mine.map((p) => (
          <li key={String(p.id)}>
            {String(p.issue)} h{String(p.horizon)} cat {String(p.drought_category)} / {String(p.fire_band)}
          </li>
        ))}
      </ul>
      <h2 className="text-xl mt-8">County board</h2>
      <ul className="text-sm mt-2">
        {board.map((b) => (
          <li key={b.device_id}>
            {b.device_id} · {b.picks}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function BeatPage() {
  return (
    <Suspense>
      <BeatInner />
    </Suspense>
  );
}
