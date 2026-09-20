"use client";

import { FormEvent, useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { API } from "@/lib/api";
import { deviceId } from "@/lib/device";

const TYPES = ["stock_tank_dry", "lawn_crispy", "creek_low", "soil_cracked", "vegetation_green"];

function ObserveInner() {
  const params = useSearchParams();
  const [lat, setLat] = useState(params.get("lat") ?? "40.54");
  const [lon, setLon] = useState(params.get("lon") ?? "-105.08");
  const [type, setType] = useState("lawn_crispy");
  const [note, setNote] = useState("");
  const [nudge, setNudge] = useState<string>("");
  const [rows, setRows] = useState<Array<Record<string, string | number>>>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/observations`)
      .then((r) => r.json())
      .then(setRows)
      .catch((e: Error) => setErr(e.message));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await fetch(`${API}/observations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_id: deviceId(),
        lat: Number(lat),
        lon: Number(lon),
        type,
        note,
      }),
    });
    const body = await res.json();
    setNudge(JSON.stringify(body.nudge, null, 2));
    const list = await fetch(`${API}/observations`).then((r) => r.json());
    setRows(list);
  }

  const weeks = rows.length;
  const rank = weeks >= 12 ? "Sentinel" : weeks >= 4 ? "Ranger" : weeks >= 1 ? "Scout" : "—";

  return (
    <div className="px-4 pt-6 max-w-xl mx-auto">
      <h1 className="text-3xl font-semibold">Observe</h1>
      <p className="text-mute mt-2">
        Ground reports enter the feature store as weekly counts by type. The nudge is a cached model
        delta, not an animation.
      </p>
      <p className="mt-2">
        Rank <span className="text-drought">{rank}</span> · {weeks} reports
      </p>
      {err && <p className="text-fire">{err}</p>}
      <form onSubmit={onSubmit} className="mt-4 space-y-3">
        <select className="w-full bg-white/10 rounded p-2" value={type} onChange={(e) => setType(e.target.value)}>
          {TYPES.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        <div className="grid grid-cols-2 gap-2">
          <input className="bg-white/10 rounded p-2" value={lat} onChange={(e) => setLat(e.target.value)} />
          <input className="bg-white/10 rounded p-2" value={lon} onChange={(e) => setLon(e.target.value)} />
        </div>
        <textarea className="w-full bg-white/10 rounded p-2" value={note} onChange={(e) => setNote(e.target.value)} />
        <button className="bg-drought text-ink font-medium px-4 py-2 rounded-lg">Submit report</button>
      </form>
      {nudge && (
        <pre className="mt-4 text-xs bg-white/5 p-3 rounded" data-testid="nudge">
          {nudge}
        </pre>
      )}
      <ul className="mt-6 text-sm text-mute space-y-1">
        {rows.map((r) => (
          <li key={String(r.id)}>
            {String(r.type)} · {String(r.lat)}, {String(r.lon)}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function ObservePage() {
  return (
    <Suspense>
      <ObserveInner />
    </Suspense>
  );
}
