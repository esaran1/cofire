/**
 * Part 3, the product: every frame is the real app, captured from the
 * production build (capture/capture.mjs). The camera moves over the captures;
 * the cursor follows the recorded pointer path.
 */
import { AbsoluteFill, Img, staticFile } from "remotion";
import { around, cap, CapturePlane, rect, type Key, type View } from "../components/Capture";
import { Laptop, laptopGeometry, Phone } from "../components/Devices";
import { shot } from "../data";
import { T } from "../theme";
import { clamp01, easeInOut, easeOut, lerp, ramp, useT } from "../util";

const W = 1920, H = 1080, A = W / H;
const FULL: View = { x: 0, y: 0, w: 1920 };

/** A dark, slightly lit ground for device shots. */
export const Ground: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ background: `radial-gradient(120% 90% at 50% 38%, #26282e 0%, ${T.ink} 62%)` }}>{children}</AbsoluteFill>
);

// The laptop: its screen is 1280 wide at rest.
const LAP = laptopGeometry(1280);
const lapLeft = (W - LAP.baseW) / 2, lapTop = (H - LAP.totalH) / 2 + 30;
const screenOrigin = { x: lapLeft + (LAP.baseW - LAP.lidW) / 2 + LAP.bezel, y: lapTop + LAP.bezel * 1.2 };
/** Transform that makes the laptop's screen fill the frame. */
const FILL = { s: W / LAP.screenW, x: -screenOrigin.x * (W / LAP.screenW), y: -screenOrigin.y * (W / LAP.screenW) };

const LaptopRig: React.FC<{ s: number; x: number; y: number; children: React.ReactNode }> = ({ s, x, y, children }) => (
  <div style={{ position: "absolute", left: 0, top: 0, transformOrigin: "0 0", transform: `translate(${x}px, ${y}px) scale(${s})` }}>
    <div style={{ position: "absolute", left: lapLeft, top: lapTop }}>
      <Laptop screenW={LAP.screenW}>{children}</Laptop>
    </div>
  </div>
);

export const LaptopIntro: React.FC = () => {
  const t = useT();
  const u = easeOut(clamp01(t / 1.6));
  const box = { w: LAP.screenW, h: LAP.screenH };
  return (
    <Ground>
      <div style={{ position: "absolute", inset: 0, opacity: clamp01(t / 0.5) }}>
        <LaptopRig s={lerp(0.9, 1, u)} x={lerp(W * 0.05, 0, u)} y={lerp(260, 0, u)}>
          <CapturePlane name="pick" t={t} keys={[{ t: 0, view: FULL }]} box={box} />
        </LaptopRig>
      </div>
    </Ground>
  );
};

export const Pick: React.FC = () => {
  const t = useT();
  const sw = rect("pick", "switcher");
  const box = { w: LAP.screenW, h: LAP.screenH };
  // Push the whole laptop toward the picker while the screen's view narrows on it.
  const u = ramp(t, 0, 2.4);
  const target = { x: screenOrigin.x + ((sw.x + sw.w / 2) / 1920) * LAP.screenW, y: screenOrigin.y + ((sw.y + sw.h / 2) / 1080) * LAP.screenH };
  const s = lerp(1, 1.5, u);
  const x = lerp(0, W * 0.62 - target.x * s, u), y = lerp(0, H * 0.36 - target.y * s, u);
  const track = cap("pick").cursor ?? [];
  return (
    <Ground>
      <LaptopRig s={s} x={x} y={y}>
        <CapturePlane name="pick" t={t} keys={[{ t: 0, view: FULL }, { t: 2.6, view: { x: 760, y: 0, w: 1160 } }]} box={box} cursor={{ track, start: shot("product.pick").cursor!.start, speed: shot("product.pick").cursor!.speed }} />
      </LaptopRig>
    </Ground>
  );
};

export const FlyIn: React.FC = () => {
  const t = useT();
  const sw = rect("pick", "switcher");
  const target = { x: screenOrigin.x + ((sw.x + sw.w / 2) / 1920) * LAP.screenW, y: screenOrigin.y + ((sw.y + sw.h / 2) / 1080) * LAP.screenH };
  // From where the pick shot ended to the screen filling the frame.
  const from = { s: 1.5, x: W * 0.62 - target.x * 1.5, y: H * 0.36 - target.y * 1.5 };
  const u = ramp(t, 0, 0.9);
  const s = lerp(from.s, FILL.s, u), x = lerp(from.x, FILL.x, u), y = lerp(from.y, FILL.y, u);
  const f = cap("flyin");
  const frame = Math.max(0, (t - 0.55) * (f.fps ?? 60));
  const box = { w: LAP.screenW, h: LAP.screenH };
  const view = lerp(1160, 1920, u);
  return (
    <Ground>
      <LaptopRig s={s} x={x} y={y}>
        <CapturePlane name="flyin" t={t} frameAt={frame} keys={[{ t: 0, view: { x: 760 * (1 - u), y: 0, w: view } }]} box={box} />
      </LaptopRig>
    </Ground>
  );
};

