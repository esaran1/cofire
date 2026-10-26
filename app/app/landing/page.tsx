"use client";

import Link from "next/link";
import { asset } from "@/lib/asset";
import { motion, useScroll, useTransform } from "motion/react";
import { usePrefersReducedMotion, useReduceMotion } from "@/lib/motion";
import { useRef } from "react";
import { ArrowRight } from "@phosphor-icons/react";
import { PidVsAciFigure, ReliabilityFigure } from "@/components/landing/PidFigure";
import { ActPreviews } from "@/components/landing/ActPreviews";
import { CardPair } from "@/components/landing/CardPair";
import { SealedTimeline } from "@/components/landing/SealedTimeline";
import { Stage } from "@/components/landing/Stage";
import { StoryMap } from "@/components/landing/StoryMap";
import { ReadingProgress, RecedingHero, ZoomIn } from "@/components/landing/Scroll";
import { Letters, Magnetic, RollText, ScrollWords } from "@/components/landing/Flourish";
import { HeroField } from "@/components/landing/HeroField";
import facts from "@/lib/facts.json";
import { useT } from "@/lib/i18n";

export default function LandingPage() {
  const reduce = useReduceMotion();
  const instant = usePrefersReducedMotion();
  const { t } = useT();
  const look = facts.look3;
  const audit = facts.interval_audit;

  return (
    <>
      <ReadingProgress />

      {/* 1. Hero. Centered is allowed here: this is a launch statement and the
          message is the design (skill 4.3 override). It recedes on scroll so
          the first section arrives over it. */}
      <RecedingHero backdrop={<HeroField />}>
        <h1 className="display text-[clamp(3.5rem,11vw,11rem)] leading-[0.95]">
          <Letters plain="CO" em="FIRE" />
        </h1>
        <motion.p
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={instant ? { duration: 0 } : { duration: 0.8, delay: 0.25 }}
          className="mt-6 text-[clamp(0.7rem,0.85vw,0.95rem)] uppercase tracking-[0.2em] text-mute sm:rule-flank sm:tracking-[0.24em]"
        >
          <span className="sm:hidden">{t("land.tagShort")}</span>
          <span className="hidden sm:inline">{t("land.tagLong")}</span>
        </motion.p>
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={instant ? { duration: 0 } : { duration: 0.7, delay: 0.4 }}
          className="mt-12 flex flex-wrap items-center justify-center gap-3"
        >
          <Magnetic>
            <Link
              href="/"
              className="group inline-flex items-center gap-2 rounded-full bg-spruce px-6 py-3 font-medium text-paper transition-[transform,background-color] hover:bg-spruce-deep active:scale-[0.98]"
            >
              <RollText>{t("nav.openMap")}</RollText>
              <ArrowRight size={17} weight="bold" className="transition-transform duration-300 group-hover:translate-x-0.5" />
            </Link>
          </Magnetic>
        </motion.div>
      </RecedingHero>

      {/* 2. The premise, carried by the one real photograph. */}
      <PhotoChapter
        src={asset("/img/hero-highpark.jpg")}
        alt={t("land.photoAlt")}
        credit={
          <>
            {t("land.photoCredit")}{" "}
            <a className="underline" href="https://creativecommons.org/licenses/by/2.0/">
              CC BY 2.0
            </a>
            {t("land.via")}{" "}
            <a
              className="underline"
              href="https://commons.wikimedia.org/wiki/File:High_Park_fire_near_Poudre_Canyon,_Colorado.jpg"
            >
              Wikimedia Commons
            </a>
            .
          </>
        }
      >
        <h2 className="display text-paper max-w-[16ch] text-5xl md:text-7xl">
          {t("land.dries1")} <em className="text-paper">{t("land.driesEm")}</em> {t("land.dries2")}
        </h2>
        <p className="text-paper/80 mt-5 max-w-[40ch] text-lg leading-relaxed md:text-xl">
          {t("land.window")}
        </p>
      </PhotoChapter>

      {/* 3. What COFIRE does, shown as the forecast itself. */}
      <section className="border-t border-rule px-6 py-24 md:py-32">
        <div className="measure w-full">
          <ZoomIn>
            <StoryMap
              title={<>{t("land.forecasts")}</>}
              line={<>{t("land.every", { km: facts.resolution_m / 1000 })}</>}
            />
          </ZoomIn>
        </div>
      </section>

      {/* 4. The idea of the app, shown through the app. */}
      <Chapter
        tinted
        title={
          <ScrollWords
            segments={[{ text: t("land.trust1") }, { text: t("land.trustEm"), em: true }, { text: ".", join: true }]}
          />
        }
      >
        <ZoomIn>
          <CardPair />
        </ZoomIn>
      </Chapter>

      {/* 5. The discipline behind the claim. */}
      <Chapter
        title={<ScrollWords segments={[{ text: t("land.locked") }]} />}
        line={<>{t("land.lockedLine")}</>}
      >
        <SealedTimeline />
      </Chapter>

      {/* 6. The correction. The interval test as it was run, against the same
          test with the delay a real forecaster faces. */}
      <Stage
        tinted
        claim={<ScrollWords segments={[{ text: t("land.flaw") }]} />}
        detail={
          <>
            {t("land.flawDetail1")}{" "}
            <span className="num text-ember">{audit.real_time_roll13_min?.toFixed(2)}</span>
            {t("land.flawDetail2")}
          </>
        }
      >
        <PidVsAciFigure
          rows={[...audit.as_tested.map((r) => ({ ...r, impl: "reference_pid" })), ...audit.real_time.map((r) => ({ ...r, impl: "aci" }))]}
          floor={0}
          target={0.7}
          caption={t("land.flawCaption")}
        />
      </Stage>

      {/* 7. Where it fell short, and what the app did about it. */}
      <Stage
        claim={<ScrollWords segments={[{ text: t("land.drift") }]} />}
        detail={<>{t("land.driftDetail", { n: look.by_test["5"].n_total - look.by_test["5"].n_pass })}</>}
      >
        <ReliabilityFigure
          byHorizon={look.reliability_by_horizon}
          caption={t("land.driftCaption")}
        />
      </Stage>

      {/* 8. What to do with it. */}
      <Chapter tinted title={<>{t("land.act")}</>}>
        <ActPreviews />
      </Chapter>

      {/* 7. Close. */}
      <section className="border-t border-rule bg-ink px-6 py-20 text-paper">
        <div className="measure">
          <p className="display max-w-[20ch] text-4xl md:text-6xl">
            <ScrollWords tone="dark" segments={[{ text: t("land.see") }]} />
          </p>
          <div className="mt-10">
            <Magnetic>
              <Link
                href="/"
                className="group inline-flex items-center gap-2 rounded-full bg-paper px-6 py-3 font-medium text-ink transition-[transform,background-color] hover:bg-paper-raised active:scale-[0.98]"
              >
                <RollText>{t("nav.openMap")}</RollText>
                <ArrowRight size={17} weight="bold" className="transition-transform duration-300 group-hover:translate-x-0.5" />
              </Link>
            </Magnetic>
          </div>
        </div>
      </section>
    </>
  );
}

