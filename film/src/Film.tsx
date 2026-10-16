/**
 * The whole film, laid out from script/timeline.json. Each shot is a
 * Sequence at its start time; a few scenes span more than one shot because
 * the picture is continuous across them (the map act, the control plot, the
 * coverage bars).
 */
import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import { shot, TIMELINE } from "./data";
import { Guard } from "./Guard";
import { MapAct } from "./scenes/MapAct";
import { Brief, CardRows, FlyIn, Frequency, Icons, LaptopIntro, PhoneCard, Pick, Spanish, Tap, Watershed, Weeks } from "./scenes/Product";
import { Collapse, Control, Freeze, Leak, Looks, Ranges, TrustTitle } from "./scenes/Trust";
import { EndCard, Final, NoBandCard, NoBandReason, OpenData, PhoneFlow, Record, Seal, Weekly } from "./scenes/Close";
import { Label } from "./components/Type";
import { T } from "./theme";

export type FilmProps = { draft?: boolean; scratch?: boolean };

/** One Sequence from the start of `from` to the end of `to` (shot ids). */
const S: React.FC<{ from: string; to?: string; children: React.ReactNode }> = ({ from, to, children }) => {
  const { fps } = useVideoConfig();
  const a = shot(from).start, b = shot(to ?? from).end;
  return <Sequence from={Math.round(a * fps)} durationInFrames={Math.round((b - a) * fps)} name={to ? `${from} to ${to}` : from}>{children}</Sequence>;
};

export const Scratch: React.FC = () => (
  <div style={{ position: "absolute", right: 28, top: 22, padding: "6px 12px", borderRadius: 3, background: "rgba(23,24,27,0.72)" }}>
    <Label size={18} color="rgba(244,242,236,0.8)">Scratch voice (macOS say): draft</Label>
  </div>
);

export const Film: React.FC<FilmProps> = ({ draft = false, scratch = false }) => (
  <Guard name="Film">
    <AbsoluteFill style={{ background: T.ink }}>
      <S from="cold.wide" to="problem.threat"><MapAct W={1920} H={1080} /></S>
      <S from="product.laptop"><LaptopIntro /></S>
      <S from="product.pick"><Pick /></S>
      <S from="product.flyin"><FlyIn /></S>
      <S from="product.tap"><Tap /></S>
      <S from="product.card"><CardRows /></S>
      <S from="product.freq"><Frequency /></S>
      <S from="product.icons"><Icons /></S>
      <S from="product.weeks"><Weeks part={1} /></S>
      <S from="product.weeks2"><Weeks part={2} /></S>
      <S from="product.ws"><Watershed part={1} /></S>
      <S from="product.ws2"><Watershed part={2} /></S>
      <S from="product.es"><Spanish /></S>
      <S from="product.brief"><Brief /></S>
      <S from="product.phone"><PhoneCard /></S>
      <S from="trust.title"><TrustTitle /></S>
      <S from="trust.freeze"><Freeze /></S>
      <S from="trust.looks"><Looks /></S>
      <S from="trust.dots" to="trust.survivors"><Control /></S>
      <S from="trust.ranges" to="trust.perfect"><Ranges /></S>
      <S from="trust.leak" to="trust.delay"><Leak /></S>
      <S from="trust.collapse" to="trust.27"><Collapse /></S>
      <S from="trust.card"><NoBandCard /></S>
      <S from="trust.reason"><NoBandReason /></S>
      <S from="close.weekly"><Weekly /></S>
      <S from="close.record"><Record /></S>
      <S from="close.seal"><Seal /></S>
      <S from="close.data"><OpenData draft={draft} /></S>
      <S from="close.final"><Final /></S>
      <S from="close.end"><EndCard /></S>
      {scratch ? <Scratch /> : null}
    </AbsoluteFill>
  </Guard>
);

/** One part of the film, for rendering the film in pieces (scripts/render.mjs). */
export const PartView: React.FC<FilmProps & { part: string }> = ({ part, ...props }) => {
  const { fps } = useVideoConfig();
  const p = TIMELINE.parts.find((x) => x.id === part);
  if (!p) throw new Error(`no part ${part}`);
  return (
    <Sequence from={-Math.round(p.start * fps)} name={part}>
      <Film {...props} />
    </Sequence>
  );
};

/** The vertical cut: the first 45 seconds, laid out for a phone screen. */
export const Vertical: React.FC<FilmProps> = ({ scratch = false }) => {
  const { fps } = useVideoConfig();
  const f = (s: number) => Math.round(s * fps);
  return (
    <Guard name="Vertical">
      <AbsoluteFill style={{ background: T.ink }}>
        <Sequence from={0} durationInFrames={f(33)} name="map"><MapAct W={1080} H={1920} /></Sequence>
        <Sequence from={f(33)} durationInFrames={f(9.3)} name="phone"><PhoneFlow /></Sequence>
        <Sequence from={f(42.3)} durationInFrames={f(2.7)} name="end"><EndCard portrait dur={2.7} /></Sequence>
        {scratch ? <Scratch /> : null}
      </AbsoluteFill>
    </Guard>
  );
};
