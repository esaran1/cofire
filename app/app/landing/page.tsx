"use client";

import Link from "next/link";
import { asset } from "@/lib/asset";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";
import { ArrowRight } from "@phosphor-icons/react";
import { PidVsAciFigure, ReliabilityFigure } from "@/components/landing/PidFigure";
import { ActPreviews } from "@/components/landing/ActPreviews";
import { CardPair } from "@/components/landing/CardPair";
import { SealedTimeline } from "@/components/landing/SealedTimeline";
import { Stage } from "@/components/landing/Stage";
import { StoryMap } from "@/components/landing/StoryMap";
import { LineReveal, ReadingProgress, RecedingHero } from "@/components/landing/Scroll";
import facts from "@/lib/facts.json";

export default function LandingPage() {
  const reduce = useReducedMotion();
  const look = facts.look3;
  const audit = facts.interval_audit;

  return (
    <>
      <ReadingProgress />

      {/* 1. Hero. Centered is allowed here: this is a launch statement and the
          message is the design (skill 4.3 override). It recedes on scroll so
          the first section arrives over it. */}
      <RecedingHero>
        <motion.h1
          initial={reduce ? false : { opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="display text-[clamp(3.5rem,11vw,11rem)] leading-[0.95]"
        >
          CO<em>FIRE</em>
        </motion.h1>
        <motion.p
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.25 }}
          className="mt-6 text-[clamp(0.7rem,0.85vw,0.95rem)] uppercase tracking-[0.2em] text-mute sm:rule-flank sm:tracking-[0.24em]"
        >
          <span className="sm:hidden">Drought and fire-spread conditions</span>
          <span className="hidden sm:inline">Colorado drought and fire-spread conditions</span>
        </motion.p>
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.4 }}
          className="mt-12 flex flex-wrap items-center justify-center gap-3"
        >
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-full bg-ember px-6 py-3 font-medium text-paper transition-transform active:scale-[0.98]"
          >
            Open the map
            <ArrowRight size={17} weight="bold" />
          </Link>
        </motion.div>
      </RecedingHero>

      {/* 2. The premise, carried by the one real photograph. */}
      <PhotoChapter
        src={asset("/img/hero-highpark.jpg")}
        alt="The sun seen through heavy smoke from the High Park Fire above Poudre Canyon, Colorado"
        credit="High Park Fire above Poudre Canyon. Photo CC BY 2.0 via Wikimedia Commons."
      >
        <h2 className="display text-paper max-w-[16ch] text-5xl md:text-7xl">
          Colorado dries out weeks <em className="text-paper">before</em> it burns.
        </h2>
        <p className="text-paper/80 mt-5 max-w-[40ch] text-lg leading-relaxed md:text-xl">
          Soil dries and fuels cure long before anything ignites. That is the window to act.
        </p>
      </PhotoChapter>

      {/* 3. What COFIRE does, shown as the forecast itself. */}
      <section className="flex min-h-[100dvh] items-center border-t border-rule px-6 py-20">
        <div className="measure w-full">
          <StoryMap
            title={<>COFIRE forecasts that window.</>}
            line={
              <>
                Every <span className="num">{facts.resolution_m / 1000}</span> km of Denver, the
                watersheds its water comes from, and two more Colorado counties, 2 to 8 weeks ahead.
              </>
            }
          />
        </div>
      </section>

      {/* 4. The idea of the app, shown through the app. */}
      <Chapter
        tinted
        title={
          <>
            Most forecasts show a number. This one says when the number{" "}
            <em>cannot be trusted</em>.
          </>
        }
      >
        <CardPair />
      </Chapter>

      {/* 5. The discipline behind the claim. */}
      <Chapter
        title={<>Then we locked a year away.</>}
        line={<>Every method was chosen and frozen before 2026 was opened, once.</>}
      >
        <SealedTimeline />
      </Chapter>

      {/* 6. The correction. The interval test as it was run, against the same
          test with the delay a real forecaster faces. */}
      <Stage
        tinted
        claim={<>Then we found a flaw in our own test.</>}
        detail={
          <>
            The range test used outcomes a real forecast would not have yet. With the real delay, its
            worst stretch fell to{" "}
            <span className="num text-ember">{audit.real_time_roll13_min?.toFixed(2)}</span>. So the
            app draws no range rather than a wrong one.
          </>
        }
      >
        <PidVsAciFigure
          rows={[...audit.as_tested.map((r) => ({ ...r, impl: "reference_pid" })), ...audit.real_time.map((r) => ({ ...r, impl: "aci" }))]}
          floor={0}
          target={0.7}
          caption="Worst 13-week coverage on 2022 to 2025, the years before the sealed one. Dark is the test as it was run; pale is the same test with the real delay of 2 to 8 weeks before an outcome is known. The dashed line is the 0.70 floor set in advance."
        />
      </Stage>

      {/* 7. Where it fell short, and what the app did about it. */}
      <Stage
        claim={<>Past two weeks, the odds drifted.</>}
        detail={
          <>
            So those{" "}
            <span className="num text-ink">
              {look.by_test["5"].n_total - look.by_test["5"].n_pass}
            </span>{" "}
            forecasts now show one county-wide rate instead of a number per cell.
          </>
        }
      >
        <ReliabilityFigure
          byHorizon={look.reliability_by_horizon}
          caption="How far the stated odds drifted from what actually happened in 2026, lower is better. The dashed line is the limit set before the year was opened."
        />
      </Stage>

      {/* 8. What to do with it. */}
      <Chapter tinted title={<>Then do something about it.</>}>
        <ActPreviews />
      </Chapter>

      {/* 7. Close. */}
      <section className="border-t border-rule bg-ink px-6 py-20 text-paper">
        <div className="measure">
          <LineReveal
            className="display max-w-[20ch] text-4xl text-paper md:text-6xl"
            lines={[<>See your area.</>]}
          />
          <Link
            href="/"
            className="mt-10 inline-flex items-center gap-2 rounded-full bg-ember px-6 py-3 font-medium text-paper transition-transform active:scale-[0.98]"
          >
            Open the map
            <ArrowRight size={17} weight="bold" />
          </Link>
        </div>
      </section>
    </>
  );
}

