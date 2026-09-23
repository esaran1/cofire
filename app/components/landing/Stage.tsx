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
 * A Stage gives one figure the entire viewport. The claim is the headline, the
 * figure is the body, and nothing else is on screen. The reader arrives, reads
 * one thing, and scrolls to the next one.
 *
 * `min-h-[100dvh]` rather than `h-screen`, because the iOS address bar changes
 * the viewport height mid-scroll and `vh` does not follow it.
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
      className={`flex min-h-[100dvh] items-center border-t border-rule px-6 py-20 ${
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
