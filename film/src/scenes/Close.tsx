/**
 * The band's removal in the app (end of part 4), and part 5: the weekly
 * refresh, the forecast record, the seal, the open data, the live map and
 * the end card. App frames are captures of the production build.
 */
import { AbsoluteFill, Img, staticFile } from "remotion";
import { around, cap, CAPTURES, CapturePlane, rect, type Key } from "../components/Capture";
import { Phone } from "../components/Devices";
import { Label } from "../components/Type";
import { FONT, T } from "../theme";
import { shot } from "../data";
import { field } from "../trace";
import { MapAct } from "./MapAct";
import { clamp01, easeOut, inOut, lerp, ramp, useT } from "../util";

const W = 1920, H = 1080, A = W / H;

export const NoBandCard: React.FC = () => {
  const t = useT();
  const nb = cap("noband");
  const click = (nb.cursor ?? []).find((p) => p.click);
  const { start: startAt, speed } = shot("trust.card").cursor!;
  const clickAt = click ? startAt + (click.t - (nb.cursor ?? [])[0].t) / 1000 / speed : 1.4;
  const r = rect("noband", "reason");
  const keys: Key[] = [
    { t: 0, view: { x: 0, y: 40, w: 1300 } },
    { t: 3.6, view: around({ x: r.x - 10, y: r.y - 180, w: r.w + 20, h: r.h + 220 }, A, 0.1) },
  ];
  return <CapturePlane name="card_en_top" t={t} keys={keys} box={{ w: W, h: H }} crossTo={{ name: "noband", u: ramp(t, clickAt + 0.08, clickAt + 0.4) }} cursor={{ track: nb.cursor ?? [], start: startAt, speed, until: clickAt + 0.9 }} />;
};

export const NoBandReason: React.FC = () => {
  const t = useT();
  const r = rect("noband", "reason");
  const a = around({ x: r.x - 10, y: r.y - 180, w: r.w + 20, h: r.h + 220 }, A, 0.1);
  const b = around({ x: r.x - 6, y: r.y - 8, w: r.w + 12, h: r.h + 16 }, A, 0.08);
  return <CapturePlane name="noband" t={t} keys={[{ t: 0, view: a }, { t: 1.8, view: b }, { t: 3.7, view: { ...b, w: b.w * 0.96, x: b.x + 4 } }]} box={{ w: W, h: H }} />;
};

/** The map, issue after issue: what the weekly refresh adds. */
export const Weekly: React.FC = () => {
  const t = useT();
  const wk = cap("weekly") as unknown as { files: string[] };
  const files = wk.files;
  const dur = shot("close.weekly").end - shot("close.weekly").start;
  // Issue after issue, dissolving into each other over [0.3, dur - 0.5] s; scripts/audio.mjs ticks at the same moments.
  const f = Math.min(files.length - 1, Math.max(0, ((t - 0.3) / (dur - 0.8)) * files.length));
  const i = Math.min(files.length - 1, Math.floor(f));
  const frac = i >= files.length - 1 ? 0 : clamp01((f - i - 0.35) / 0.65);
  const view = { x: lerp(120, 300, t / dur), y: lerp(40, 110, t / dur), w: lerp(1780, 1560, t / dur) };
  const k = W / view.w;
  return (
    <AbsoluteFill style={{ background: T.ink, overflow: "hidden" }}>
      <div style={{ position: "absolute", width: 1920, height: 1080, transformOrigin: "0 0", transform: `translate(${-view.x * k}px, ${-view.y * k}px) scale(${k})` }}>
        <Img src={staticFile(`captures/${files[i]}`)} style={{ position: "absolute", width: 1920, height: 1080 }} />
        {frac > 0 ? <Img src={staticFile(`captures/${files[i + 1]}`)} style={{ position: "absolute", width: 1920, height: 1080, opacity: frac }} /> : null}
      </div>
    </AbsoluteFill>
  );
};

/** The forecast record, close enough to read: every issue's publish time and fingerprint. */
export const Record: React.FC = () => {
  const t = useT();
  const table = rect("scoreboard", "score-table");
  // The fingerprints themselves, and down the list; the next shot holds the seal notice above them.
  const keys: Key[] = [
    { t: 0, view: { x: table.x - 40, y: table.y - 90, w: table.w + 80 } },
    { t: 3.8, view: { x: table.x - 30, y: table.y + 230, w: table.w + 20 } },
  ];
  return <AbsoluteFill style={{ background: T.paper }}><CapturePlane name="scoreboard" t={t} keys={keys} box={{ w: W, h: H }} /></AbsoluteFill>;
};

/** The seal notice, then what will be scored. */
export const Seal: React.FC = () => {
  const t = useT();
  const r = rect("scoreboard", "score-seal");
  const a = around(r, A, 0.14);
  const b = around(r, A, 0.05);
  const list = { x: r.x - 30, y: r.y + r.h + 10, w: r.w + 60 };
  return <AbsoluteFill style={{ background: T.paper }}><CapturePlane name="scoreboard" t={t} keys={[{ t: 0, view: a }, { t: 2.6, view: b }, { t: 5.6, view: { ...list, y: list.y - 60 } }]} box={{ w: W, h: H }} /></AbsoluteFill>;
};