/** The magic moment: tap a square, the card resolves. */
export const Tap: React.FC = () => {
  const t = useT();
  const c = cap("card");
  const cell = rect("card", "cellOnMap");
  const click = (c.cursor ?? []).find((p) => p.click);
  const { start: startAt, speed } = shot("product.tap").cursor!;
  const clickAt = click ? startAt + (click.t - (c.cursor ?? [])[0].t) / 1000 / speed : 1.6;
  const keys: Key[] = [
    { t: 0, view: FULL },
    { t: clickAt, view: { x: 260, y: 40, w: 1500 } },
    { t: clickAt + 1.2, view: { x: 0, y: 30, w: 1340 } },
    { t: 6.7, view: { x: 0, y: 60, w: 1180 } },
  ];
  const resolve = ramp(t, clickAt + 0.12, clickAt + 0.5);
  void cell;
  return (
    <AbsoluteFill style={{ background: T.ink }}>
      <CapturePlane name="denver" t={t} keys={keys} box={{ w: W, h: H }} crossTo={{ name: "card", u: resolve }} cursor={{ track: c.cursor ?? [], start: startAt, speed, until: clickAt + 1.6 }} />
    </AbsoluteFill>
  );
};

/** Down the card to the first odds. */
export const CardRows: React.FC = () => {
  const t = useT();
  const f = rect("card_row", "frequency");
  const keys: Key[] = [
    { t: 0, view: { x: 0, y: 60, w: 1180 } },
    { t: 2.9, view: around({ x: 10, y: f.y - 70, w: 400, h: 200 }, A, 0.12) },
  ];
  return <CapturePlane name="card_row" t={t} keys={keys} box={{ w: W, h: H }} />;
};

/** The frequency sentence, close. */
export const Frequency: React.FC = () => {
  const t = useT();
  const f = rect("card_row", "frequency");
  const a = around({ x: 10, y: f.y - 70, w: 400, h: 200 }, A, 0.12);
  const b = around({ x: f.x - 6, y: f.y - 30, w: f.w + 40, h: f.h + 40 }, A, 0.1);
  return <CapturePlane name="card_row" t={t} keys={[{ t: 0, view: a }, { t: 1.6, view: b }, { t: 4.7, view: { ...b, x: b.x + 6, w: b.w * 0.97 } }]} box={{ w: W, h: H }} />;
};

/** Open "Why": the icon array. */
export const Icons: React.FC = () => {
  const t = useT();
  const f = rect("card_row", "frequency");
  const icons = rect("card_why_open", "icons");
  const w = cap("card_why_open");
  const click = (w.cursor ?? []).find((p) => p.click);
  const { start: startAt, speed } = shot("product.icons").cursor!;
  const clickAt = click ? startAt + (click.t - (w.cursor ?? [])[0].t) / 1000 / speed : 1.3;
  const b = around({ x: f.x - 6, y: f.y - 30, w: f.w + 40, h: f.h + 40 }, A, 0.1);
  const keys: Key[] = [
    { t: 0, view: { ...b, w: b.w * 1.35, x: b.x - 10 } },
    { t: clickAt + 0.3, view: around({ x: 10, y: f.y - 40, w: 400, h: 230 }, A, 0.08) },
    { t: 5.3, view: around({ x: icons.x - 10, y: f.y - 10, w: 360, h: icons.y + icons.h - f.y + 30 }, A, 0.1) },
  ];
  return (
    <CapturePlane name="card_row" t={t} keys={keys} box={{ w: W, h: H }} crossTo={{ name: "card_why_open", u: ramp(t, clickAt + 0.08, clickAt + 0.4) }} cursor={{ track: w.cursor ?? [], start: startAt, speed, until: clickAt + 1.0 }} />
  );
};

export const Weeks: React.FC<{ part: 1 | 2 }> = ({ part }) => {
  const t = useT();
  const r = rect("card_weeks", "weeks");
  const top = around({ x: r.x - 6, y: r.y - 10, w: r.w + 12, h: 150 }, A, 0.08);
  const bottom = around({ x: r.x - 6, y: r.y + r.h - 150, w: r.w + 12, h: 150 }, A, 0.08);
  const keys: Key[] = part === 1
    ? [{ t: 0, view: { ...top, w: top.w * 1.25, x: top.x - 20 } }, { t: 3.9, view: top }]
    : [{ t: 0, view: top }, { t: 3.0, view: bottom }];
  return <CapturePlane name="card_weeks" t={t} keys={keys} box={{ w: W, h: H }} />;
};

