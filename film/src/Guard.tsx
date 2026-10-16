import { useLayoutEffect, useRef } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { assertTraced } from "./trace";

const MIN_PX = 18; // smallest type the film may set, before any camera zoom

/** Fail on text set smaller than MIN_PX: it would not be readable on a phone at 30 fps. */
function assertReadable(root: HTMLElement, where: string): void {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!n.textContent?.trim() || !n.parentElement) continue;
    const st = getComputedStyle(n.parentElement);
    if (st.opacity === "0" || st.visibility === "hidden") continue;
    const px = parseFloat(st.fontSize);
    if (px < MIN_PX) throw new Error(`Text "${n.textContent.trim().slice(0, 40)}" is ${px}px at ${where}; the film's minimum is ${MIN_PX}px.`);
  }
}

/** Wraps a composition and checks every frame: no untraced number (trace.ts), no text too small to read. */
export const Guard: React.FC<{ children: React.ReactNode; name: string }> = ({ children, name }) => {
  const ref = useRef<HTMLDivElement>(null);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  useLayoutEffect(() => {
    if (!ref.current) return;
    const where = `${name} frame ${frame} (${(frame / fps).toFixed(2)} s)`;
    assertTraced(ref.current, where);
    assertReadable(ref.current, where);
  });
  return <AbsoluteFill ref={ref}>{children}</AbsoluteFill>;
};
