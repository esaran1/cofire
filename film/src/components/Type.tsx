/**
 * Kinetic type, used sparingly (four lines in the whole film), in the app's
 * display face. Words rise into place one after another; numbers are always
 * tabular figures.
 */
import { FONT, T } from "../theme";
import { clamp01, easeOut, ramp } from "../util";

export const Kinetic: React.FC<{ text: string; t: number; start: number; end: number; size?: number; color?: string; italic?: boolean; align?: "left" | "center"; stagger?: number }> = ({ text, t, start, end, size = 96, color = T.paper, italic = false, align = "center", stagger = 0.09 }) => {
  const words = text.split(" ");
  const out = 1 - ramp(t, end - 0.4, end);
  return (
    <div style={{ fontFamily: FONT.serif, fontWeight: 400, fontStyle: italic ? "italic" : "normal", fontSize: size, lineHeight: 1.08, color, textAlign: align, letterSpacing: "-0.01em", fontVariantNumeric: "tabular-nums", opacity: out }}>
      {words.map((w, i) => {
        const u = easeOut(clamp01((t - start - i * stagger) / 0.55));
        return (
          <span key={i} style={{ display: "inline-block", whiteSpace: "pre", transform: `translateY(${(1 - u) * size * 0.35}px)`, opacity: u, filter: `blur(${(1 - u) * 6}px)` }}>
            {w}{i < words.length - 1 ? " " : ""}
          </span>
        );
      })}
    </div>
  );
};

/** The small line naming where an outside fact comes from. */
export const SourceLine: React.FC<{ text: string; t: number; start: number; end: number; dark?: boolean }> = ({ text, t, start, end, dark = true }) => {
  const op = Math.min(ramp(t, start, start + 0.4), 1 - ramp(t, end - 0.4, end));
  return (
    <div style={{ position: "absolute", left: 64, bottom: 54, fontFamily: FONT.mono, fontSize: 25, color: dark ? "rgba(244,242,236,0.72)" : T.mute, opacity: op, letterSpacing: "0.01em" }}>
      {text}
    </div>
  );
};

/** A small label in the app's UI face. */
export const Label: React.FC<{ children: React.ReactNode; size?: number; color?: string; weight?: number; style?: React.CSSProperties }> = ({ children, size = 30, color = T.paper, weight = 400, style }) => (
  <div style={{ fontFamily: FONT.sans, fontSize: size, color, fontWeight: weight, fontVariantNumeric: "tabular-nums", ...style }}>{children}</div>
);