/** The open data page, when it has been captured (it ships with v1.3 stage 6). */
export const OpenData: React.FC<{ draft?: boolean }> = ({ draft = false }) => {
  const t = useT();
  if (!CAPTURES.datadict) {
    // The animatic may run before the page exists; a real render may not.
    if (draft) return <AbsoluteFill style={{ background: T.ink, justifyContent: "center", alignItems: "center" }}><Label size={40} color="rgba(244,242,236,0.6)">[animatic: open-data page not captured yet]</Label></AbsoluteFill>;
    throw new Error("capture 'datadict' is missing: the open-data page must exist and be captured before the film claims open data");
  }
  const latest = rect("datadict", "data-latest");
  const dict = rect("datadict", "data-dictionary");
  const a = { x: latest.x - 40, y: latest.y - 150, w: latest.w + 80 };
  const b = { x: dict.x - 40, y: dict.y - 40, w: dict.w + 80 };
  return <AbsoluteFill style={{ background: T.paper }}><CapturePlane name="datadict" t={t} keys={[{ t: 0, view: { ...a, y: a.y - 20 } }, { t: 1.8, view: a }, { t: 4.9, view: b }]} box={{ w: W, h: H }} /></AbsoluteFill>;
};

/** The finale: back to the map of the opening, at the latest issue, pulling back to all five areas. */
export const Final: React.FC = () => <MapAct W={W} H={H} finale />;

export const Wordmark: React.FC<{ size: number }> = ({ size }) => (
  <div style={{ fontFamily: FONT.serif, fontSize: size, letterSpacing: "0.01em", color: T.paper, lineHeight: 1 }}>
    CO<span style={{ fontStyle: "italic", color: T.emberBright }}>FIRE</span>
  </div>
);

export const EndCard: React.FC<{ portrait?: boolean; dur?: number }> = ({ portrait = false, dur = 3 }) => {
  const t = useT();
  const u = easeOut(clamp01(t / 0.45));
  return (
    <AbsoluteFill style={{ background: T.ink, justifyContent: "center", alignItems: "center" }}>
      <div style={{ textAlign: "center", transform: `translateY(${(1 - u) * 24}px)`, opacity: u }}>
        <Wordmark size={portrait ? 190 : 200} />
        <Label size={portrait ? 46 : 44} color="rgba(244,242,236,0.86)" style={{ marginTop: 34, fontFamily: FONT.serif, padding: "0 60px" }}>Calibrated odds for Denver, and for the water it depends on.</Label>
        <Label size={portrait ? 40 : 36} weight={500} style={{ marginTop: 34, fontFamily: FONT.mono, opacity: ramp(t, 0.5, 1.0) }}>{field("site_url")}</Label>
      </div>
      <div style={{ position: "absolute", left: 60, right: 60, bottom: portrait ? 120 : 54, textAlign: "center", opacity: inOut(t, 0.7, dur + 1) }}>
        <Label size={portrait ? 24 : 22} color="rgba(244,242,236,0.6)">Drought: U.S. Drought Monitor (NDMC, USDA, NOAA) · Fuel dryness: gridMET · Map data © OpenStreetMap contributors, © Protomaps</Label>
      </div>
    </AbsoluteFill>
  );
};

/** The vertical cut's product beat: pick, move in and tap, on a phone. */
export const PhoneFlow: React.FC = () => {
  const t = useT();
  const screenW = 760;
  const screenH = (screenW * 844) / 390;
  const f = cap("m_flyin");
  const frame = Math.max(0, (t - 2.6) * (f.fps ?? 60));
  const showFly = t >= 2.6 && t < 6.2;
  const tapped = t >= 6.2;
  const toCard = ramp(t, 7.4, 8.2);
  const enter = easeOut(clamp01(t / 0.9));
  const tapAge = t - 6.3;
  const tap = cap("m_map_tapped").cursor?.[0];
  return (
    <AbsoluteFill style={{ background: `radial-gradient(120% 80% at 50% 40%, #26282e 0%, ${T.ink} 65%)` }}>
      <div style={{ position: "absolute", left: (1080 - screenW * 1.09) / 2, top: lerp(1920, (1920 - screenH * 1.09) / 2, enter) }}>
        <Phone screenW={screenW}>
          <div style={{ position: "absolute", inset: 0 }}>
            {!showFly && !tapped ? <Img src={staticFile(`captures/${cap("m_pick").file}`)} style={{ position: "absolute", width: screenW, height: screenH }} /> : null}
            {showFly ? <Img src={staticFile(`captures/m_flyin/${String(Math.min((f.frames ?? 1) - 1, Math.round(frame))).padStart(4, "0")}.png`)} style={{ position: "absolute", width: screenW, height: screenH }} /> : null}
            {tapped ? (
              <>
                <Img src={staticFile(`captures/${cap("m_map_tapped").file}`)} style={{ position: "absolute", width: screenW, height: screenH, opacity: 1 - toCard }} />
                <Img src={staticFile(`captures/${cap("m_card").file}`)} style={{ position: "absolute", width: screenW, height: screenH, opacity: toCard }} />
              </>
            ) : null}
            {tap && tapAge > 0 && tapAge < 0.7 ? (
              <div style={{ position: "absolute", left: (tap.x / 390) * screenW - 40 - 50 * tapAge, top: (tap.y / 844) * screenH - 40 - 50 * tapAge, width: 80 + 100 * tapAge, height: 80 + 100 * tapAge, borderRadius: "50%", border: `4px solid ${T.emberBright}`, opacity: 1 - tapAge / 0.7 }} />
            ) : null}
          </div>
        </Phone>
      </div>
    </AbsoluteFill>
  );
};
