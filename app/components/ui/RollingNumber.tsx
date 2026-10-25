"use client";

import { useEffect, useRef } from "react";

/**
 * A figure whose changed digits roll into place when it updates.
 *
 * When the reader switches horizon or issue, the dryness figure and the odds
 * change; without a cue, a change from 61% to 64% is easy to miss. Only the
 * characters that changed move, counted from the right so "8%" to "12%" lines
 * up by place value.
 *
 * Plain CSS (`.digit-roll` in globals.css), so the map page still loads no
 * animation library. The text content is always exactly the value shown, for
 * screen readers and tests. Nothing moves on first render, and the global
 * reduced-motion rule stops the roll for readers who asked for no motion.
 */
export function RollingNumber({ value }: { value: string }) {
  const prev = useRef<string | null>(null);
  const before = prev.current;
  useEffect(() => {
    prev.current = value;
  }, [value]);

  const chars = [...value];
  const old = before === null ? null : [...before];
  return (
    <>
      {chars.map((ch, i) => {
        const fromRight = chars.length - i;
        const was = old ? old[old.length - fromRight] : ch;
        const changed = old !== null && was !== ch;
        // The key carries the character, so a changed digit is a new element
        // and its roll-in animation runs once; an unchanged one stays put.
        return (
          <span key={`${fromRight}:${ch}`} className={changed ? "digit-roll" : undefined}>
            {ch}
          </span>
        );
      })}
    </>
  );
}
