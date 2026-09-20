"use client";

import { useEffect, useState } from "react";
import { API } from "@/lib/api";
import { deviceId } from "@/lib/device";

type Item = {
  id: string;
  label: string;
  cost: string;
  group_label: string;
  item_weight: number;
  rationale: string;
  source: string;
};

type Payload = {
  score: number;
  items: Item[];
  top_free: Item[];
  done: string[];
};

export default function EmberPage() {
  const [zone, setZone] = useState<"urban" | "wui">("wui");
  const [data, setData] = useState<Payload | null>(null);
  const [state, setState] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState<string | null>(null);

  async function load(z: "urban" | "wui", st: Record<string, boolean>) {
    const res = await fetch(`${API}/ember/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId(), zone: z, state: st }),
    });
    if (!res.ok) {
      setErr(`ember ${res.status}`);
      return;
    }
    setData(await res.json());
  }

  useEffect(() => {
    fetch(`${API}/ember/checklist?zone=${zone}`)
      .then((r) => r.json())
      .then(setData)
      .catch((e: Error) => setErr(e.message));
  }, [zone]);

  function toggle(id: string) {
    const next = { ...state, [id]: !state[id] };
    setState(next);
    load(zone, next);
  }

  const score = data?.score ?? 0;
  const groups = new Map<string, Item[]>();
  for (const it of data?.items ?? []) {
    const arr = groups.get(it.group_label) ?? [];
    arr.push(it);
    groups.set(it.group_label, arr);
  }

  return (
    <div className="px-4 pt-6 max-w-xl mx-auto pb-8">
      <h1 className="text-3xl font-semibold">Ember Score</h1>
      <p className="text-mute mt-2">
        Hardening checklist. The score is weighted completion. It is not a forecast of whether a fire
        will reach this house.
      </p>
      {err && <p className="text-fire">{err}</p>}
      <div className="flex gap-2 mt-4">
        {(["urban", "wui"] as const).map((z) => (
          <button
            key={z}
            onClick={() => setZone(z)}
            className={`px-3 py-1 rounded-full ${zone === z ? "bg-paper text-ink" : "bg-white/10"}`}
          >
            {z}
          </button>
        ))}
      </div>
      <div className="mt-6 flex items-center gap-4">
        <div
          className="h-24 w-24 rounded-full grid place-items-center border-4 border-fire text-2xl"
          data-testid="ember-score"
        >
          {Math.round(score * 100)}
        </div>
        <div>
          <p className="text-sm uppercase text-mute">three free things this weekend</p>
          <ul className="text-sm mt-1">
            {(data?.top_free ?? []).map((t) => (
              <li key={t.id}>· {t.label}</li>
            ))}
          </ul>
        </div>
      </div>
      {Array.from(groups.entries()).map(([label, items]) => (
        <section key={label} className="mt-6">
          <h2 className="text-lg">{label}</h2>
          <ul className="mt-2 space-y-2">
            {items.map((it) => (
              <li key={it.id} className="flex gap-2 items-start">
                <input type="checkbox" checked={!!state[it.id]} onChange={() => toggle(it.id)} />
                <div>
                  <p>
                    {it.label}{" "}
                    <span className="text-mute text-xs">{it.cost.replace("_", " ")}</span>
                  </p>
                  <p className="text-mute text-sm">{it.rationale}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
