"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight } from "@phosphor-icons/react";
import { PidVsAciFigure, ReliabilityFigure } from "@/components/landing/PidFigure";
import { LineReveal, ParallaxFigure, ReadingProgress, RecedingHero, Reveal } from "@/components/landing/Scroll";
import { Numeral } from "@/components/ui/Controls";
import facts from "@/lib/facts.json";

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : `${(v * 100).toFixed(1)}%`);

export default function LandingPage() {
  const reduce = useReducedMotion();
  const look = facts.look3;
  const informative = facts.stage_ab.classification.filter((c) => c.classification === "informative");
  const survivors = facts.survivors;

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
          className="display text-6xl md:text-8xl"
        >
          CO<em>FIRE</em>
        </motion.h1>
        <motion.p
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.25 }}
          className="mt-6 text-[11px] uppercase tracking-[0.2em] text-mute sm:rule-flank sm:tracking-[0.24em]"
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

      {/* 2. The claim, as a display statement. */}
      <Section n="01" title="The idea">
        <LineReveal
          className="display max-w-[22ch] text-4xl md:text-6xl"
          lines={[<>Colorado dries out weeks</>, <><em>before</em> it burns.</>]}
        />
        <div className="mt-10 grid gap-10 md:grid-cols-2">
          <p className="max-w-prose leading-relaxed text-ink-soft">
            Fire-spread conditions build slowly. Soil moisture falls, fuels cure, and the energy
            available to a fire climbs for weeks before anything ignites. That window is when a
            county can still act, and it is the window this forecasts.
          </p>
          <p className="max-w-prose leading-relaxed text-ink-soft">
            COFIRE forecasts drought severity and fire-spread conditions 2 to 8 weeks ahead on
            4&nbsp;km cells, then does the part most forecasts skip: it measures whether its own
            uncertainty holds, and says so when it does not.
          </p>
        </div>
      </Section>

      {/* 3. Full-bleed photograph. Different layout family from every other section. */}
      <ParallaxFigure
        src="/img/hero-highpark.jpg"
        alt="The sun seen through heavy smoke from the High Park Fire above Poudre Canyon, Colorado"
        caption="High Park Fire above Poudre Canyon. Photo CC BY 2.0 via Wikimedia Commons."
      />

      {/* 4. What you do with it. Asymmetric trio, no equal cards. */}
      <Section n="02" title="What it does">
        {/* Asymmetric trio: the lead action gets the weight, the other two
            stack beside it. Not three equal cards. */}
        <div className="grid gap-px overflow-hidden rounded border border-rule bg-rule lg:grid-cols-5">
          <Act
            k="Harden"
            body="Turn a bad outlook into a weighted checklist for your own property. Fifteen actions, each scored by how much it cuts ember ignition risk, sourced from IBHS field research."
            href="/ember"
            className="lg:col-span-3 lg:p-12"
            large
          />
          <div className="grid gap-px bg-rule lg:col-span-2">
            <Act
              k="Predict"
              body="Lock your own call on a cell before the model shows its own."
              href="/beat"
            />
            <Act
              k="Observe"
              body="Report a dry stock tank or a crisp lawn. Ground truth from the people who live on the cell."
              href="/observe"
            />
          </div>
        </div>
      </Section>

      {/* 5. The calibration story: ACI collapsed on the sealed year, PID held. */}
      <Section n="03" title="The honest part" tinted>
        <LineReveal
          className="display max-w-[24ch] text-4xl md:text-6xl"
          lines={[<>Most forecasts show a number.</>, <>This one says when the number</>, <><em>cannot be trusted</em>.</>]}
        />

        <div className="mt-12 space-y-14">
          <div className="grid gap-8 lg:grid-cols-[minmax(0,26rem)_1fr] lg:items-start lg:gap-16">
            <div>
              <h3 className="font-medium">One controller held its coverage. The other did not.</h3>
              <p className="mt-3 leading-relaxed text-ink-soft">
                An interval is only worth drawing if it contains the truth as often as it claims. On
                the sealed 2026 year the adaptive method fell to{" "}
                <span className="num text-ink">{look.aci.roll13_min.toFixed(3)}</span> coverage over
                its worst thirteen weeks and was wrong{" "}
                <span className="num text-ink">{look.aci.miss_run_max}</span> cell-weeks in a row.
                The reference conformal PID controller, on the same rows, never fell below{" "}
                <span className="num text-ink">{look.pid.roll13_min.toFixed(3)}</span> and was never
                wrong more than <span className="num text-ink">{look.pid.miss_run_max}</span> in a
                row.
              </p>
              <p className="mt-4 leading-relaxed text-ink-soft">
                Every interval test written down before the look passed, on both counties and all
                three ranges.
              </p>
            </div>
            <PidVsAciFigure rows={look.coverage_series} />
          </div>

          <div className="grid gap-8 lg:grid-cols-[minmax(0,26rem)_1fr] lg:items-start lg:gap-16">
            <div>
              <h3 className="font-medium">One test failed, which is why they are written down first</h3>
              <p className="mt-3 leading-relaxed text-ink-soft">
                A probability should be right as often as it says it is. That held at two weeks and
                broke further out: mean reliability rises from{" "}
                <span className="num text-ink">{look.reliability_by_horizon["2"].mean.toFixed(4)}</span>{" "}
                at two weeks to{" "}
                <span className="num text-ink">{look.reliability_by_horizon["8"].mean.toFixed(4)}</span>{" "}
                at eight, against a threshold of 0.05 fixed before the look.{" "}
                <span className="num text-ink">{look.by_test["5"].n_total - look.by_test["5"].n_pass}</span>{" "}
                of <span className="num text-ink">{look.by_test["5"].n_total}</span> failed it.
              </p>
              <p className="mt-4 leading-relaxed text-ink-soft">
                Those targets now show a regional base rate and state the reason, instead of a
                per-cell number the year did not support. That consequence was decided in advance
                too, so the result could not be argued into a better presentation afterwards.
              </p>
            </div>
            <ReliabilityFigure byHorizon={look.reliability_by_horizon} />
          </div>
        </div>

        <div className="mt-14 border-t border-rule pt-10">
          <LineReveal
            className="display max-w-[30ch] text-2xl md:text-3xl"
            lines={[
              <>Nineteen years of record made the intervals worth showing.</>,
              <>On three years they were no better than a climatology.</>,
              <>The sealed year was opened once, under a frozen configuration.</>,
            ]}
          />
          <p className="mt-6 max-w-prose leading-relaxed text-ink-soft">
            Extending the record turned{" "}
            <span className="num text-ink">{informative.length}</span> of six forecast horizons from
            no better than the historical range into genuinely narrower than it. The other{" "}
            <span className="num text-ink">{6 - informative.length}</span> show the historical range
            instead, and say so on the card.
          </p>
        </div>
      </Section>

      {/* 6. Discipline, as figures. Plain layout, no cards. */}
      <Section n="04" title="How it was tested">
        <dl className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            v={String(facts.hindcast_looks)}
            k="looks at the sealed 2026 holdout, the third under a pre-registered, hash-frozen configuration"
          />
          <Stat
            v={`${look.criteria_passed}/${look.criteria_total}`}
            k="pre-registered criteria passed, including every interval test on both counties"
          />
          <Stat
            v={String(survivors.length)}
            k={`of ${facts.multiplicity.n_comparisons} comparisons beat their baseline, after multiplicity control and a shuffled-target check`}
          />
          <Stat
            v={String(facts.subx.n_switched)}
            k="targets adopted a forecast-weather model, from one run judged by a rule fixed beforehand"
            tone="ember"
          />
        </dl>

        <p className="mt-12 max-w-prose leading-relaxed text-ink-soft">
          COFIRE claims skill only where it survived the test: {survivors.length} target and county
          pairs, mostly drought transitions at two and four weeks. A raw skill score was not enough
          to earn that, because a forecast can beat a baseline through spread alone. Each claim had
          to beat its own targets shuffled in place, which removed five that would otherwise have
          been reported as skill.
        </p>
      </Section>

      {/* 7. Close. */}
      <section className="border-t border-rule bg-ink px-6 py-20 text-paper">
        <div className="mx-auto max-w-[1400px]">
          <LineReveal
            className="display max-w-[20ch] text-4xl text-paper md:text-6xl"
            lines={[<>Open it on Pueblo County.</>]}
          />
          <p className="mt-5 max-w-prose leading-relaxed text-paper/70">
            Forecasts run through {facts.split.holdout} on {facts.domains.length} counties at{" "}
            <span className="num">{facts.resolution_m / 1000}</span> km cells, from a configuration
            frozen before the sealed year was opened.
          </p>
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

