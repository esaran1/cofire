"use client";

import { WhyBar } from "@/lib/api";

export function WhyBars({ bars }: { bars: WhyBar[] }) {
  return (
    <div className="space-y-3" data-testid="why-panel">
      {bars.map((b) => {
        const w = Math.min(1, Math.abs(b.value));
        const color = b.sign === "pos" ? "#ff5a2a" : "#e6c15c";
        return (
          <div key={b.group}>
            <div className="flex justify-between text-sm">
              <span className="capitalize">{b.label}</span>
              <span className="text-mute">{b.value >= 0 ? "+" : ""}{b.value.toFixed(2)}</span>
            </div>
            <div className="h-1.5 bg-white/10 rounded-full mt-1">
              <div className="h-1.5 rounded-full" style={{ width: `${w * 100}%`, background: color }} />
            </div>
            <p className="text-mute text-sm mt-1 leading-snug">{b.text}</p>
          </div>
        );
      })}
    </div>
  );
}
