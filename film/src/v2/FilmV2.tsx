/**
 * Film v2: the rules-complete, four-person cut (film/SCRIPT_V2 (1).md and
 * film/SLIDES_V2 (2).md, with the corrections in film/v2/CHANGES.md).
 *
 * The picture follows script/v2/timeline.json, which scripts/v2/build.mjs
 * lays out from the lines' recorded (or scratch) lengths, so every cut lands
 * on the voice. A beat is a new scene here, the tap trace (Trace.tsx), or a
 * run of short shots from the v1 film, time-remapped to fit the line and
 * reusing its captures, camera moves and cursor. Every number on screen comes
 * through field() (or clock() for the countdown), and the Guard checks every
 * frame.
 */
import { AbsoluteFill, Freeze, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import tl from "../../script/v2/timeline.json";
import tw from "../../../app/tailwind.config";
import { CapturePlane, cap } from "../components/Capture";
import { Film } from "../Film";
import { Guard } from "../Guard";
import { FONT, T } from "../theme";
import { clock, field, fill } from "../trace";
import { clamp01, easeOut, lerp, ramp } from "../util";
import { Trace } from "./Trace";

const C = (tw.theme?.extend?.colors ?? {}) as Record<string, string>;
const SPRUCE = C.spruce ?? "#245e50";
const SPRUCE_LIGHT = "#8cc2b2"; // spruce lifted for type and lines on the ink ground

type Shot = { a: number; at: number; len: number; rate: number; plate?: string };
type Beat = { id: string; section: string; start: number; end: number; scene?: string; who?: string; capture?: string; plates?: string[]; dir?: "back" | "forward"; shots?: Shot[] };
type Line = { id: string; speaker: string; beat: string; start: number; end: number; len: number; text_en: string };
const TL = tl as unknown as { duration: number; timer: { start: number; end: number }; beats: Beat[]; lines: Line[] };
export const V2_DURATION = TL.duration;

const line = (id: string) => TL.lines.find((l) => l.id === id);
const beat = (id: string) => TL.beats.find((b) => b.id === id)!;

/** Seconds from the start of the enclosing Sequence. */
function useSec(): number {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return f / fps;
}

/** Where a word starts in a line, as film time (by characters, which tracks speech closely enough to cut on). */
function wordTime(l: Line | undefined, needle: string, fallback: number): number {
  if (!l) return fallback;
  const text = l.text_en;
  const m = new RegExp(`\\b${needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`, "i").exec(text);
  return m ? l.start + (l.len * m.index) / text.length : fallback;
}

/** Cut points inside a beat: at most `max` seconds apart, each moved to the nearest word start. */
function cutsOn(b: Beat, max = 3.6): number[] {
  const span = b.end - b.start;
  const n = Math.max(1, Math.ceil(span / max));
  const words: number[] = [];
  for (const l of TL.lines.filter((x) => x.start >= b.start - 0.01 && x.start < b.end)) {
    let i = 0;
    for (const w of l.text_en.split(" ")) { words.push(l.start + (l.len * i) / l.text_en.length); i += w.length + 1; }
  }
  const cuts = [b.start];
  for (let i = 1; i < n; i++) {
    const target = b.start + (span * i) / n;
    const best = words.reduce((a, w) => (Math.abs(w - target) < Math.abs(a - target) ? w : a), target);
    cuts.push(Math.abs(best - target) < 0.8 ? best : target);
  }
  return cuts;
}

// ---------------------------------------------------------------------------
// A v1 shot, time-remapped: frame f of the shot shows v1 time a + f/fps * rate.
const V1Shot: React.FC<{ a: number; rate: number }> = ({ a, rate }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <Freeze frame={Math.round(f * rate)}>
      <Sequence from={-Math.round(a * fps)} name={`v1 from ${a}`}>
        <Film />
      </Sequence>
    </Freeze>
  );
};
const Shots: React.FC<{ b: Beat }> = ({ b }) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill>
      {(b.shots ?? []).map((s, i) => (
        <Sequence key={i} from={Math.round(s.at * fps)} durationInFrames={Math.max(1, Math.round(s.len * fps))} name={`shot ${i + 1}`}>
          {s.plate ? <PlateNow name={s.plate} len={s.len} /> : <V1Shot a={s.a} rate={s.rate} />}
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// The countdown: 3:00 minus film time, from the team intro to the end. It
// starts large in the clock beat and settles into its corner.
const Timer: React.FC = () => {
  const t = useSec();
  const { start, end } = TL.timer;
  if (t < start || t > end) return null;
  const left = Math.max(0, Math.floor(180 - t));
  const text = clock(`${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`);
  // The scripted glances: "This is COFIRE" (and P4's "We're fine", if it is in the cut).
  const g1 = line("team5"), g2 = line("glance");
  const glance = (l?: Line) => (l ? Math.min(ramp(t, l.start - 0.3, l.start + 0.15), 1 - ramp(t, l.end + 0.2, l.end + 0.7)) : 0);
  const k = Math.max(glance(g1), glance(g2));
  const cb = beat("clock");
  const big = cb ? Math.min(ramp(t, cb.start - 0.05, cb.start + 0.25), 1 - ramp(t, cb.end - 0.55, cb.end - 0.05)) : 0;
  // The pill's centre sits near (1760, 1006); the frame's centre is (960, 540).
  const s = 1 + 0.7 * k + 3.0 * big;
  const dx = -60 * k - 800 * big, dy = -40 * k - 466 * big;
  return (
    <div
      style={{
        position: "absolute", right: 48, bottom: 44, transformOrigin: "50% 50%",
        transform: `translate(${dx}px, ${dy}px) scale(${s})`, opacity: ramp(t, start, start + 0.3),
        display: "flex", alignItems: "center", gap: 12, padding: "10px 18px", borderRadius: 999,
        background: "rgba(250,250,246,0.94)", border: `1px solid ${T.rule}`, boxShadow: "0 2px 16px rgba(22,26,25,0.18)",
      }}
    >
      <span style={{ width: 10, height: 10, borderRadius: 999, background: k > 0.5 ? T.ember : SPRUCE }} />
      <span style={{ fontFamily: FONT.mono, fontSize: 30, color: T.ink, fontVariantNumeric: "tabular-nums" }}>{text}</span>
    </div>
  );
};

// ---------------------------------------------------------------------------
// An app capture filling the frame, with a slow push.
const Plate: React.FC<{ name: string; t: number; len: number }> = ({ name, t, len }) => {
  const s = cap(name);
  const vw = s.viewport.width;
  const w0 = Math.min(vw, 1920);
  const u = clamp01(t / Math.max(0.5, len));
  return <CapturePlane name={name} t={u} keys={[{ t: 0, view: { x: 0, y: 0, w: w0 } }, { t: 1, view: { x: w0 * 0.01, y: (w0 * 0.01 * 9) / 16, w: w0 * 0.98 } }]} box={{ w: 1920, h: 1080 }} />;
};
/** Plates cut on the voice, each 3.6 seconds or shorter. */
const Plates: React.FC<{ b: Beat; names: string[] }> = ({ b, names }) => {
  const { fps } = useVideoConfig();
  const cuts = cutsOn(b);
  return (
    <AbsoluteFill>
      {cuts.map((c, i) => {
        const end = cuts[i + 1] ?? b.end;
        return (
          <Sequence key={i} from={Math.round((c - b.start) * fps)} durationInFrames={Math.max(1, Math.round((end - c) * fps))}>
            <PlateNow name={names[i % names.length]} len={end - c} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
const PlateNow: React.FC<{ name: string; len: number }> = ({ name, len }) => <Plate name={name} t={useSec()} len={len} />;

// ---------------------------------------------------------------------------
// Lower thirds: name and title, in the app's type.
const Third: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec();
  const who = (b.who ?? "P1").toLowerCase();
  const k = easeOut(clamp01((t - 0.08) / 0.35));
  const k2 = easeOut(clamp01((t - 0.2) / 0.35));
  return (
    <AbsoluteFill>
      {b.plates ? <Plates b={b} names={b.plates} /> : <PlateNow name={b.capture ?? "denver"} len={b.end - b.start} />}
      <AbsoluteFill style={{ background: "linear-gradient(0deg, rgba(23,24,27,0.42) 0%, rgba(23,24,27,0) 42%)" }} />
      <div style={{ position: "absolute", left: 110, bottom: 120, display: "flex", alignItems: "stretch", opacity: k, transform: `translateX(${lerp(-40, 0, k)}px)`, boxShadow: "0 10px 40px rgba(22,26,25,0.28)" }}>
        <div style={{ width: 8, background: SPRUCE }} />
        <div style={{ background: T.paperRaised, padding: "24px 40px 26px 30px" }}>
          <div style={{ fontFamily: FONT.sans, fontSize: 60, fontWeight: 500, color: T.ink, lineHeight: 1.05, letterSpacing: "-0.01em" }}>{field(`name_${who}`)}</div>
          <div style={{ fontFamily: FONT.sans, fontSize: 34, color: T.mute, marginTop: 8, opacity: k2 }}>{field(`role_${who}`)}</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Wordmark: React.FC<{ size: number }> = ({ size }) => (
  <div style={{ fontFamily: FONT.serif, fontWeight: 300, fontSize: size, lineHeight: 1, color: T.paper, letterSpacing: "-0.02em" }}>
    CO<em style={{ color: T.emberBright, fontStyle: "italic" }}>FIRE</em>
  </div>
);

const Logo: React.FC = () => {
  const t = useSec();
  const k = easeOut(clamp01(t / 0.4));
  return (
    <AbsoluteFill style={{ background: T.ink, alignItems: "center", justifyContent: "center" }}>
      <AbsoluteFill style={{ background: `radial-gradient(900px 520px at 50% 50%, rgba(36,94,80,0.28), transparent 70%)` }} />
      <div style={{ transform: `scale(${lerp(1.12, 1, k)})`, opacity: k }}>
        <Wordmark size={250} />
      </div>
    </AbsoluteFill>
  );
};

/** The clock beat: the timer, large, while P1 says how long we have. */
const Clock: React.FC = () => (
  <AbsoluteFill style={{ background: T.ink }}>
    <AbsoluteFill style={{ background: `radial-gradient(900px 520px at 50% 50%, rgba(36,94,80,0.32), transparent 70%)` }} />
    <div style={{ position: "absolute", left: 0, right: 0, top: 210, display: "flex", justifyContent: "center" }}>
      <Wordmark size={84} />
    </div>
  </AbsoluteFill>
);

// ---------------------------------------------------------------------------
// The purpose, verbatim, over the app; then who it is for, with the purpose held above.
const PurposeText: React.FC<{ small: number }> = ({ small }) => {
  const text = line("purpose")?.text_en ?? "";
  return (
    <div style={{ position: "absolute", left: 0, right: 0, top: lerp(250, 96, small), padding: "0 180px", textAlign: "center" }}>
      <div style={{ fontFamily: FONT.sans, fontSize: 28, letterSpacing: "0.26em", textTransform: "uppercase", color: SPRUCE_LIGHT, opacity: 1 - small, height: lerp(56, 0, small) }}>What COFIRE does</div>
      <div style={{ fontFamily: FONT.serif, fontWeight: 400, fontSize: lerp(70, 42, small), lineHeight: 1.2, color: T.paper, textWrap: "balance" as never }}>{text}</div>
    </div>
  );
};
const Purpose: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec();
  const k = easeOut(clamp01((t - 0.05) / 0.5));
  return (
    <AbsoluteFill>
      <Plates b={b} names={b.plates ?? ["denver"]} />
      <AbsoluteFill style={{ background: "rgba(23,24,27,0.8)" }} />
      <div style={{ opacity: k, transform: `translateY(${lerp(16, 0, k)}px)` }}>
        <PurposeText small={0} />
      </div>
    </AbsoluteFill>
  );
};

const AUDIENCE = [
  { label: "Denver residents", word: "Denver" },
  { label: "In English and Spanish", word: "English" },
  { label: "Neighbors", word: "neighbors" },
  { label: "Community gardeners", word: "community" },
  { label: "Teachers", word: "teachers" },
  { label: "City staff", word: "city" },
];
const Audience: React.FC<{ b: Beat }> = ({ b }) => {
  const s = useSec();
  const t = s + b.start;
  const l = line("audience");
  const small = easeOut(clamp01(s / 0.5));
  return (
    <AbsoluteFill>
      <Plates b={b} names={b.plates ?? ["brief"]} />
      <AbsoluteFill style={{ background: "rgba(23,24,27,0.88)" }} />
      <PurposeText small={small} />
      <div style={{ position: "absolute", left: 180, right: 180, top: 470 }}>
        <div style={{ fontFamily: FONT.sans, fontSize: 30, letterSpacing: "0.26em", textTransform: "uppercase", color: SPRUCE_LIGHT, opacity: small }}>Who it's for</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 20, marginTop: 30 }}>
          {AUDIENCE.map((a) => {
            const at = wordTime(l, a.word, b.start + 0.5);
            const k = easeOut(clamp01((t - at + 0.1) / 0.3));
            return (
              <div key={a.label} style={{ opacity: k, transform: `translateY(${lerp(14, 0, k)}px)`, padding: "18px 34px", borderRadius: 999, background: T.paperRaised, border: `2px solid ${SPRUCE}`, fontFamily: FONT.sans, fontSize: 44, color: T.ink }}>
                {a.label}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Slides: ink ground, paper type, spruce for what is being said. Each slide
// holds still in one framing; its parts build with the voice.
type Framing = { at: number; scale: number; cx: number; cy: number };
/** A slide: held still, in one framing, while its parts build with the voice. */
const SlideFrame: React.FC<{ b: Beat; title: string; framings?: Framing[]; children: React.ReactNode }> = ({ title, children }) => (
  <AbsoluteFill style={{ background: T.ink, padding: "100px 140px" }}>
    <div style={{ fontFamily: FONT.serif, fontWeight: 300, fontSize: 84, color: T.paper, letterSpacing: "-0.015em" }}>{title}</div>
    <div style={{ position: "relative", flex: 1, marginTop: 50 }}>{children}</div>
  </AbsoluteFill>
);

const TOOLS = [
  { name: "Python", note: "Data pipeline and models", word: "Python" },
  { name: "pandas, xarray, SciPy, scikit-learn", note: "Analysis libraries", word: "models" },
  { name: "TypeScript, React, Next.js", note: "The app", word: "TypeScript" },
  { name: "MapLibre GL, PMTiles", note: "The map", word: "MapLibre" },
  { name: "GitHub Actions", note: "Weekly auto-update", word: "GitHub" },
  { name: "Postgres", note: "Predictions and reports", word: "refreshes" },
  { name: "Playwright", note: "Automated browser tests", word: "every week" },
];
const SlideTools: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec() + b.start;
  const l = line("slide1");
  const foot = wordTime(l, "We used", b.end - 3);
  return (
    <SlideFrame b={b} title="How it's built">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 22 }}>
        {TOOLS.map((x, i) => {
          const at = wordTime(l, x.word, b.start + 0.6 + i * 0.8);
          const appear = easeOut(clamp01((t - b.start - 0.1 - i * 0.07) / 0.35));
          const lit = ramp(t, at - 0.1, at + 0.2);
          return (
            <div key={x.name} style={{ opacity: appear * lerp(0.5, 1, lit), padding: "26px 28px", borderRadius: 2, border: `1.5px solid ${lit > 0.5 ? SPRUCE_LIGHT : "rgba(243,243,238,0.16)"}`, background: lit > 0.5 ? "rgba(36,94,80,0.32)" : "rgba(243,243,238,0.03)", minHeight: 150 }}>
              <div style={{ fontFamily: FONT.sans, fontSize: 36, color: T.paper, fontWeight: 500 }}>{x.name}</div>
              <div style={{ fontFamily: FONT.sans, fontSize: 27, color: "rgba(243,243,238,0.7)", marginTop: 10 }}>{x.note}</div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 0, bottom: 0, opacity: ramp(t, foot - 0.2, foot + 0.3), fontFamily: FONT.sans, fontSize: 32, color: "rgba(243,243,238,0.9)", lineHeight: 1.5 }}>
        Open-source libraries are listed in our repo.
        <br />
        AI-assisted development is disclosed in AI_USAGE.md.
      </div>
    </SlideFrame>
  );
};

const SOURCES = ["U.S. Drought Monitor", "gridMET fire danger", "Colorado EnviroScreen", "USGS watershed boundaries"];
const SlideData: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec() + b.start;
  const l = line("slide2");
  const gate = wordTime(l, "every download", b.start + 3);
  const counters = [
    { big: field("years_history"), label: "years of history", at: b.start + 0.2 },
    { big: field("n_areas"), label: "areas", at: b.start + 0.4 },
    { big: field("n_cells"), label: "map cells", at: wordTime(l, "map cells", b.start + 2) - 0.6 },
    { big: "", label: "Updated weekly", at: b.start + 0.8 },
  ];
  return (
    <SlideFrame b={b} title="Real data, checked every week">
      <div style={{ display: "flex", alignItems: "center", gap: 40 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14, width: 560 }}>
          {SOURCES.map((s, i) => (
            <div key={s} style={{ opacity: easeOut(clamp01((t - b.start - 0.1 - i * 0.12) / 0.3)), fontFamily: FONT.sans, fontSize: 36, color: T.paper, padding: "12px 22px", border: "1.5px solid rgba(243,243,238,0.2)", borderRadius: 2 }}>{s}</div>
          ))}
        </div>
        <svg width={170} height={60} style={{ overflow: "visible" }}>
          <path d={`M 0 30 L ${170 * ramp(t, b.start + 0.6, gate)} 30`} stroke={SPRUCE_LIGHT} strokeWidth={4} strokeDasharray="10 8" strokeDashoffset={-t * 60} />
        </svg>
        <div style={{ padding: "26px 30px", border: `2px solid ${t > gate ? SPRUCE_LIGHT : "rgba(243,243,238,0.25)"}`, background: t > gate ? "rgba(36,94,80,0.32)" : "transparent", borderRadius: 2, width: 470 }}>
          <div style={{ fontFamily: FONT.sans, fontSize: 38, color: T.paper, fontWeight: 500 }}>Checked download</div>
          <div style={{ fontFamily: FONT.sans, fontSize: 27, color: "rgba(243,243,238,0.75)", marginTop: 10, lineHeight: 1.4 }}>Host allowlist · error pages rejected · every file logged with its checksum</div>
        </div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, display: "flex", gap: 70 }}>
        {counters.map((c) => {
          const k = easeOut(clamp01((t - c.at) / 0.35));
          return (
            <div key={c.label} style={{ opacity: k, transform: `translateY(${lerp(12, 0, k)}px)` }}>
              {c.big ? <div style={{ fontFamily: FONT.serif, fontWeight: 300, fontSize: 96, color: T.paper, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>{c.big}</div> : <div style={{ height: 96 }} />}
              <div style={{ fontFamily: FONT.sans, fontSize: 32, color: "rgba(243,243,238,0.8)", marginTop: 8 }}>{c.label}</div>
            </div>
          );
        })}
      </div>
    </SlideFrame>
  );
};

const MODELS = ["Gradient boosting (LightGBM)", "Physics-informed neural network (ConvLSTM)", "Ensemble of the two"];
const SlideModels: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec() + b.start;
  const l = line("slide3");
  const win = wordTime(l, "The simplest", b.start + 3);
  return (
    <SlideFrame b={b} title="Simple beat complex">
      <div style={{ display: "flex", gap: 26 }}>
        {MODELS.map((m, i) => {
          const appear = easeOut(clamp01((t - b.start - 0.2 - i * 0.2) / 0.35));
          const gone = ramp(t, win - 0.5 + i * 0.3, win + i * 0.3);
          return (
            <div key={m} style={{ flex: 1, opacity: appear * (1 - gone), transform: `translateY(${lerp(0, 60, gone)}px)`, padding: "34px 30px", border: "1.5px solid rgba(243,243,238,0.2)", borderRadius: 2, fontFamily: FONT.sans, fontSize: 36, color: "rgba(243,243,238,0.85)" }}>
              {m}
            </div>
          );
        })}
      </div>
      {(() => {
        const k = easeOut(clamp01((t - win - 0.4) / 0.5));
        return (
          <div style={{ position: "absolute", left: 0, right: 0, top: 200, display: "flex", flexDirection: "column", alignItems: "center", opacity: k, transform: `translateY(${lerp(16, 0, k)}px)` }}>
            <div style={{ padding: "40px 60px", border: `2px solid ${SPRUCE_LIGHT}`, background: "rgba(36,94,80,0.3)", borderRadius: 2, fontFamily: FONT.serif, fontWeight: 300, fontSize: 66, color: T.paper }}>
              Weeks like this one → what happened next
            </div>
            <div style={{ marginTop: 30, fontFamily: FONT.sans, fontSize: 36, color: "rgba(243,243,238,0.82)" }}>{fill("Every similar week, {train_start} to {train_end}. Explainable. Hard to beat.")}</div>
          </div>
        );
      })()}
    </SlideFrame>
  );
};

const SlideTested: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec() + b.start;
  const l = line("slide4");
  const segs = [
    { label: "Train", years: fill("{train_start} to {train_end}"), w: 15 },
    { label: "Validate", years: fill("{val_start} to {val_end}"), w: 4.2 },
    { label: "Calibrate", years: fill("{cal_start} to {cal_end}"), w: 4.2 },
    { label: "Locked, every look counted", years: field("holdout"), w: 8, hold: true },
  ];
  const total = segs.reduce((a, s) => a + s.w, 0);
  const counted = wordTime(l, "and counted", b.start + 2);
  const badges = [
    { text: "Shuffled-data control", at: counted },
    { text: "Multiple-testing correction", at: counted + 0.5 },
    { text: fill("{n_survivors} of {n_tested} forecasts beat their baselines"), at: wordTime(l, "forecasts", b.end - 2) - 0.8 },
  ];
  return (
    <SlideFrame b={b} title="Tested before we trusted it">
      <div style={{ display: "flex", gap: 6, height: 96 }}>
        {segs.map((s, i) => {
          const fillK = ramp(t, b.start + 0.15 + i * 0.35, b.start + 0.55 + i * 0.35);
          const lock = s.hold ? ramp(t, wordTime(l, "locked", b.start + 1) - 0.1, wordTime(l, "locked", b.start + 1) + 0.3) : 1;
          return (
            <div key={s.label} style={{ flex: s.w / total, position: "relative" }}>
              <div style={{ height: "100%", background: s.hold ? "rgba(36,94,80,0.55)" : `rgba(243,243,238,${0.85 - i * 0.18})`, border: s.hold ? `2px solid ${SPRUCE_LIGHT}` : "none", transformOrigin: "0 50%", transform: `scaleX(${fillK})`, opacity: lock }} />
              <div style={{ marginTop: 16, opacity: fillK * lock, fontFamily: FONT.sans, fontSize: 30, color: s.hold ? SPRUCE_LIGHT : T.paper }}>{s.label}</div>
              <div style={{ marginTop: 4, opacity: fillK * lock, fontFamily: FONT.mono, fontSize: 26, color: "rgba(243,243,238,0.7)" }}>{s.years}</div>
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 18, marginTop: 170 }}>
        {badges.map((x) => {
          const k = easeOut(clamp01((t - x.at) / 0.3));
          return (
            <div key={x.text} style={{ opacity: k, transform: `translateY(${lerp(12, 0, k)}px)`, padding: "16px 28px", borderRadius: 999, border: `1.5px solid ${SPRUCE_LIGHT}`, fontFamily: FONT.sans, fontSize: 34, color: T.paper }}>
              {x.text}
            </div>
          );
        })}
      </div>
    </SlideFrame>
  );
};

// ---------------------------------------------------------------------------
// The turn: black, one line, no music.
const Turn: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec() + b.start;
  const l1 = line("turn1"), l2 = line("turn2");
  const a1 = (l1?.start ?? b.start + 0.6) - 0.05;
  const a2 = (l2?.start ?? b.start + 4) - 0.05;
  const one = Math.min(ramp(t, a1, a1 + 0.35), 1 - ramp(t, a2 - 0.25, a2));
  const two = ramp(t, a2, a2 + 0.35);
  const strike = ramp(t, wordTime(l2, "pulled", a2 + 2) - 0.05, wordTime(l2, "pulled", a2 + 2) + 0.45);
  const plain = wordTime(l2, "Now COFIRE", b.end - 3);
  // A slow push, so the stillness is held, not frozen.
  const push = 1 + 0.02 * clamp01((t - b.start) / Math.max(1, b.end - b.start));
  return (
    <AbsoluteFill style={{ background: "#000", alignItems: "center", justifyContent: "center", transform: `scale(${push})` }}>
      <div style={{ position: "absolute", opacity: one, fontFamily: FONT.serif, fontWeight: 300, fontSize: 96, color: T.paper, letterSpacing: "-0.01em" }}>One result looked perfect.</div>
      <div style={{ position: "absolute", opacity: two * (1 - ramp(t, plain - 0.2, plain + 0.15)), display: "flex", flexDirection: "column", alignItems: "center", gap: 46 }}>
        <span style={{ position: "relative", padding: "14px 34px", borderRadius: 999, border: `2px solid ${T.emberBright}`, fontFamily: FONT.sans, fontSize: 40, color: T.emberBright }}>
          forecast band
          <span style={{ position: "absolute", left: 16, right: 16, top: "50%", height: 3, background: T.emberBright, transformOrigin: "0 50%", transform: `scaleX(${strike})` }} />
        </span>
        <div style={{ fontFamily: FONT.serif, fontWeight: 300, fontSize: 86, color: T.paper }}>We found the flaw. We pulled it.</div>
      </div>
      <div style={{ position: "absolute", opacity: ramp(t, plain, plain + 0.35), fontFamily: FONT.serif, fontWeight: 300, fontSize: 72, color: T.paper, textAlign: "center", padding: "0 200px", textWrap: "balance" as never }}>
        COFIRE says plainly when it can't back up a number.
      </div>
    </AbsoluteFill>
  );
};

const Glance: React.FC = () => (
  <AbsoluteFill style={{ background: T.ink }}>
    <AbsoluteFill style={{ background: `radial-gradient(900px 520px at 70% 70%, rgba(36,94,80,0.3), transparent 70%)` }} />
  </AbsoluteFill>
);

// ---------------------------------------------------------------------------
const EndCard: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec();
  const k = easeOut(clamp01(t / 0.45));
  return (
    <AbsoluteFill style={{ background: T.ink, alignItems: "center", justifyContent: "center" }}>
      <div style={{ opacity: k, transform: `translateY(${lerp(14, 0, k)}px)`, textAlign: "center" }}>
        <Wordmark size={190} />
        <div style={{ fontFamily: FONT.serif, fontWeight: 300, fontSize: 46, color: "rgba(243,243,238,0.88)", marginTop: 24 }}>Plain-language odds for Denver, and for the water it depends on.</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, auto)", justifyContent: "center", columnGap: 64, marginTop: 70 }}>
          {["p1", "p2", "p3", "p4"].map((p, i) => {
            const kk = easeOut(clamp01((t - 0.25 - i * 0.12) / 0.35));
            return (
              <div key={p} style={{ opacity: kk, textAlign: "left" }}>
                <div style={{ fontFamily: FONT.sans, fontSize: 38, fontWeight: 500, color: T.paper }}>{field(`name_${p}`)}</div>
                <div style={{ fontFamily: FONT.sans, fontSize: 26, color: "rgba(243,243,238,0.72)", marginTop: 6 }}>{field(`role_${p}`)}</div>
              </div>
            );
          })}
        </div>
      </div>
      <div style={{ position: "absolute", bottom: 46, fontFamily: FONT.mono, fontSize: 22, color: "rgba(243,243,238,0.66)", opacity: ramp(t, 0.6, 1) }}>
        Data: U.S. Drought Monitor, gridMET. Sources: Denver Water. Map: OpenStreetMap contributors, Protomaps.
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
/** A slow push on scenes without their own camera, so no frame is ever still. */
const Drift: React.FC<{ b: Beat; children: React.ReactNode }> = ({ b, children }) => {
  const t = useSec();
  const u = clamp01(t / Math.max(0.1, b.end - b.start));
  const amount = 0.02;
  return <AbsoluteFill style={{ transform: `scale(${1 + amount * u})`, transformOrigin: "50% 45%" }}>{children}</AbsoluteFill>;
};

const TraceScene: React.FC<{ b: Beat; W: number; H: number }> = ({ b, W, H }) => {
  const t = useSec() + b.start;
  return <Trace b={b} t={t} W={W} H={H} L={line} />;
};

const Scene: React.FC<{ b: Beat }> = ({ b }) => {
  if (b.shots) return <Shots b={b} />;
  switch (b.scene) {
    case "Trace": return <TraceScene b={b} W={1920} H={1080} />;
    case "Third": return <Third b={b} />;
    case "Purpose": return <Purpose b={b} />;
    case "Audience": return <Audience b={b} />;
    case "SlideTools": return <SlideTools b={b} />;
    case "SlideData": return <SlideData b={b} />;
    case "SlideModels": return <SlideModels b={b} />;
    case "SlideTested": return <SlideTested b={b} />;
    case "Turn": return <Turn b={b} />;
    default: return <Drift b={b}><SceneBody b={b} /></Drift>;
  }
};

const SceneBody: React.FC<{ b: Beat }> = ({ b }) => {
  switch (b.scene) {
    case "Logo": return <Logo />;
    case "Clock": return <Clock />;
    case "Glance": return <Glance />;
    case "EndCard": return <EndCard b={b} />;
    default: throw new Error(`no v2 scene ${b.scene}`);
  }
};


const Beats: React.FC<{ until?: number }> = ({ until = Infinity }) => {
  const { fps } = useVideoConfig();
  return (
    <>
      {TL.beats.filter((b) => b.start < until).map((b) => (
        <Sequence key={b.id} from={Math.round(b.start * fps)} durationInFrames={Math.max(1, Math.round((b.end - b.start) * fps))} name={b.id}>
          <Scene b={b} />
        </Sequence>
      ))}
    </>
  );
};

export const FilmV2: React.FC<{ scratch?: boolean }> = () => (
  <Guard name="FilmV2">
    <AbsoluteFill style={{ background: T.ink }}>
      <Beats />
      <Timer />
    </AbsoluteFill>
  </Guard>
);

/** The vertical cut: the cold open and the team, for phones (45 s or less). */
export const V2_VERTICAL = Math.min(45, beat("clock").end);
export const VerticalV2: React.FC<{ scratch?: boolean }> = () => {
  const scale = 1080 / 1920;
  return (
    <Guard name="VerticalV2">
      <AbsoluteFill style={{ background: T.ink }}>
        <div style={{ position: "absolute", left: 0, top: (1920 - 1080 * scale) / 2, width: 1920, height: 1080, transform: `scale(${scale})`, transformOrigin: "0 0" }}>
          <AbsoluteFill>
            <Beats until={V2_VERTICAL} />
            <Timer />
          </AbsoluteFill>
        </div>
        <div style={{ position: "absolute", top: 260, left: 0, right: 0, textAlign: "center" }}>
          <Wordmark size={150} />
        </div>
        </AbsoluteFill>
    </Guard>
  );
};
