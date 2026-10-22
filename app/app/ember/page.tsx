"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { usePrefersReducedMotion } from "@/lib/motion";
import { API, Checklist, EmberItem, getParsed, postParsed } from "@/lib/api";
import { ChecklistSchema } from "@/lib/schemas";
import { IS_STATIC, getDomains, localScore, staticChecklist } from "@/lib/data";
import { deviceId } from "@/lib/device";
import { useDomain } from "@/lib/domain";
import { Action, ErrorNote, Numeral, OfflineNote, Panel, Skeleton } from "@/components/ui/Controls";
import { Segmented } from "@/components/ui/Animated";
import { type Lang, useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import emberEs from "@/lib/i18n/ember_es.json";
import { EMBER_LINKS, LINKS } from "@/lib/links";

// "city" is the Urban Ember Score, written for Denver (cofire/ship/ember_city.yaml):
// water before restrictions, smoke readiness, not starting a fire. "wui" is the
// wildland-edge hardening checklist for the foothills and mountain watersheds.
const ZONES: { value: string; label: MessageKey }[] = [
  { value: "city", label: "ember.zoneCity" },
  { value: "wui", label: "ember.zoneWui" },
];

const COST_LABEL: Record<string, MessageKey> = {
  free: "ember.cost.free",
  under_100: "ember.cost.under_100",
  over_100: "ember.cost.over_100",
  contractor: "ember.cost.contractor",
};

// The checklists' own text is English (the wildland-edge list is in the frozen
// model tree); the Spanish is kept beside the app, keyed by item and group id.
const ES = emberEs as { groups: Record<string, string>; items: Record<string, { label: string; rationale: string }> };

/** The checked program page behind an action, under its row. */
function ProgramLink({ id, lang, className }: { id: string; lang: Lang; className: string }) {
  const { t } = useT();
  const link = LINKS[EMBER_LINKS[id] ?? ""];
  if (!link) return null;
  return (
    <a href={link.url} target="_blank" rel="noopener noreferrer" className={`block text-xs text-ink-soft underline underline-offset-2 ${className}`} data-link={link.id}>
      {t("ember.more", { publisher: link[lang] })}
    </a>
  );
}

function itemText(i: EmberItem, lang: Lang): { label: string; rationale: string } {
  const es = lang === "es" ? ES.items[i.id] : undefined;
  return es ?? { label: i.label.replace(/\u2013/g, " to "), rationale: i.rationale };
}

function Ring({ score, label }: { score: number; label: string }) {
  const instant = usePrefersReducedMotion();
  const r = 52;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, score));
  return (
    <div className="relative h-32 w-32">
      <svg viewBox="0 0 128 128" className="h-32 w-32 -rotate-90">
        <circle cx="64" cy="64" r={r} fill="none" stroke="#d5d8cf" strokeWidth="10" />
        {/* Animates only when the score changes, never on a loop. */}
        <motion.circle
          cx="64"
          cy="64"
          r={r}
          fill="none"
          stroke="#245e50"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={c}
          initial={false}
          animate={{ strokeDashoffset: c * (1 - pct) }}
          transition={instant ? { duration: 0 } : { duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
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
  const { lang, t } = useT();
  const [domain, , ready] = useDomain();
  const [zone, setZone] = useState("");
  const [data, setData] = useState<Checklist | null>(null);
  const [state, setState] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback((z: string) => {
    setData(null);
    // The saved ticks come back with the checklist: from the service, or from
    // this browser in the static build. This used to fetch the bare checklist,
    // so every reload started from nothing although the ticks were saved.
    const get = IS_STATIC
      ? staticChecklist<Checklist>(z).then((d) => ChecklistSchema.parse(d))
      : getParsed(`/ember/score?device_id=${deviceId()}&zone=${z}`, ChecklistSchema);
    get
      .then((d) => {
        if (!IS_STATIC) {
          const done = new Set(d.done);
          setState((prev) => {
            const next = { ...prev };
            for (const it of d.items) next[it.id] = done.has(it.id);
            return next;
          });
        }
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

  const z = zone === "city" ? "city" : "wui";
  const copy = { title: t(`ember.${z}.title`), lede: t(`ember.${z}.lede`), ring: t(`ember.${z}.ring`) };

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
      setErr(e instanceof Error ? e.message : t("ember.saveFailed"));
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
      const g = by.get(it.group) ?? { label: (lang === "es" && ES.groups[it.group]) || it.group_label, items: [] };
      g.items.push(it);
      by.set(it.group, g);
    }
    return [...by.values()];
  }, [data, quickWins, lang]);

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
        <Segmented
          label={t("ember.where")}
          options={ZONES.map((o) => ({ value: o.value, label: t(o.label) }))}
          value={zone}
          onChange={setZone}
        />
      </div>

      <div className="mt-8 flex items-center gap-6">
        <Ring score={data?.score ?? 0} label={copy.ring} />
        <div className="flex-1">
          <p className="text-sm leading-relaxed text-ink-soft">
            {data
              ? t("ember.done", { n: data.items.filter((i) => state[i.id]).length, total: data.items.length })
              : t("ember.loading")}
          </p>
          {busy && <p className="mt-1 text-xs text-ink-soft">{t("ember.saving")}</p>}
        </div>
      </div>

      {quickWins.length > 0 && (
        <>
          <h2 className="mt-10 text-lg font-medium">{t("ember.start")}</h2>
          <div className="mt-3 space-y-2">
            {quickWins.map((i) => (
              <div key={i.id}>
              <button
                role="checkbox"
                aria-checked={!!state[i.id]}
                onClick={() => toggle(i.id)}
                className="flex w-full items-start gap-3 rounded border border-spruce/25 bg-spruce-soft p-3 text-left transition-transform active:scale-[0.99]"
              >
                <span
                  className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                    state[i.id] ? "border-spruce bg-spruce text-paper" : "border-spruce/60 bg-paper-raised"
                  }`}
                >
                  {state[i.id] ? <Check size={11} weight="bold" aria-hidden /> : null}
                </span>
                <span>
                  <span className={`block text-sm ${state[i.id] ? "text-mute line-through" : "text-ink"}`}>{itemText(i, lang).label}</span>
                  <span className="mt-0.5 block text-xs leading-snug text-ink-soft">{itemText(i, lang).rationale}</span>
                </span>
              </button>
              <ProgramLink id={i.id} lang={lang} className="mt-1 pl-10" />
              </div>
            ))}
          </div>
        </>
      )}

      <h2 className="mt-10 text-lg font-medium">{t("ember.rest")}</h2>
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
                        role="checkbox"
                        aria-checked={done}
                        onClick={() => toggle(i.id)}
                        className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-paper-sunk"
                      >
                        <span
                          className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                            done ? "border-spruce bg-spruce text-paper" : "border-rule"
                          }`}
                        >
                          {done ? <Check size={11} weight="bold" aria-hidden /> : null}
                        </span>
                        <span className="flex-1">
                          <span className={`block text-sm ${done ? "text-mute line-through" : "text-ink"}`}>
                            {itemText(i, lang).label}
                          </span>
                          <span className="mt-0.5 block text-xs leading-snug text-ink-soft">{itemText(i, lang).rationale}</span>
                          <span className="mt-1 block text-xs text-mute">
                            {COST_LABEL[i.cost] ? t(COST_LABEL[i.cost]) : i.cost} · <span lang="en">{i.source}</span>
                          </span>
                        </span>
                      </button>
                      <ProgramLink id={i.id} lang={lang} className="px-4 pb-3 pl-11" />
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
            {t("ember.reset")}
          </Action>
        </div>
      )}
    </div>
  );
}
