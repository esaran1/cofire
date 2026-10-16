/**
 * Part 4, why it can be trusted. Data-driven graphics, no slides: the frozen
 * model and the counted looks (facts.json), the 115 paired comparisons
 * against a shuffled control (artifacts/v11/survivors_v11.csv), and the
 * interval audit (facts.json interval_audit): the ranges that looked perfect,
 * the leak, the collapse.
 */
import { AbsoluteFill } from "remotion";
import { DATA } from "../data";
import { FONT, T } from "../theme";
import { field } from "../trace";
import { clamp01, easeInOut, easeOut, inOut, lerp, ramp, useT } from "../util";
import { Kinetic, Label } from "../components/Type";

const W = 1920, H = 1080;
const Dark: React.FC<{ children: React.ReactNode }> = ({ children }) => <AbsoluteFill style={{ background: T.ink }}>{children}</AbsoluteFill>;

export const TrustTitle: React.FC = () => {
  const t = useT();
  return (
    <Dark>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", transform: `scale(${lerp(1, 1.04, t / 5.3)})` }}>
        <Kinetic text="Why trust it?" t={t} start={0.35} end={5.3} size={150} />
      </AbsoluteFill>
    </Dark>
  );
};

const Lock: React.FC<{ u: number; size?: number }> = ({ u, size = 64 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64">
    <path d={`M20 30 V${lerp(14, 20, u)} a12 12 0 0 1 24 0 V${lerp(18, 30, u)}`} fill="none" stroke={T.emberBright} strokeWidth={5} strokeLinecap="round" />
    <rect x="12" y="30" width="40" height="28" rx="4" fill={T.emberBright} />
    <circle cx="32" cy="43" r="4" fill={T.ink} />
  </svg>
);

const Card: React.FC<{ t: number; at: number; title: string; line: string; mono: string }> = ({ t, at, title, line, mono }) => {
  const u = easeOut(clamp01((t - at) / 0.7));
  const lock = ramp(t, at + 0.8, at + 1.3);
  return (
    <div style={{ width: 780, padding: "52px 56px", border: `1px solid rgba(244,242,236,0.16)`, borderRadius: 4, background: "rgba(244,242,236,0.04)", transform: `translateY(${(1 - u) * 50}px)`, opacity: u }}>
      <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
        <Lock u={lock} size={76} />
        <Label size={62} style={{ fontFamily: FONT.serif }}>{title}</Label>
      </div>
      <Label size={36} color="rgba(244,242,236,0.75)" style={{ marginTop: 28 }}>{line}</Label>
      <Label size={46} weight={500} style={{ fontFamily: FONT.mono, marginTop: 10, letterSpacing: "0.02em" }}>{mono}</Label>
    </div>
  );
};

export const Freeze: React.FC = () => {
  const t = useT();
  return (
    <Dark>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", transform: `scale(${lerp(1, 1.035, t / 5.5)})` }}>
        <Label size={40} color="rgba(244,242,236,0.7)" style={{ marginBottom: 56, opacity: ramp(t, 0.1, 0.6), letterSpacing: "0.08em", textTransform: "uppercase" }}>{field("holdout")} · held out</Label>
        <div style={{ display: "flex", gap: 48 }}>
          <Card t={t} at={0.3} title="The model" line="frozen at commit" mono={field("freeze_short")} />
          <Card t={t} at={1.5} title="The test" line="written down first; its fingerprint" mono={`${field("prereg_short")}…`} />
        </div>
      </AbsoluteFill>
    </Dark>
  );
};

export const Looks: React.FC = () => {
  const t = useT();
  const n = Number(field("looks"));
  const col = (i: number, label: string, children: React.ReactNode) => {
    const u = easeOut(clamp01((t - 0.2 - i * 0.45) / 0.6));
    return (
      <div style={{ width: 520, opacity: u, transform: `translateY(${(1 - u) * 30}px)` }}>
        <Label size={30} color="rgba(244,242,236,0.7)" style={{ letterSpacing: "0.06em", textTransform: "uppercase" }}>{label}</Label>
        <div style={{ marginTop: 18 }}>{children}</div>
      </div>
    );
  };
  return (
    <Dark>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "row", gap: 30, transform: `translateX(${lerp(20, -20, t / 5.4)}px)` }}>
        {col(0, "The held-out year", <Label size={120} weight={500} style={{ fontFamily: FONT.mono }}>{field("holdout")}</Label>)}
        {col(1, "Looks at it, all counted", (
          <div style={{ display: "flex", alignItems: "center", gap: 26 }}>
            <Label size={120} weight={500} style={{ fontFamily: FONT.mono }}>{field("looks")}</Label>
            <div style={{ display: "flex", gap: 14 }}>
              {Array.from({ length: n }, (_, i) => (
                <div key={i} style={{ width: 16, height: 96, background: T.paper, borderRadius: 2, opacity: ramp(t, 1.0 + i * 0.25, 1.2 + i * 0.25), transform: `scaleY(${ramp(t, 1.0 + i * 0.25, 1.3 + i * 0.25, easeOut)})`, transformOrigin: "bottom" }} />
              ))}
            </div>
          </div>
        ))}
        {col(2, "Scored in full on", <Label size={64} weight={500} style={{ fontFamily: FONT.serif, lineHeight: 1.1 }}>{field("unseal")}</Label>)}
      </AbsoluteFill>
    </Dark>
  );
};

