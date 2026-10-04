"use client";

import { useMemo } from "react";
import { useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import { LINKS } from "@/lib/links";
import type { TractFeature, Tracts } from "@/lib/tracts";

const ROWS: { key: "score" | "heat" | "pm25" | "asthma"; label: MessageKey }[] = [
  { key: "score", label: "tract.score" },
  { key: "heat", label: "tract.heat" },
  { key: "pm25", label: "tract.pm25" },
  { key: "asthma", label: "tract.asthma" },
];

/** One tract's EnviroScreen percentiles, labelled as context. */
export function TractCard({ tract }: { tract: TractFeature | null }) {
  const { lang, t } = useT();
  return (
    <section className="mx-6 mt-4 rounded border border-[#3b2a78]/30 bg-paper p-4" data-testid="tract-card">
      {tract ? (
        <>
          <h2 className="text-base font-semibold">{t("tract.title", { geoid: tract.properties.geoid })}</h2>
          <p className="text-xs text-mute">
            {tract.properties.pop ? t("tract.pop", { n: tract.properties.pop.toLocaleString(lang === "es" ? "es-US" : "en-US") }) : t("tract.noPop")}
          </p>
          <dl className="mt-2 text-sm">
            {ROWS.map((r) => (
              <div key={r.key} className="flex items-baseline justify-between border-b border-rule py-1.5 last:border-0" data-row={r.key}>
                <dt>{t(r.label)}</dt>
                <dd className="num">{tract.properties[r.key]?.toFixed(0) ?? ""}</dd>
              </div>
            ))}
          </dl>
        </>
      ) : (
        <p className="text-sm text-ink-soft">{t("tract.pick")}</p>
      )}
      <p className="mt-2 text-[11px] leading-relaxed text-mute">
        {t("tract.context")}{" "}
        <a href={LINKS.enviroscreen.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2" data-link="enviroscreen">
          {LINKS.enviroscreen[lang]}
        </a>
      </p>
    </section>
  );
}

/** Every tract as a button, most burdened first: the accessible equivalent of clicking the map. */
export function TractList({ tracts, selected, onSelect }: { tracts: Tracts; selected: string | null; onSelect: (f: TractFeature) => void }) {
  const { t } = useT();
  const sorted = useMemo(() => [...tracts.features].sort((a, b) => (b.properties.score ?? -1) - (a.properties.score ?? -1)), [tracts]);
  return (
    <details className="mx-6 mt-4 rounded border border-rule" data-testid="tract-list">
      <summary className="cursor-pointer px-3 py-2 text-sm text-ink-soft">
        {t("tract.list")} <span className="num">({sorted.length})</span>
      </summary>
      <p className="px-3 text-[11px] leading-relaxed text-mute">{t("tract.listHint")}</p>
      <ul className="mt-1 max-h-72 overflow-y-auto border-t border-rule">
        {sorted.map((f) => {
          const on = f.properties.geoid === selected;
          return (
            <li key={f.properties.geoid} className="border-b border-rule/60 last:border-0">
              <button
                type="button"
                onClick={() => onSelect(f)}
                aria-current={on ? "true" : undefined}
                data-testid="tract-list-item"
                data-geoid={f.properties.geoid}
                className={`flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-xs hover:bg-paper-sunk ${on ? "bg-paper-sunk text-ink" : "text-ink-soft"}`}
              >
                <span>{t("tract.item", { geoid: f.properties.geoid })}</span>
                <span className="num">{t("tract.itemScore", { v: f.properties.score?.toFixed(0) ?? "" })}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </details>
  );
}