/**
 * One chapter of the story: a headline, at most one line, then the picture.
 *
 * Each chapter is one idea, set off by generous, equal padding. They used to
 * take a full screen each and centre their content, which left a short chapter
 * (the sealed-year bar) floating in 400 to 500 px of blank paper; equal padding
 * keeps one idea at a time without the dead air.
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
      className={`border-t border-rule px-6 py-24 md:py-32 ${
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
  credit: React.ReactNode;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReduceMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], ["-6%", "6%"]);
  // The photograph arrives as a framed plate and opens to the full width as
  // its section rises into view: the calm of the title gives way to the fire.
  // It is fully open by the time the headline is in the reading zone.
  const enter = useScroll({ target: ref, offset: ["start end", "start 0.25"] }).scrollYProgress;
  const inset = useTransform(enter, [0, 1], [7, 0]);
  const clipPath = useTransform(inset, (v) => `inset(${v}% ${v * 0.75}% ${v}% ${v * 0.75}% round ${v > 0.2 ? 2 : 0}px)`);
  return (
    <section ref={ref} className="relative flex min-h-[100dvh] items-end overflow-hidden bg-paper">
      <motion.div className="absolute inset-0 overflow-hidden bg-ink" style={reduce ? undefined : { clipPath }}>
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
      </motion.div>
      <div className="measure relative w-full px-6 pb-20 md:pb-28">
        <div className="reveal">{children}</div>
        <p className="text-paper/55 mt-12 text-xs">{credit}</p>
      </div>
    </section>
  );
}
