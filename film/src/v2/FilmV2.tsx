/**
 * Film v2: the rules-complete, four-person cut (film/SCRIPT_V2.md).
 *
 * The picture follows script/v2/timeline.json, which scripts/v2/build.mjs
 * lays out from the lines' recorded (or scratch) lengths. A beat is either a
 * new scene here or a window of the v1 film, which reuses its captures, camera
 * moves and cursor exactly. Every number on screen comes through field() (or
 * clock() for the countdown), and the Guard checks every frame.
 */
import { AbsoluteFill, Freeze, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import tl from "../../script/v2/timeline.json";
import tw from "../../../app/tailwind.config";
import { DATA } from "../data";
import { Film } from "../Film";
import { Guard } from "../Guard";
import { FONT, T } from "../theme";
import { clock, field, fill } from "../trace";
import { clamp01, easeOut, lerp, ramp } from "../util";

const C = (tw.theme?.extend?.colors ?? {}) as Record<string, string>;
const SPRUCE = C.spruce ?? "#245e50";
const SPRUCE_LIGHT = "#8cc2b2"; // spruce lifted for type and lines on the ink ground

type Beat = { id: string; section: string; start: number; end: number; scene?: string; who?: string; v1?: [number, number] };
type Line = { id: string; speaker: string; beat: string; start: number; end: number; len: number; text_en: string };
const TL = tl as unknown as { duration: number; timer: { start: number; end: number }; beats: Beat[]; lines: Line[] };
export const V2_DURATION = TL.duration;

const line = (id: string) => TL.lines.find((l) => l.id === id);
const beat = (id: string) => TL.beats.find((b) => b.id === id)!;

/** Film time, in seconds, from the start of the enclosing Sequence. */
function useSec(): number {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return f / fps;
}

/** Where a word sits in a line, as film time: for building a slide with the voice. */
function wordTime(l: Line | undefined, needle: string, fallback: number): number {
  if (!l) return fallback;
  const w = l.text_en.split(/\s+/);
  const i = w.findIndex((x) => x.toLowerCase().startsWith(needle.toLowerCase()));
  return i < 0 ? fallback : l.start + (l.len * i) / w.length;
}

// ---------------------------------------------------------------------------
// A window of the v1 film, holding its last frame if the beat runs longer.
const V1Window: React.FC<{ a: number; b: number }> = ({ a, b }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const last = Math.round((b - a) * fps) - 1;
  const inner = (
    <Sequence from={-Math.round(a * fps)} name={`v1 ${a} to ${b}`}>
      <Film />
    </Sequence>
  );
  return f > last ? <Freeze frame={last}>{inner}</Freeze> : inner;
};

// ---------------------------------------------------------------------------
// The countdown: 3:00 at the first intro card, counting real film time.
const Timer: React.FC = () => {
  const t = useSec();
  const { start, end } = TL.timer;
  if (t < start || t > end) return null;
  const left = Math.max(0, Math.floor(180 - (t - start)));
  const text = clock(`${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`);
  // Two scripted glances: when all four say "We are COFIRE", and P4's "We're fine".
  const g1 = line("intro5"), g2 = line("glance");
  const glance = (l?: Line) => (l ? Math.min(ramp(t, l.start - 0.3, l.start + 0.15), 1 - ramp(t, l.end + 0.2, l.end + 0.7)) : 0);
  const k = Math.max(glance(g1), glance(g2));
  const appear = ramp(t, start, start + 0.4);
  return (
    <div
      style={{
        position: "absolute", right: 48, bottom: 44, transformOrigin: "100% 100%",
        transform: `scale(${1 + 0.7 * k}) translate(${-60 * k}px, ${-40 * k}px)`, opacity: appear,
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
// Cold open: three verified numbers slam in, then fold into the state.
const COLD = [
  { line: "cold1", big: () => field("ext_drought_pct"), sub: "of Colorado is in drought", src: () => field("ext_drought_src") },
  { line: "cold2", big: () => field("ext_strontia_pct"), sub: "of Denver's drinking water passes through one reservoir", src: () => field("ext_strontia_src") },
  { line: "cold3", big: () => field("ext_sediment"), sub: "cubic yards of mud in it, after two fires", src: () => field("ext_sediment_src") },
];
const ColdOpen: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec() + b.start;
  const fold = line("cold4")?.start ?? b.end - 2;
  const items = COLD.map((c, i) => ({ ...c, at: line(c.line)?.start ?? b.start + i * 3, next: i < 2 ? line(COLD[i + 1].line)?.start ?? fold : fold }));
  const s = DATA as unknown as { colorado: { d: string; width: number; height: number } };
  const out = ramp(t, fold - 0.1, fold + 0.6);
  return (
    <AbsoluteFill style={{ background: T.ink, alignItems: "center", justifyContent: "center" }}>
      {items.map((c, i) => {
        if (t < c.at - 0.05 || t > c.next + 0.7) return null;
        const hit = easeOut(clamp01((t - c.at) / 0.28));
        const leave = i < 2 ? ramp(t, c.next - 0.12, c.next + 0.05) : out;
        return (
          <AbsoluteFill key={c.line} style={{ alignItems: "center", justifyContent: "center", opacity: hit * (1 - leave) }}>
            <div style={{ transform: `scale(${lerp(1.22, 1, hit) * lerp(1, i < 2 ? 0.92 : 0.25, leave)})`, textAlign: "center" }}>
              <div style={{ fontFamily: FONT.serif, fontWeight: 300, fontSize: i === 2 ? 250 : 330, lineHeight: 1, color: T.paper, letterSpacing: "-0.02em" }}>{c.big()}</div>
              <div style={{ fontFamily: FONT.sans, fontSize: 44, color: "rgba(243,243,238,0.82)", marginTop: 22 }}>{c.sub}</div>
            </div>
            <div style={{ position: "absolute", left: 64, bottom: 54, fontFamily: FONT.mono, fontSize: 24, color: "rgba(243,243,238,0.62)" }}>Source: {c.src()}</div>
          </AbsoluteFill>
        );
      })}
      {/* The numbers fold into the state they describe. */}
      <svg
        viewBox={`-4 -4 ${s.colorado.width + 8} ${s.colorado.height + 8}`}
        style={{ position: "absolute", width: 760, opacity: out, transform: `scale(${lerp(0.7, 1, easeOut(out))})` }}
      >
        <path d={s.colorado.d} fill="rgba(140,194,178,0.08)" stroke={SPRUCE_LIGHT} strokeWidth={1.4} vectorEffect="non-scaling-stroke" />
      </svg>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Trailer cards: name large, role under it, the gag as a subtitle.
const Card: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec();
  const who = (b.who ?? "P1").toLowerCase();
  const l = TL.lines.find((x) => x.beat === b.id);
  const sentences = (l?.text_en ?? "").match(/[^.!?]+[.!?]+/g) ?? [];
  const gag = (sentences.length >= 3 ? sentences.slice(2) : sentences.slice(1)).join(" ").trim();
  const inn = easeOut(clamp01(t / 0.35));
  const wipe = easeOut(clamp01((t - 0.15) / 0.5));
  const sub = ramp(t, 0.9, 1.4);
  const drift = t * 6;
  return (
    <AbsoluteFill style={{ background: T.ink, justifyContent: "center", padding: "0 160px" }}>
      <AbsoluteFill style={{ background: `radial-gradient(1100px 620px at 78% 30%, rgba(36,94,80,0.32), transparent 70%)` }} />
      <div style={{ transform: `translateX(${lerp(70, 0, inn) - drift}px)`, opacity: inn }}>
        <div style={{ fontFamily: FONT.sans, fontSize: 32, letterSpacing: "0.32em", textTransform: "uppercase", color: SPRUCE_LIGHT }}>{field(`role_${who}`)}</div>
        <div style={{ fontFamily: FONT.serif, fontWeight: 300, fontSize: 168, lineHeight: 1.04, color: T.paper, marginTop: 18, letterSpacing: "-0.02em" }}>{field(`name_${who}`)}</div>
        <div style={{ height: 3, width: 520 * wipe, background: SPRUCE_LIGHT, marginTop: 26 }} />
      </div>
      {gag ? (
        <div style={{ position: "absolute", left: 160, bottom: 150, maxWidth: 1300, fontFamily: FONT.serif, fontStyle: "italic", fontSize: 46, color: "rgba(243,243,238,0.86)", opacity: sub }}>
          {gag}
        </div>
      ) : null}
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
  const k = easeOut(clamp01(t / 0.45));
  return (
    <AbsoluteFill style={{ background: T.ink, alignItems: "center", justifyContent: "center" }}>
      <div style={{ transform: `scale(${lerp(1.15, 1, k)})`, opacity: k }}>
        <Wordmark size={250} />
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// The purpose, verbatim, and who it is for.
const Purpose: React.FC = () => {
  const t = useSec();
  const text = line("purpose")?.text_en ?? "";
  const k = easeOut(clamp01((t - 0.2) / 0.7));
  return (
    <AbsoluteFill style={{ background: T.paper, alignItems: "center", justifyContent: "center", padding: "0 200px" }}>
      <div style={{ opacity: k, transform: `translateY(${lerp(18, 0, k)}px)`, textAlign: "center" }}>
        <div style={{ fontFamily: FONT.sans, fontSize: 26, letterSpacing: "0.28em", textTransform: "uppercase", color: T.mute }}>What COFIRE does</div>
        <div style={{ fontFamily: FONT.serif, fontWeight: 300, fontSize: 68, lineHeight: 1.18, color: T.ink, marginTop: 30, textWrap: "balance" as never }}>{text}</div>
      </div>
    </AbsoluteFill>
  );
};

const AUDIENCE = [
  { label: "Denver residents", word: "Denver" },
  { label: "In English and Spanish", word: "English" },
  { label: "Neighborhood groups", word: "neighborhood" },
  { label: "Gardeners", word: "gardeners" },
  { label: "Teachers", word: "teachers" },
  { label: "City staff", word: "city" },
];
const Audience: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec() + b.start;
  const l = line("audience");
  return (
    <AbsoluteFill style={{ background: T.paper, justifyContent: "center", padding: "0 200px" }}>
      <div style={{ fontFamily: FONT.serif, fontWeight: 300, fontSize: 84, color: T.ink }}>Who it's for</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 18, marginTop: 44, maxWidth: 1400 }}>
        {AUDIENCE.map((a) => {
          const at = wordTime(l, a.word, b.start + 0.5);
          const k = easeOut(clamp01((t - at + 0.1) / 0.35));
          return (
            <div key={a.label} style={{ opacity: k, transform: `translateY(${lerp(14, 0, k)}px)`, padding: "16px 30px", borderRadius: 999, border: `1.5px solid ${k > 0.5 ? SPRUCE : T.rule}`, background: T.paperRaised, fontFamily: FONT.sans, fontSize: 40, color: T.ink }}>
              {a.label}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Slides: ink ground, paper type, spruce for what is being said.
const SlideFrame: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <AbsoluteFill style={{ background: T.ink, padding: "110px 150px" }}>
    <div style={{ fontFamily: FONT.serif, fontWeight: 300, fontSize: 84, color: T.paper, letterSpacing: "-0.015em" }}>{title}</div>
    <div style={{ position: "relative", flex: 1, marginTop: 56 }}>{children}</div>
  </AbsoluteFill>
);

const TOOLS = [
  { name: "Python", note: "Data pipeline and models", word: "Python" },
  { name: "pandas, xarray, SciPy, scikit-learn", note: "Analysis libraries", word: "models" },
  { name: "TypeScript, React, Next.js", note: "The app", word: "TypeScript" },
  { name: "MapLibre GL, PMTiles", note: "The map", word: "MapLibre" },
  { name: "GitHub Actions", note: "Weekly auto-update", word: "GitHub" },
  { name: "Postgres", note: "Predictions and reports", word: "weekly" },
  { name: "Playwright", note: "Automated browser tests", word: "update" },
];
const SlideTools: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec() + b.start;
  const l = line("slide1");
  const foot = wordTime(l, "AI", b.end - 3);
  return (
    <SlideFrame title="How it's built">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 22 }}>
        {TOOLS.map((x, i) => {
          const at = wordTime(l, x.word, b.start + 0.6 + i * 0.8);
          const appear = easeOut(clamp01((t - b.start - 0.2 - i * 0.07) / 0.4));
          const lit = ramp(t, at - 0.1, at + 0.25);
          return (
            <div key={x.name} style={{ opacity: appear * lerp(0.45, 1, lit), padding: "26px 28px", borderRadius: 2, border: `1.5px solid ${lit > 0.5 ? SPRUCE_LIGHT : "rgba(243,243,238,0.16)"}`, background: lit > 0.5 ? "rgba(36,94,80,0.32)" : "rgba(243,243,238,0.03)", minHeight: 150 }}>
              <div style={{ fontFamily: FONT.sans, fontSize: 36, color: T.paper, fontWeight: 500 }}>{x.name}</div>
              <div style={{ fontFamily: FONT.sans, fontSize: 26, color: "rgba(243,243,238,0.66)", marginTop: 10 }}>{x.note}</div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 0, bottom: 0, opacity: ramp(t, foot - 0.2, foot + 0.4), fontFamily: FONT.sans, fontSize: 30, color: "rgba(243,243,238,0.86)", lineHeight: 1.5 }}>
        Open-source libraries are listed in our repo.
        <br />
        AI-assisted development is disclosed in AI_USAGE.md.
      </div>
    </SlideFrame>
  );
};

const MODELS = ["Gradient boosting (LightGBM)", "Neural network (ConvLSTM)", "Ensemble of both"];
const SlideModels: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec() + b.start;
  const l = line("slide3");
  const win = wordTime(l, "simple", b.start + 4);
  return (
    <SlideFrame title="Simple beat complex">
      <div style={{ display: "flex", gap: 26 }}>
        {MODELS.map((m, i) => {
          const appear = easeOut(clamp01((t - b.start - 0.3 - i * 0.25) / 0.4));
          const gone = ramp(t, win - 0.6 + i * 0.35, win - 0.1 + i * 0.35);
          return (
            <div key={m} style={{ flex: 1, opacity: appear * (1 - gone), transform: `translateY(${lerp(0, 60, gone)}px)`, padding: "34px 30px", border: "1.5px solid rgba(243,243,238,0.18)", borderRadius: 2, fontFamily: FONT.sans, fontSize: 36, color: "rgba(243,243,238,0.8)" }}>
              {m}
            </div>
          );
        })}
      </div>
      {(() => {
        const k = easeOut(clamp01((t - win - 0.6) / 0.6));
        return (
          <div style={{ position: "absolute", left: 0, right: 0, top: 230, display: "flex", flexDirection: "column", alignItems: "center", opacity: k, transform: `scale(${lerp(0.94, 1, k)})` }}>
            <div style={{ padding: "40px 60px", border: `2px solid ${SPRUCE_LIGHT}`, background: "rgba(36,94,80,0.3)", borderRadius: 2, fontFamily: FONT.serif, fontWeight: 300, fontSize: 64, color: T.paper }}>
              Weeks like this one → what happened next
            </div>
            <div style={{ marginTop: 30, fontFamily: FONT.sans, fontSize: 34, color: "rgba(243,243,238,0.78)" }}>Explainable. Hard to beat.</div>
          </div>
        );
      })()}
    </SlideFrame>
  );
};

const SlideTested: React.FC<{ b: Beat; freeze?: boolean }> = ({ b, freeze }) => {
  const now = useSec() + b.start;
  const t = freeze ? b.end : now;
  const la = line("slide4a"), lb = line("slide4b");
  const segs = [
    { label: "Train", years: fill("{train_start} to {train_end}"), w: 15 },
    { label: "Validate", years: fill("{val_start} to {val_end}"), w: 4.2 },
    { label: "Calibrate", years: fill("{cal_start} to {cal_end}"), w: 4.2 },
    { label: "Locked, every look counted", years: field("holdout"), w: 5.4, hold: true },
  ];
  const total = segs.reduce((a, s) => a + s.w, 0);
  const badges = [
    { text: "Shuffled-data control", at: wordTime(la, "shuffled", b.start + 4) },
    { text: "Multiple-testing correction", at: wordTime(la, "shuffled", b.start + 4) + 0.6 },
    { text: fill("{n_survivors} of {n_tested} forecasts beat their baselines"), at: wordTime(la, "forecasts", b.start + 6) },
  ];
  const bugAt = lb?.start ?? b.end - 4;
  const strike = ramp(t, bugAt + 0.8, bugAt + 1.5);
  return (
    <SlideFrame title="Tested before we trusted it">
      <div style={{ display: "flex", gap: 6, height: 96 }}>
        {segs.map((s, i) => {
          const fillK = ramp(t, b.start + 0.3 + i * 0.5, b.start + 0.8 + i * 0.5);
          return (
            <div key={s.label} style={{ flex: s.w / total, position: "relative" }}>
              <div style={{ height: "100%", background: s.hold ? "rgba(36,94,80,0.55)" : `rgba(243,243,238,${0.85 - i * 0.18})`, border: s.hold ? `2px solid ${SPRUCE_LIGHT}` : "none", transformOrigin: "0 50%", transform: `scaleX(${fillK})` }} />
              <div style={{ marginTop: 16, opacity: fillK, fontFamily: FONT.sans, fontSize: 28, color: s.hold ? SPRUCE_LIGHT : T.paper }}>{s.label}</div>
              <div style={{ marginTop: 4, opacity: fillK, fontFamily: FONT.mono, fontSize: 24, color: "rgba(243,243,238,0.62)" }}>{s.years}</div>
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", gap: 18, marginTop: 150 }}>
        {badges.map((x) => {
          const k = easeOut(clamp01((t - x.at) / 0.35));
          return (
            <div key={x.text} style={{ opacity: k, transform: `translateY(${lerp(12, 0, k)}px)`, padding: "16px 26px", borderRadius: 999, border: `1.5px solid ${SPRUCE_LIGHT}`, fontFamily: FONT.sans, fontSize: 32, color: T.paper }}>
              {x.text}
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 0, bottom: 0, display: "flex", alignItems: "center", gap: 24, opacity: ramp(t, bugAt - 0.1, bugAt + 0.4) }}>
        <span style={{ position: "relative", padding: "10px 22px", borderRadius: 999, border: `1.5px solid ${T.emberBright}`, fontFamily: FONT.sans, fontSize: 28, color: T.emberBright }}>
          forecast band
          <span style={{ position: "absolute", left: 12, right: 12, top: "50%", height: 2.5, background: T.emberBright, transformOrigin: "0 50%", transform: `scaleX(${strike})` }} />
        </span>
        <span style={{ fontFamily: FONT.sans, fontSize: 34, color: T.paper }}>Found a bug in our best result → removed it</span>
      </div>
    </SlideFrame>
  );
};

// ---------------------------------------------------------------------------
const EndCard: React.FC<{ b: Beat }> = ({ b }) => {
  const t = useSec() + b.start;
  const names = line("close3");
  const k = easeOut(clamp01((t - b.start) / 0.5));
  return (
    <AbsoluteFill style={{ background: T.ink, alignItems: "center", justifyContent: "center" }}>
      <div style={{ opacity: k, transform: `translateY(${lerp(14, 0, k)}px)`, textAlign: "center" }}>
        <Wordmark size={200} />
        <div style={{ fontFamily: FONT.serif, fontWeight: 300, fontSize: 46, color: "rgba(243,243,238,0.86)", marginTop: 26 }}>Calibrated odds for Denver, and for the water it depends on.</div>
        <div style={{ display: "flex", justifyContent: "center", gap: 54, marginTop: 70 }}>
          {["p1", "p2", "p3", "p4"].map((p, i) => {
            const at = names ? names.start + (names.len * i) / 4 : b.start + 1 + i * 0.4;
            const kk = easeOut(clamp01((t - at + 0.1) / 0.35));
            return (
              <div key={p} style={{ opacity: kk, fontFamily: FONT.sans, fontSize: 40, color: T.paper }}>{field(`name_${p}`)}</div>
            );
          })}
        </div>
      </div>
      <div style={{ position: "absolute", bottom: 46, fontFamily: FONT.mono, fontSize: 20, color: "rgba(243,243,238,0.6)" }}>
        Data: U.S. Drought Monitor, gridMET. Map: OpenStreetMap contributors, Protomaps.
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
/** A slow push on every new scene, so no frame of the film is ever still. */
const Drift: React.FC<{ b: Beat; children: React.ReactNode }> = ({ b, children }) => {
  const t = useSec();
  const u = clamp01(t / Math.max(0.1, b.end - b.start));
  return <AbsoluteFill style={{ transform: `scale(${1 + 0.03 * u})`, transformOrigin: "50% 45%" }}>{children}</AbsoluteFill>;
};

const Scene: React.FC<{ b: Beat }> = ({ b }) => {
  if (b.v1) return <V1Window a={b.v1[0]} b={b.v1[1]} />;
  return <Drift b={b}><SceneBody b={b} /></Drift>;
};

const SceneBody: React.FC<{ b: Beat }> = ({ b }) => {
  switch (b.scene) {
    case "ColdOpen": return <ColdOpen b={b} />;
    case "Card": return <Card b={b} />;
    case "Logo": return <Logo />;
    case "Purpose": return <Purpose />;
    case "Audience": return <Audience b={b} />;
    case "SlideTools": return <SlideTools b={b} />;
    case "SlideModels": return <SlideModels b={b} />;
    case "SlideTested": return <SlideTested b={b} />;
    case "Glance": return <SlideTested b={beat("slide4")} freeze />;
    case "EndCard": return <EndCard b={b} />;
    default: throw new Error(`no v2 scene ${b.scene}`);
  }
};

export const ScratchV2: React.FC = () => (
  <div style={{ position: "absolute", left: 28, top: 22, padding: "6px 12px", borderRadius: 3, background: "rgba(22,26,25,0.72)", fontFamily: FONT.sans, fontSize: 18, color: "rgba(243,243,238,0.85)" }}>
    Scratch voices (macOS say), placeholder names: draft
  </div>
);

export const FilmV2: React.FC<{ scratch?: boolean; start?: number; length?: number }> = ({ scratch = false }) => {
  const { fps } = useVideoConfig();
  return (
    <Guard name="FilmV2">
      <AbsoluteFill style={{ background: T.ink }}>
        {TL.beats.map((b) => (
          <Sequence key={b.id} from={Math.round(b.start * fps)} durationInFrames={Math.max(1, Math.round((b.end - b.start) * fps))} name={b.id}>
            <Scene b={b} />
          </Sequence>
        ))}
        <Timer />
        {scratch ? <ScratchV2 /> : null}
      </AbsoluteFill>
    </Guard>
  );
};

/** The vertical cut: the cold open and the team intros, for phones. */
export const V2_VERTICAL = Math.min(45, beat("logo").end);
export const VerticalV2: React.FC<{ scratch?: boolean }> = ({ scratch = false }) => {
  const { fps } = useVideoConfig();
  // The landscape picture, fitted to the phone's width, over the ink ground.
  const scale = 1080 / 1920;
  return (
    <Guard name="VerticalV2">
      <AbsoluteFill style={{ background: T.ink }}>
        <div style={{ position: "absolute", left: 0, top: (1920 - 1080 * scale) / 2, width: 1920, height: 1080, transform: `scale(${scale})`, transformOrigin: "0 0" }}>
          <AbsoluteFill>
            {TL.beats.filter((b) => b.end <= V2_VERTICAL + 0.01).map((b) => (
              <Sequence key={b.id} from={Math.round(b.start * fps)} durationInFrames={Math.max(1, Math.round((b.end - b.start) * fps))} name={b.id}>
                <Scene b={b} />
              </Sequence>
            ))}
            <Timer />
          </AbsoluteFill>
        </div>
        <div style={{ position: "absolute", top: 260, left: 0, right: 0, textAlign: "center" }}>
          <Wordmark size={150} />
        </div>
        {scratch ? <ScratchV2 /> : null}
      </AbsoluteFill>
    </Guard>
  );
};
