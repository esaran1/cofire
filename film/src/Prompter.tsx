/**
 * A prompter for recording the narration in time with the film (see
 * RECORDING_GUIDE.md). Not part of the film: the current line large, the next
 * one dim, a bar showing how much of the line's slot is left, and a count-in
 * before each line. The film's picture plays small in the corner.
 */
import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import { DATA, NARRATION, TIMELINE } from "./data";
import { Film } from "./Film";
import { FONT, T } from "./theme";
import { useT } from "./util";

const fillText = (tpl: string) => tpl.replace(/\{([a-z0-9_]+)\}/g, (_, k: string) => DATA.fields[k]?.en ?? `{${k}}`);

export const Prompter: React.FC = () => {
  const t = useT();
  const { fps } = useVideoConfig();
  const lines = NARRATION.lines;
  const i = lines.findIndex((l, k) => t >= l.start - 1.5 && t < (lines[k + 1]?.start ?? TIMELINE.duration) - 1.5);
  const cur = i >= 0 ? lines[i] : null;
  const next = i >= 0 ? lines[i + 1] : lines[0];
  const end = cur ? (lines[i + 1]?.start ?? TIMELINE.duration - 1) : 0;
  const speaking = cur && t >= cur.start;
  const count = cur && !speaking ? Math.ceil(cur.start - t) : null;
  return (
    <AbsoluteFill style={{ background: "#0f1012", color: T.paper, fontFamily: FONT.sans }}>
      <div style={{ position: "absolute", left: 60, top: 40, fontFamily: FONT.mono, fontSize: 26, opacity: 0.7 }}>
        {Math.floor(t / 60)}:{(t % 60).toFixed(1).padStart(4, "0")} {cur ? `· line ${cur.id} of ${lines.length}` : ""}
      </div>
      <div style={{ position: "absolute", left: 60, right: 520, top: 150 }}>
        {cur ? <div style={{ fontSize: 56, lineHeight: 1.25, color: speaking ? T.paper : "rgba(244,242,236,0.6)" }}>{fillText(cur.en)}</div> : <div style={{ fontSize: 40, opacity: 0.5 }}>(music only)</div>}
        {count !== null ? <div style={{ marginTop: 30, fontSize: 40, color: T.emberBright, fontFamily: FONT.mono }}>{count}…</div> : null}
        {speaking && cur ? (
          <div style={{ marginTop: 40, height: 10, width: 640, background: "rgba(244,242,236,0.15)", borderRadius: 5 }}>
            <div style={{ height: 10, width: `${Math.min(100, ((t - cur.start) / (end - cur.start)) * 100)}%`, background: T.emberBright, borderRadius: 5 }} />
          </div>
        ) : null}
        {next ? <div style={{ marginTop: 60, fontSize: 32, lineHeight: 1.3, opacity: 0.4 }}>Next: {fillText(next.en)}</div> : null}
      </div>
      <div style={{ position: "absolute", right: 40, bottom: 40, width: 440, height: 248, overflow: "hidden", borderRadius: 4, border: "1px solid rgba(244,242,236,0.2)" }}>
        <div style={{ width: 1920, height: 1080, transform: "scale(0.229)", transformOrigin: "0 0" }}>
          <Sequence from={0} durationInFrames={Math.round(TIMELINE.duration * fps)}>
            <Film draft />
          </Sequence>
        </div>
      </div>
    </AbsoluteFill>
  );
};