export const Watershed: React.FC<{ part: 1 | 2 }> = ({ part }) => {
  const t = useT();
  const p = rect("card_ws", "panel");
  const head = around({ x: p.x - 6, y: p.y - 10, w: p.w + 12, h: 190 }, A, 0.08);
  const table = around({ x: p.x - 6, y: p.y + 240, w: p.w + 12, h: 140 }, A, 0.06);
  const keys: Key[] = part === 1
    ? [{ t: 0, view: { ...head, w: head.w * 1.3, x: head.x - 30 } }, { t: 3.2, view: head }]
    : [{ t: 0, view: head }, { t: 2.6, view: table }];
  return <CapturePlane name="card_ws" t={t} keys={keys} box={{ w: W, h: H }} />;
};

/** The language toggle: the screen turns over to Spanish. */
export const Spanish: React.FC = () => {
  const t = useT();
  const es = cap("card_es");
  const click = (es.cursor ?? []).find((p) => p.click);
  const { start: startAt, speed } = shot("product.es").cursor!;
  const clickAt = click ? startAt + (click.t - (es.cursor ?? [])[0].t) / 1000 / speed : 1.2;
  const flip = ramp(t, clickAt + 0.05, clickAt + 0.85, easeInOut);
  const view: View = { x: 0, y: 0, w: 1920 };
  const showEs = flip >= 0.5;
  const angle = showEs ? (1 - flip) * 180 : -flip * 180;
  const pull = Math.sin(flip * Math.PI) * 0.08;
  return (
    <AbsoluteFill style={{ background: T.ink, perspective: 2600 }}>
      <AbsoluteFill style={{ transform: `rotateY(${angle}deg) scale(${1 - pull})`, backfaceVisibility: "hidden" }}>
        <CapturePlane name={showEs ? "card_es" : "card_en_top"} t={t} keys={[{ t: 0, view: { ...view } }, { t: 3.6, view: { x: 0, y: 0, w: 1820 } }]} box={{ w: W, h: H }} cursor={showEs ? undefined : { track: es.cursor ?? [], start: startAt, speed, until: clickAt + 0.2 }} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/** The weekly brief, as a printed sheet. */
export const Brief: React.FC = () => {
  const t = useT();
  const b = cap("brief");
  const sheetW = 1100;
  const sheetH = (sheetW * (b.height ?? b.viewport.height)) / b.viewport.width;
  const enter = easeOut(clamp01(t / 0.9));
  const pan = ramp(t, 0.6, 4.9);
  const y = lerp(H + 40, 70, enter) - pan * (sheetH - H + 140);
  return (
    <Ground>
      <div style={{ position: "absolute", left: (W - sheetW) / 2, top: y, width: sheetW, height: sheetH, transform: `rotate(${lerp(-2.5, 0, enter)}deg)`, boxShadow: "0 30px 80px rgba(0,0,0,0.55)", background: "#fff" }}>
        <Img src={staticFile(`captures/${b.file}`)} style={{ width: sheetW, height: sheetH }} />
      </div>
    </Ground>
  );
};

/** The same card on a phone. */
export const PhoneCard: React.FC = () => {
  const t = useT();
  const screenW = 430;
  const scroll = ramp(t, 0.7, 1.4);
  const rot = lerp(16, -6, easeOut(clamp01(t / 2.5)));
  const tapped = cap("m_map_tapped");
  const screenH = (screenW * 844) / 390;
  return (
    <Ground>
      <div style={{ position: "absolute", left: W / 2 - 250, top: (H - screenH * 1.09) / 2, perspective: 1800 }}>
        <div style={{ transform: `rotateY(${rot}deg) rotateZ(${rot * -0.08}deg)` }}>
          <Phone screenW={screenW}>
            <div style={{ position: "absolute", inset: 0, transform: `translateY(${-scroll * 20}px)` }}>
              <Img src={staticFile(`captures/${tapped.file}`)} style={{ position: "absolute", width: screenW, height: screenH, opacity: 1 - scroll }} />
              <Img src={staticFile(`captures/${cap("m_card").file}`)} style={{ position: "absolute", width: screenW, height: screenH, opacity: scroll }} />
            </div>
          </Phone>
        </div>
      </div>
    </Ground>
  );
};
