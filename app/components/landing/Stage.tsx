"use client";

import { ReactNode } from "react";

/**
 * One figure, one screen.
 *
 * The evidence sections used to stack two charts inside a single scrolling
 * section, each squeezed into a column beside its own caption. Two figures
 * competing in one viewport means neither is read: the eye has to choose, and
 * the charts are the whole argument.
 *
 * A Stage gives one figure its own section. The claim is the headline, the
 * figure is the body, and nothing else competes with it. The reader arrives,
 * reads one thing, and scrolls to the next one.
 *
 * Generous, equal padding sets it apart. A full-viewport minimum used to centre
 * a short figure (the three-bar drift chart) in a screen of blank paper.
 */
export function Stage({
  claim,
  detail,
  children,
  tinted = false,
}: {
  /** The single sentence this screen exists to make. */
  claim: ReactNode;
  /** One line of support, at most. Optional. */
  detail?: ReactNode;
  children: ReactNode;
  tinted?: boolean;
}) {
  return (
    <section
      className={`border-t border-rule px-6 py-24 md:py-32 ${
        tinted ? "bg-paper-sunk" : ""
      }`}
    >
      <div className="measure w-full">
        <div className="reveal">
          <h3 className="display max-w-[24ch] text-3xl leading-[1.15] [text-wrap:balance] md:text-5xl">{claim}</h3>
          {detail ? (
            <p className="text-ink-soft mt-4 max-w-[52ch] text-base leading-relaxed md:text-lg">
              {detail}
            </p>
          ) : null}
        </div>
        <div className="mt-12 md:mt-16">{children}</div>
      </div>
    </section>
  );
}