/** Numbered section, the reference's organising device. */
function Section({
  n,
  title,
  children,
  tinted,
}: {
  n: string;
  title: string;
  children: React.ReactNode;
  tinted?: boolean;
}) {
  return (
    <section className={`border-t border-rule px-6 py-20 md:py-28 ${tinted ? "bg-paper-raised" : ""}`}>
      <div className="mx-auto max-w-[1400px]">
        <Reveal>
          <p className="num mb-10 text-xs text-mute">
            {n} <span className="mx-2 text-rule">/</span> {title}
          </p>
        </Reveal>
        {children}
      </div>
    </section>
  );
}

function Act({
  k,
  body,
  href,
  className = "",
  large,
}: {
  k: string;
  body: string;
  href: string;
  className?: string;
  large?: boolean;
}) {
  return (
    <Link href={href} className={`group bg-paper p-8 transition-colors hover:bg-paper-raised ${className}`}>
      <h3 className={`display ${large ? "text-4xl" : "text-2xl"}`}>{k}</h3>
      <p className="mt-3 leading-relaxed text-ink-soft">{body}</p>
      <span className="mt-5 inline-flex items-center gap-1.5 text-sm text-ember">
        Open
        <ArrowRight size={14} weight="bold" className="transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}

function Stat({ v, k, tone = "ink" }: { v: string; k: string; tone?: "ink" | "ember" }) {
  return (
    <Reveal>
      <dt className="sr-only">{k}</dt>
      <dd>
        <Numeral value={v} size="xl" tone={tone} />
        <p className="mt-2 max-w-[30ch] text-sm leading-relaxed text-mute">{k}</p>
      </dd>
    </Reveal>
  );
}
