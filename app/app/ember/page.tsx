"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { API, Checklist, EmberItem, getParsed, postParsed } from "@/lib/api";
import { ChecklistSchema } from "@/lib/schemas";
import { IS_STATIC, getDomains, localScore, staticChecklist } from "@/lib/data";
import { deviceId } from "@/lib/device";
import { useDomain } from "@/lib/domain";
import { Action, ErrorNote, Numeral, OfflineNote, Panel, Segmented, Skeleton } from "@/components/ui/Controls";

// "city" is the Urban Ember Score, written for Denver (cofire/ship/ember_city.yaml):
// water before restrictions, smoke readiness, not starting a fire. "wui" is the
// wildland-edge hardening checklist for the foothills and mountain watersheds.
const ZONES = [
  { value: "city", label: "In the city" },
  { value: "wui", label: "Wildland edge" },
];

const COPY: Record<string, { title: string; lede: string; ring: string }> = {
  city: {
    title: "Urban Ember Score",
    lede: "For Denver: save water before restrictions, get ready for smoke days, and do not start a fire.",
    ring: "ready",
  },
  wui: {
    title: "Ember Score",
    lede: "For homes at the wildland edge, weighted by how much each action cuts ember ignition risk.",
    ring: "hardened",
  },
};

const COST_LABEL: Record<string, string> = {
  free: "Free",
  under_100: "Under $100",
  over_100: "Over $100",
  contractor: "Contractor",
};

function Ring({ score, label }: { score: number; label: string }) {
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
        <span className="text-[10px] uppercase tracking-wide text-ink-soft">{label}</span>
      </div>
    </div>
  );
}

export default function EmberPage() {
  const [domain, , ready] = useDomain();
  const [zone, setZone] = useState("");
  const [data, setData] = useState<Checklist | null>(null);
  const [state, setState] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback((z: string) => {
    setData(null);
    const get = IS_STATIC
      ? staticChecklist<Checklist>(z).then((d) => ChecklistSchema.parse(d))
      : getParsed(`/ember/checklist?zone=${z}`, ChecklistSchema);
    get
      .then((d) => {
        if (IS_STATIC) {
          // The static site has no service to store ticks; keep them here.
          let saved: Record<string, boolean> = {};
          try {
            saved = JSON.parse(window.localStorage.getItem(`ember_${z}`) ?? "{}") as Record<string, boolean>;
          } catch {
            saved = {};
          }
          setState(saved);
          setData(localScore(d, saved));
        } else {
          setData(d);
        }
        setOffline(false);
      })
      .catch(() => setOffline(true));
  }, []);

  // Open on the checklist that fits the area: the city list for Denver, the
  // wildland-edge list for the watersheds and counties.
  useEffect(() => {
    if (!ready) return;
    getDomains()
      .then((d) => setZone(d.domains[domain]?.ember_zone ?? "wui"))
      .catch(() => setZone(domain === "denver" ? "city" : "wui"));
  }, [domain, ready]);

  useEffect(() => {
    if (zone) load(zone);
  }, [zone, load]);

  const copy = COPY[zone] ?? COPY.wui;

  async function save(next: Record<string, boolean>) {
    if (IS_STATIC) {
      try {
        window.localStorage.setItem(`ember_${zone}`, JSON.stringify(next));
      } catch {
        /* storage blocked: the score still updates for this visit */
      }
      if (data) setData(localScore(data, next));
      return;
    }
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

  // The full list excludes whatever is already surfaced above it. Printing the
  // same three actions twice made the page look longer than it is and made the
  // quick-wins block look like decoration rather than a shortcut.
  const groups = useMemo(() => {
    if (!data) return [];
    const surfaced = new Set(quickWins.map((q) => q.id));
    const by = new Map<string, { label: string; items: EmberItem[] }>();
    for (const it of data.items) {
      if (surfaced.has(it.id)) continue;
      const g = by.get(it.group) ?? { label: it.group_label, items: [] };
      g.items.push(it);
      by.set(it.group, g);
    }
    return [...by.values()];
  }, [data, quickWins]);

  return (
    <div className="reading px-6 pb-24 pt-12">
      <h1 className="display text-4xl" data-testid="ember-title">
        {copy.title}
      </h1>
      <p className="mt-2 leading-relaxed text-ink-soft">{copy.lede}</p>

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
        <Segmented label="Where do you live" options={ZONES} value={zone} onChange={setZone} />
      </div>

      <div className="mt-8 flex items-center gap-6">
        <Ring score={data?.score ?? 0} label={copy.ring} />
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
          <h2 className="mt-10 text-lg font-medium">Start here. These are free.</h2>
          <div className="mt-3 space-y-2">
            {quickWins.map((i) => (
              <button
                key={i.id}
                onClick={() => toggle(i.id)}
                className="flex w-full items-start gap-3 rounded-lg border border-ember/30 bg-ember-soft p-3 text-left transition-transform active:scale-[0.99]"
              >
                <span className="mt-0.5 h-4 w-4 shrink-0 rounded border border-ember/60" />
                <span>
                  <span className="block text-sm text-ink">{i.label.replace(/\u2013/g, " to ")}</span>
                  <span className="mt-0.5 block text-xs leading-snug text-ink-soft">{i.rationale}</span>
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      <h2 className="mt-10 text-lg font-medium">Everything else</h2>
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
                          <span className={`block text-sm ${done ? "text-mute line-through" : "text-ink"}`}>
                            {i.label.replace(/\u2013/g, " to ")}
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