// --- The paired control: 115 comparisons. -------------------------------------
const CMP = DATA.comparisons;
const EST = CMP.filter((c) => c.estimable && c.diff !== null && c.lo !== null && c.hi !== null).sort((a, b) => (a.diff as number) - (b.diff as number));
const NOT = CMP.filter((c) => !EST.includes(c));
const LO = Math.min(...EST.map((c) => c.lo as number)), HI = Math.max(...EST.map((c) => c.hi as number));
const span = Math.max(Math.abs(LO), Math.abs(HI));
const AX = { left: 520, right: 1720, top: 190, bottom: 900 };
const xOf = (v: number) => AX.left + ((v + span) / (2 * span)) * (AX.right - AX.left);

/** Both control shots: the dots gather (0 to 5.3 s), then the survivors light (5.3 to 10.8 s). */
export const Control: React.FC = () => {
  const t = useT();
  const gather = ramp(t, 1.6, 4.4, easeInOut);
  const light = ramp(t, 5.6, 6.6);
  const push = ramp(t, 7.4, 10.8, easeInOut);
  const rowH = (AX.bottom - AX.top) / EST.length;
  const grid = (i: number) => {
    const cols = 23;
    return { x: 560 + (i % cols) * 48, y: 330 + Math.floor(i / cols) * 48 };
  };
  const zeroX = xOf(0);
  return (
    <Dark>
      <AbsoluteFill style={{ transformOrigin: `${zeroX + 300}px 360px`, transform: `scale(${lerp(1, 1.12, push)})` }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 84, textAlign: "center", opacity: inOut(t, 0.2, 10.8) }}>
          <Label size={38} style={{ fontFamily: FONT.serif }}>{field("n_comparisons")} forecast comparisons, real outcomes against the same outcomes shuffled</Label>
        </div>
        <svg width={W} height={H} style={{ position: "absolute", inset: 0 }}>
          <line x1={zeroX} x2={zeroX} y1={AX.top - 20} y2={AX.bottom + 20} stroke="rgba(244,242,236,0.5)" strokeWidth={2} strokeDasharray="6 6" opacity={gather} />
          {EST.map((c, i) => {
            const g = grid(i);
            const y = AX.top + (i + 0.5) * rowH;
            const x = lerp(g.x, xOf(c.diff as number), gather);
            const yy = lerp(g.y, y, gather);
            const on = c.survivor ? light : 0;
            const colour = on > 0 ? T.emberBright : "rgba(244,242,236,0.55)";
            return (
              <g key={`${c.domain}-${c.target}`}>
                <line x1={lerp(x, xOf(c.lo as number), gather)} x2={lerp(x, xOf(c.hi as number), gather)} y1={yy} y2={yy} stroke={colour} strokeOpacity={gather * (0.35 + 0.55 * on)} strokeWidth={2} />
                <circle cx={x} cy={yy} r={lerp(9, 4.5, gather) + on * 1.5} fill={colour} opacity={c.survivor ? 0.65 + 0.35 * on : lerp(0.9, 0.5 - 0.25 * light, gather)} />
              </g>
            );
          })}
          {NOT.map((c, i) => {
            const g = grid(EST.length + i);
            const x = lerp(g.x, 300 + (i % 4) * 26, gather);
            const y = lerp(g.y, AX.top + 40 + Math.floor(i / 4) * 26, gather);
            return <circle key={`${c.domain}-${c.target}`} cx={x} cy={y} r={lerp(9, 6, gather)} fill="none" stroke="rgba(244,242,236,0.45)" strokeWidth={2} opacity={1 - 0.4 * gather} />;
          })}
        </svg>
        <div style={{ position: "absolute", left: zeroX - 260, top: AX.bottom + 34, width: 520, textAlign: "center", opacity: gather }}>
          <Label size={28} color="rgba(244,242,236,0.75)">no better than shuffled</Label>
        </div>
        <div style={{ position: "absolute", left: AX.right - 360, top: AX.bottom + 34, width: 360, textAlign: "right", opacity: gather }}>
          <Label size={28} color="rgba(244,242,236,0.75)">better →</Label>
        </div>
        <div style={{ position: "absolute", left: 230, top: AX.top - 34, width: 200, opacity: gather * 0.9 }}>
          <Label size={26} color="rgba(244,242,236,0.7)">too few events to test</Label>
        </div>
        <div style={{ position: "absolute", left: 1290, top: 300, width: 520, opacity: light }}>
          <Label size={150} weight={500} color={T.emberBright} style={{ fontFamily: FONT.mono, lineHeight: 1 }}>{field("n_survivors")}</Label>
          <Label size={34} style={{ marginTop: 10 }}>of {field("n_comparisons")} beat the shuffled control,</Label>
          <Label size={34} color="rgba(244,242,236,0.75)">after correcting for testing so many.</Label>
        </div>
      </AbsoluteFill>
    </Dark>
  );
};

