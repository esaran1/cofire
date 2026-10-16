/**
 * Compositions. Everything is timed in seconds, so one film renders at any
 * frame rate:
 *   Film      1920x1080, 60 fps, the master (rendered in parts P1 to P5)
 *   P1 to P5  the master's parts, for split rendering (scripts/render.mjs)
 *   Animatic  the same film at 15 fps, rendered small, with draft stand-ins
 *   Vertical  1080x1920, 30 fps, the first 45 seconds for phones
 *   Prompter  a recording aid, not the film (RECORDING_GUIDE.md)
 */
import { Composition } from "remotion";
import { TIMELINE } from "./data";
import { Film, PartView, Vertical, type FilmProps } from "./Film";
import { loadFonts } from "./fonts";
import { Prompter } from "./Prompter";

loadFonts();

const MASTER_FPS = 60;
const total = TIMELINE.duration;
if (total > 180) throw new Error(`the film is ${total} s; it must not run over 3:00`);
if (total < 150 || total > 175) throw new Error(`the film is ${total} s; the target is 2:30 to 2:55`);

const defaults: FilmProps = { draft: false, scratch: false };

export const Root: React.FC = () => (
  <>
    <Composition id="Film" component={Film} durationInFrames={Math.round(total * MASTER_FPS)} fps={MASTER_FPS} width={1920} height={1080} defaultProps={defaults} />
    {TIMELINE.parts.map((p) => (
      <Composition key={p.id} id={p.id} component={PartView} durationInFrames={Math.round((p.end - p.start) * MASTER_FPS)} fps={MASTER_FPS} width={1920} height={1080} defaultProps={{ ...defaults, part: p.id }} />
    ))}
    <Composition id="Animatic" component={Film} durationInFrames={Math.round(total * 15)} fps={15} width={1920} height={1080} defaultProps={{ draft: true, scratch: true }} />
    <Composition id="Prompter" component={Prompter} durationInFrames={Math.round(total * 15)} fps={15} width={1280} height={720} />
    <Composition id="Vertical" component={Vertical} durationInFrames={Math.round(TIMELINE.vertical_duration * 30)} fps={30} width={1080} height={1920} defaultProps={defaults} />
  </>
);
