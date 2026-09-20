"use client";

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
  return (
    <div className="absolute bottom-20 inset-x-3 z-20 rounded-xl bg-ink/90 p-3 border border-white/10">
      <div className="flex justify-between text-xs uppercase tracking-wide text-mute mb-2">
        <span>Issue {issue || "—"}</span>
        <span>{horizon} weeks ahead</span>
      </div>
      <input
        type="range"
        min={0}
        max={Math.max(0, issues.length - 1)}
        value={idx}
        onChange={(e) => onIssue(issues[Number(e.target.value)] ?? issue)}
        className="w-full accent-drought"
      />
      <div className="flex justify-between mt-2 text-sm">
        <div className="flex gap-1">
          {(["2", "4", "8"] as const).map((h) => (
            <button
              key={h}
              onClick={() => onHorizon(h)}
              className={`px-2 py-0.5 rounded ${horizon === h ? "bg-paper text-ink" : "text-mute"}`}
            >
              {h}w
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          <button
            onClick={() => onLayer("drought")}
            className={`px-2 py-0.5 rounded ${layer === "drought" ? "bg-drought text-ink" : "text-mute"}`}
          >
            Drought
          </button>
          <button
            onClick={() => onLayer("fire")}
            className={`px-2 py-0.5 rounded ${layer === "fire" ? "bg-fire text-ink" : "text-mute"}`}
          >
            Fire condition
          </button>
        </div>
      </div>
    </div>
  );
}