// --- The interval audit: six forecast ranges. ----------------------------------
const PAIRS = DATA.intervals.pairs;
const CH = { left: 300, right: 1620, top: 260, bottom: 860 };
const yOf = (v: number) => CH.bottom - v * (CH.bottom - CH.top);
const TARGET = Number(field("coverage_target").replace("%", "")) / 100;

const Bars: React.FC<{ values: number[]; labels: string[]; grow: number; tone: number[] }> = ({ values, labels, grow, tone }) => {
  const bw = 120, gap = (CH.right - CH.left - PAIRS.length * bw) / (PAIRS.length - 1);
  return (
    <>
      <svg width={W} height={H} style={{ position: "absolute", inset: 0 }}>
        <line x1={CH.left - 40} x2={CH.right + 40} y1={yOf(TARGET)} y2={yOf(TARGET)} stroke={T.paper} strokeOpacity={0.75} strokeWidth={2.5} strokeDasharray="10 8" />
        <line x1={CH.left - 40} x2={CH.right + 40} y1={CH.bottom} y2={CH.bottom} stroke="rgba(244,242,236,0.35)" strokeWidth={2} />
        {values.map((v, i) => {
          const x = CH.left + i * (bw + gap);
          const h = (CH.bottom - yOf(v)) * grow;
          const c = tone[i] > 0 ? `rgb(${lerp(196, 226, tone[i])},${lerp(196, 100, tone[i])},${lerp(190, 60, tone[i])})` : "rgb(196,196,190)";
          return <rect key={i} x={x} y={CH.bottom - h} width={bw} height={h} fill={c} rx={2} />;
        })}
      </svg>
      {values.map((v, i) => {
        const x = CH.left + i * (bw + gap);
        return (
          <div key={i}>
            <div style={{ position: "absolute", left: x - 40, width: bw + 80, top: CH.bottom - (CH.bottom - yOf(v)) * grow - 58, textAlign: "center", opacity: grow }}>
              <Label size={34} weight={500} style={{ fontFamily: FONT.mono }}>{labels[i]}</Label>
            </div>
            <div style={{ position: "absolute", left: x - 60, width: bw + 120, top: CH.bottom + 18, textAlign: "center" }}>
              <Label size={28} color="rgba(244,242,236,0.8)">{field(`pair_${i}_label`)}</Label>
            </div>
          </div>
        );
      })}
      <div style={{ position: "absolute", left: CH.right + 50, top: yOf(TARGET) - 20 }}>
        <Label size={30} color="rgba(244,242,236,0.9)">target {field("coverage_target")}</Label>
      </div>
    </>
  );
};

/** The ranges as tested, rising onto the target; then "It looked perfect." */
export const Ranges: React.FC = () => {
  const t = useT();
  const grow = ramp(t, 0.4, 2.2, easeOut);
  return (
    <Dark>
      <AbsoluteFill style={{ transformOrigin: "50% 40%", transform: `scale(${lerp(1, 1.06, ramp(t, 4.4, 7.7))})` }}>
        <div style={{ position: "absolute", left: CH.left - 40, top: 110, opacity: inOut(t, 0.1, 7.7) * (1 - ramp(t, 4.0, 4.4)) }}>
          <Label size={40} style={{ fontFamily: FONT.serif }}>Forecast ranges, as first tested: coverage in their worst stretch</Label>
        </div>
        <Bars values={PAIRS.map((p) => p.tested)} labels={PAIRS.map((_, i) => field(`pair_${i}_tested`))} grow={grow} tone={PAIRS.map(() => 0)} />
        {t > 4.3 ? (
          <div style={{ position: "absolute", left: 0, right: 0, top: 92, textAlign: "center" }}>
            <Kinetic text="It looked perfect." t={t} start={4.45} end={7.75} size={110} italic />
          </div>
        ) : null}
      </AbsoluteFill>
    </Dark>
  );
};

