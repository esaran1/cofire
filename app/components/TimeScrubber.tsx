"use client";

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
}: {
  issues: string[];
  issue: string;
  horizon: string;
  layer: "drought" | "fire";
  onIssue: (v: string) => void;
  onHorizon: (v: string) => void;
  onLayer: (v: "drought" | "fire") => void;
}) {
  const idx = Math.max(0, issues.indexOf(issue));
  const single = issues.length <= 1;

  return (
    <div data-testid="time-scrubber" className="absolute inset-x-4 bottom-4 z-20 rounded border border-rule bg-paper/95 p-4 shadow-[0_2px_16px_rgba(23,24,27,0.08)] backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1" role="group" aria-label="Forecast horizon">
          {(["2", "4", "8"] as const).map((h) => (
            <button
              key={h}
              onClick={() => onHorizon(h)}
              aria-pressed={horizon === h}
              className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
                horizon === h ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
              }`}
            >
              {h} weeks
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1" role="group" aria-label="Layer">
          <button
            onClick={() => onLayer("fire")}
            aria-pressed={layer === "fire"}
            className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
              layer === "fire" ? "bg-ember text-paper" : "text-ink-soft hover:text-ink"
            }`}
          >
            Fire-spread
          </button>
          <button
            onClick={() => onLayer("drought")}
            aria-pressed={layer === "drought"}
            className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
              layer === "drought" ? "bg-ochre text-paper" : "text-ink-soft hover:text-ink"
            }`}
          >
            Drought
          </button>
        </div>
      </div>

      {!single && (
        <div className="mt-4">
          <label htmlFor="issue-scrub" className="flex items-baseline justify-between text-xs">
            <span className="text-mute">Issue date</span>
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
          Issued <span className="num text-ink">{issue}</span>. This build ships a single issue date.
        </p>
      )}
    </div>
  );
}