/**
 * One chapter of the story: a headline, at most one line, then the picture.
 *
 * Each chapter takes at least a full screen so the reader meets one idea at a
 * time. `min-h-[100dvh]`, not `h-screen`, because the mobile address bar
 * changes the viewport height mid-scroll.
 */
function Chapter({
  title,
  line,
  tinted = false,
  children,
}: {
  title: React.ReactNode;
  line?: React.ReactNode;
  tinted?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      className={`flex min-h-[100dvh] items-center border-t border-rule px-6 py-24 ${
        tinted ? "bg-paper-sunk" : ""
      }`}
    >
      <div className="measure w-full">
        <div className="reveal">
          <h2 className="display max-w-[22ch] text-4xl leading-[1.12] [text-wrap:balance] md:text-6xl">{title}</h2>
          {line ? (
            <p className="text-ink-soft mt-5 max-w-[48ch] text-lg leading-relaxed md:text-xl">
              {line}
            </p>
          ) : null}
        </div>
        <div className="mt-14 md:mt-20">{children}</div>
      </div>
    </section>
  );
}

/**
 * The photograph as the whole screen, with the premise set on it.
 *
 * The image moves slightly slower than the page for depth. That parallax
 * animates position only, starting from rest, so the photograph is always
 * visible whether or not the animation runs.
 */
function PhotoChapter({
  src,
  alt,
  credit,
  children,
}: {
  src: string;
  alt: string;
  credit: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], ["-6%", "6%"]);
  return (
    <section ref={ref} className="relative flex min-h-[100dvh] items-end overflow-hidden bg-ink">
      <motion.img
        src={src}
        alt={alt}
        style={reduce ? undefined : { y, scale: 1.14 }}
        className="absolute inset-0 h-full w-full object-cover"
      />
      {/* Scrim so the headline passes contrast over any part of the photo. */}
      <div
        className="absolute inset-0 bg-gradient-to-t from-ink/85 via-ink/35 to-transparent"
        aria-hidden
      />
      <div className="measure relative w-full px-6 pb-20 md:pb-28">
        <div className="reveal">{children}</div>
        <p className="text-paper/55 mt-12 text-xs">{credit}</p>
      </div>
    </section>
  );
}