/** The leak, as a timeline: an outcome used before it could be known; then the honest delay. */
export const Leak: React.FC = () => {
  const t = useT();
  const n = 12, bw = 104, gap = 22, left = (W - (n * bw + (n - 1) * gap)) / 2, top = 470;
  const bx = (i: number) => left + i * (bw + gap);
  const outcome = 7, early = 4; // positions on the row, not data
  const real = ramp(t, 4.6, 5.6, easeInOut);
  const arrowTo = lerp(early, outcome + 1, real);
  const x1 = bx(outcome) + bw / 2, x2 = bx(arrowTo) + bw / 2;
  const back = x2 < x1;
  const mid = (x1 + x2) / 2;
  const lift = 150;
  const draw = ramp(t, 0.9, 2.0);
  return (
    <Dark>
      <div style={{ position: "absolute", left: 0, right: 0, top: 150, textAlign: "center", opacity: inOut(t, 0.2, 4.7) }}>
        <Label size={44} style={{ fontFamily: FONT.serif }}>As tested, each range was corrected with an outcome</Label>
        <Label size={44} style={{ fontFamily: FONT.serif }}>a real forecast would not know yet.</Label>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 150, textAlign: "center", opacity: ramp(t, 4.9, 5.4) }}>
        <Label size={44} style={{ fontFamily: FONT.serif }}>In real time, an outcome is known only</Label>
        <Label size={44} style={{ fontFamily: FONT.serif }}>{field("h_min")} to {field("h_max")} weeks after its forecast is made.</Label>
      </div>
      {Array.from({ length: n }, (_, i) => {
        const isOutcome = i === outcome;
        const isTarget = Math.abs(i - arrowTo) < 0.5;
        return (
          <div key={i} style={{ position: "absolute", left: bx(i), top, width: bw, height: 110, borderRadius: 3, border: `2px solid ${isOutcome ? T.emberBright : "rgba(244,242,236,0.28)"}`, background: isOutcome ? "rgba(226,100,60,0.18)" : isTarget ? "rgba(244,242,236,0.12)" : "transparent" }} />
        );
      })}
      <svg width={W} height={H} style={{ position: "absolute", inset: 0 }}>
        <defs>
          <marker id="lk" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={back ? T.emberBright : T.paper} />
          </marker>
        </defs>
        <path d={`M ${x1} ${top} C ${x1} ${top - lift}, ${x2} ${top - lift}, ${x2} ${top - 4}`} stroke={back ? T.emberBright : T.paper} strokeWidth={5} fill="none" markerEnd="url(#lk)" strokeDasharray={1400} strokeDashoffset={1400 * (1 - draw)} />
        <line x1={left} x2={bx(n - 1) + bw} y1={top + 160} y2={top + 160} stroke="rgba(244,242,236,0.4)" strokeWidth={2} markerEnd="url(#lk)" />
      </svg>
      <div style={{ position: "absolute", left: bx(outcome) - 60, width: bw + 120, top: top + 122, textAlign: "center" }}>
        <Label size={30} color={T.emberBright}>outcome</Label>
      </div>
      <div style={{ position: "absolute", left: mid - 300, width: 600, top: top - lift - 50, textAlign: "center", opacity: draw }}>
        <Label size={34} color={back ? T.emberBright : T.paper}>{back ? "used before it was known" : "used once it is known"}</Label>
      </div>
      <div style={{ position: "absolute", right: left, top: top + 176 }}>
        <Label size={28} color="rgba(244,242,236,0.7)">weeks →</Label>
      </div>
    </Dark>
  );
};

/** With the honest delay, the six ranges fall. */
export const Collapse: React.FC = () => {
  const t = useT();
  const u = ramp(t, 0.5, 2.6, easeInOut);
  const vals = PAIRS.map((p) => lerp(p.tested, p.realtime, u));
  const drop = PAIRS.map((p) => clamp01((p.tested - p.realtime) / 0.65) * u);
  const labels = PAIRS.map((_, i) => (u < 0.5 ? field(`pair_${i}_tested`) : field(`pair_${i}_realtime`)));
  const big = ramp(t, 4.9, 5.4, easeOut);
  return (
    <Dark>
      <div style={{ position: "absolute", left: CH.left - 40, top: 110, opacity: inOut(t, 0.1, 4.9) }}>
        <Label size={40} style={{ fontFamily: FONT.serif }}>The same ranges in real time, with the honest delay</Label>
      </div>
      <div style={{ opacity: 1 - big * 0.85 }}>
        <Bars values={vals} labels={labels} grow={1} tone={drop} />
      </div>
      {t > 4.8 ? (
        <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", opacity: big, transform: `scale(${lerp(0.94, 1.02, ramp(t, 4.9, 6.8))})` }}>
          <Label size={300} weight={500} color={T.emberBright} style={{ fontFamily: FONT.mono, lineHeight: 1 }}>{field("roll13_pct")}%</Label>
          <Label size={40} style={{ marginTop: 20 }}>coverage in the worst stretch, in real time</Label>
        </AbsoluteFill>
      ) : null}
    </Dark>
  );
};
