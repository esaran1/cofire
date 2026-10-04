"use client";

import { useMemo } from "react";
import type { MapCell } from "./MapView";
import { useT } from "@/lib/i18n";

/**
 * Every cell on the map as a list of buttons: the screen-reader and keyboard
 * equivalent of clicking the map, whose canvas cannot be read aloud. Ordered
 * by the layer's value, highest first, so the list answers the same question
 * the colours do.
 */
export function CellList({
  cells,
  layer,
  selectedId,
  onSelect,
}: {
  cells: MapCell[];
  layer: "drought" | "fire";
  selectedId?: string | null;
  onSelect: (c: MapCell) => void;
}) {
  const { t } = useT();
  const sorted = useMemo(() => [...cells].sort((a, b) => (b.value ?? -1) - (a.value ?? -1)), [cells]);
  if (cells.length === 0) return null;
  const describe = (v: number | null) => {
    if (v === null) return t("map.cellNone");
    if (layer === "fire") return t("map.cellFire", { v: v.toFixed(0) });
    return t("map.cellDrought", { v: v > 0 && v < 1 ? "<1" : v.toFixed(0) });
  };
  return (
    <details className="mx-6 mt-4 rounded border border-rule" data-testid="cell-list">
      <summary className="cursor-pointer px-3 py-2 text-sm text-ink-soft">
        {t("map.listTitle")} <span className="num">({cells.length})</span>
      </summary>
      <p className="px-3 text-[11px] leading-relaxed text-mute">
        {layer === "fire" ? t("map.listHintFire") : t("map.listHintDrought")}
      </p>
      <ul className="mt-1 max-h-72 overflow-y-auto border-t border-rule">
        {sorted.map((c) => {
          const on = c.id === selectedId;
          return (
            <li key={c.id} className="border-b border-rule/60 last:border-0">
              <button
                type="button"
                onClick={() => onSelect(c)}
                aria-current={on ? "true" : undefined}
                data-testid="cell-list-item"
                data-cell={c.id}
                className={`flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-xs hover:bg-paper-sunk ${on ? "bg-paper-sunk text-ink" : "text-ink-soft"}`}
              >
                <span>
                  {t("map.cell", { lat: c.lat.toFixed(3), lon: c.lon.toFixed(3) })}
                  {on ? <span className="sr-only">, {t("map.selected")}</span> : null}
                </span>
                <span className="num">{describe(c.value)}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </details>
  );
}
