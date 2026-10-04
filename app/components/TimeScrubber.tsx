"use client";

import { useT } from "@/lib/i18n";

/**
 * Map controls. Floats over the map because it controls the map, but it is a
 * real surface on paper rather than a dark box, so it belongs to the page.
 */
export function TimeScrubber({
  issues,
  issue,
  horizon,
  layer,
  onIssue,
  onHorizon,
  onLayer,
  burden = false,
}: {
  issues: string[];
  issue: string;
  horizon: string;
  layer: "drought" | "fire" | "burden";
  onIssue: (v: string) => void;
  onHorizon: (v: string) => void;
  onLayer: (v: "drought" | "fire" | "burden") => void;
  /** Offer the EnviroScreen neighborhoods layer (Denver only). */
  burden?: boolean;
}) {
  const { t } = useT();
  const idx = Math.max(0, issues.indexOf(issue));
  const single = issues.length <= 1;

  return (
    <div data-testid="time-scrubber" className="absolute inset-x-4 bottom-4 z-20 rounded border border-rule bg-paper/95 p-4 shadow-[0_2px_16px_rgba(23,24,27,0.08)] backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1" role="group" aria-label={t("scrub.horizon")}>
          {(["2", "4", "8"] as const).map((h) => (
            <button
              key={h}
              onClick={() => onHorizon(h)}
              aria-pressed={horizon === h}
              className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
                horizon === h ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
              }`}
            >
              {t("scrub.weeks", { h })}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1" role="group" aria-label={t("scrub.layer")}>
          <button
            onClick={() => onLayer("fire")}
            aria-pressed={layer === "fire"}
            className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
              layer === "fire" ? "bg-ember text-paper" : "text-ink-soft hover:text-ink"
            }`}
          >
            {t("scrub.fire")}
          </button>
          <button
            onClick={() => onLayer("drought")}
            aria-pressed={layer === "drought"}
            className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
              layer === "drought" ? "bg-ochre text-paper" : "text-ink-soft hover:text-ink"
            }`}
          >
            {t("scrub.drought")}
          </button>
          {burden ? (
            <button
              onClick={() => onLayer("burden")}
              aria-pressed={layer === "burden"}
              data-testid="layer-burden"
              className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
                layer === "burden" ? "bg-[#3b2a78] text-paper" : "text-ink-soft hover:text-ink"
              }`}
            >
              {t("scrub.burden")}
            </button>
          ) : null}
        </div>
      </div>

      {!single && (
        <div className="mt-4">
          <label htmlFor="issue-scrub" className="flex items-baseline justify-between text-xs">
            <span className="text-mute">{t("scrub.issue")}</span>
            <span className="num text-ink">{issue || "n/a"}</span>
          </label>
          <input
            id="issue-scrub"
            type="range"
            min={0}
            max={Math.max(0, issues.length - 1)}
            value={idx}
            onChange={(e) => onIssue(issues[Number(e.target.value)] ?? issue)}
            className="mt-2 w-full accent-ember"
          />
        </div>
      )}
      {single && issue && (
        <p className="mt-3 text-xs text-mute">
          {t("scrub.issued")} <span className="num text-ink">{issue}</span>. {t("scrub.single")}
        </p>
      )}
    </div>
  );
}
