import { useLayoutEffect, useRef } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { assertTraced } from "./trace";

/** Wraps a composition and checks every frame for untraced numbers (see trace.ts). */
export const Guard: React.FC<{ children: React.ReactNode; name: string }> = ({ children, name }) => {
  const ref = useRef<HTMLDivElement>(null);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  useLayoutEffect(() => {
    if (ref.current) assertTraced(ref.current, `${name} frame ${frame} (${(frame / fps).toFixed(2)} s)`);
  });
  return <AbsoluteFill ref={ref}>{children}</AbsoluteFill>;
};
