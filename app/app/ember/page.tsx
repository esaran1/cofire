"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { API, Checklist, EmberItem, getParsed, postParsed } from "@/lib/api";
import { ChecklistSchema } from "@/lib/schemas";
import { deviceId } from "@/lib/device";
import { Action, ErrorNote, Numeral, OfflineNote, Panel, Segmented, Skeleton } from "@/components/ui/Controls";

const ZONES = [
  { value: "wui", label: "Wildland edge" },
  { value: "urban", label: "In town" },
];

const COST_LABEL: Record<string, string> = {
  free: "Free",
  under_100: "Under $100",
  over_100: "Over $100",
  contractor: "Contractor",
};

function Ring({ score }: { score: number }) {
  const reduce = useReducedMotion();
  const r = 52;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, score));
  return (
    <div className="relative h-32 w-32">
      <svg viewBox="0 0 128 128" className="h-32 w-32 -rotate-90">
        <circle cx="64" cy="64" r={r} fill="none" stroke="#d9d6cc" strokeWidth="10" />
        {/* Animates only when the score changes, never on a loop. */}
        <motion.circle
          cx="64"
          cy="64"
          r={r}
          fill="none"
          stroke="#b33a1a"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={c}
          initial={false}
          animate={{ strokeDashoffset: c * (1 - pct) }}
          transition={reduce ? { duration: 0 } : { duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <Numeral value={Math.round(pct * 100)} suffix="%" size="xl" />
        <span className="text-[10px] uppercase tracking-wide text-ink-soft">hardened</span>
      </div>
    </div>
  );
}

export default function EmberPage() {
  const [zone, setZone] = useState("wui");
  const [data, setData] = useState<Checklist | null>(null);
  const [state, setState] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback((z: string) => {
    setData(null);
    getParsed(`/ember/checklist?zone=${z}`, ChecklistSchema)
      .then((d) => {
        setData(d);
        setOffline(false);
      })
      .catch(() => setOffline(true));
  }, []);

  useEffect(() => {
    load(zone);
  }, [zone, load]);

  async function save(next: Record<string, boolean>) {
    setBusy(true);
    setErr(null);
    try {
      setData(await postParsed("/ember/state", { device_id: deviceId(), zone, state: next }, ChecklistSchema));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save that change.");
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: string) {
    const next = { ...state, [id]: !state[id] };
    setState(next);
    void save(next);
  }

  // The three highest-weight free actions, surfaced before the full list.
  const quickWins = useMemo(() => {
    if (!data) return [];
    return data.items
      .filter((i) => i.cost === "free" && !state[i.id])
      .sort((a, b) => b.item_weight - a.item_weight)
      .slice(0, 3);
  }, [data, state]);

  const groups = useMemo(() => {
    if (!data) return [];
    const by = new Map<string, { label: string; items: EmberItem[] }>();
    for (const it of data.items) {
      const g = by.get(it.group) ?? { label: it.group_label, items: [] };
      g.items.push(it);
      by.set(it.group, g);
    }
    return [...by.values()];
  }, [data]);

  return (
    <div className="mx-auto max-w-2xl px-6 pb-24 pt-12">
      <h1 className="display text-4xl">Ember Score</h1>
      <p className="mt-2 leading-relaxed text-ink-soft">
        A bad outlook you can act on. Each item is weighted by how much it reduces ember ignition
        risk, sourced from IBHS field research.
      </p>

      {offline && (
        <div className="mt-4">
          <OfflineNote />
        </div>
      )}
      {err && (
        <div className="mt-4">
          <ErrorNote message={err} onRetry={() => setErr(null)} />
        </div>
      )}

      <div className="mt-8">
        <Segmented label="Where is your property" options={ZONES} value={zone} onChange={setZone} />
      </div>

      <div className="mt-8 flex items-center gap-6">
        <Ring score={data?.score ?? 0} />
        <div className="flex-1">
          <p className="text-sm leading-relaxed text-ink-soft">
            {data
              ? `${data.items.filter((i) => state[i.id]).length} of ${data.items.length} actions done.`
              : "Loading your checklist."}
          </p>
          {busy && <p className="mt-1 text-xs text-ink-soft">Saving.</p>}
        </div>
      </div>

      {quickWins.length > 0 && (
        <>
          <h2 className="mt-10 text-lg font-medium">Start here, these cost nothing</h2>
          <div className="mt-3 space-y-2">
            {quickWins.map((i) => (
              <button
                key={i.id}
                onClick={() => toggle(i.id)}
                className="flex w-full items-start gap-3 rounded-lg border border-ember/30 bg-ember-soft p-3 text-left transition-transform active:scale-[0.99]"
              >
                <span className="mt-0.5 h-4 w-4 shrink-0 rounded border border-ember/60" />
                <span>
                  <span className="block text-sm text-ink">{i.label}</span>
                  <span className="mt-0.5 block text-xs leading-snug text-ink-soft">{i.rationale}</span>
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      <h2 className="mt-10 text-lg font-medium">Full checklist</h2>
      <div className="mt-3 space-y-6">
        {data === null ? (
          <Skeleton rows={6} />
        ) : (
          groups.map((g) => (
            <div key={g.label}>
              <h3 className="text-sm font-medium text-ink">{g.label}</h3>
              <ul className="mt-2 divide-y divide-rule rounded-lg border border-rule">
                {g.items.map((i) => {
                  const done = !!state[i.id];
                  return (
                    <li key={i.id}>
                      <button
                        onClick={() => toggle(i.id)}
                        className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-paper-sunk"
                      >
                        <span
                          className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] ${
                            done ? "border-ember bg-ember text-paper" : "border-rule"
                          }`}
                        >
                          {done ? "x" : ""}
                        </span>
                        <span className="flex-1">
                          <span className={`block text-sm ${done ? "text-mute line-through" : "text-paper"}`}>
                            {i.label}
                          </span>
                          <span className="mt-0.5 block text-xs leading-snug text-ink-soft">{i.rationale}</span>
                          <span className="mt-1 block text-xs text-mute">
                            {COST_LABEL[i.cost] ?? i.cost} · {i.source}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))
        )}
      </div>

      {data && (
        <div className="mt-10">
          <Action
            variant="quiet"
            onClick={() => {
              setState({});
              void save({});
            }}
          >
            Reset checklist
          </Action>
        </div>
      )}
    </div>
  );
}
