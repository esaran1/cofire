"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight } from "@phosphor-icons/react";
import { CoverageFigure, InflationFigure } from "@/components/landing/CoverageFigure";
import { Numeral } from "@/components/ui/Controls";
import facts from "@/lib/facts.json";

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : `${(v * 100).toFixed(1)}%`);

/** Residual p90 by year, from artifacts/uncertainty/leak_check.md. */
const INFLATION = [
  { year: 2018, p90: 20.59, heldOut: false },
  { year: 2019, p90: 24.94, heldOut: false },
  { year: 2020, p90: 25.06, heldOut: false },
  { year: 2021, p90: 23.77, heldOut: false },
  { year: 2022, p90: 26.38, heldOut: false },
  { year: 2023, p90: 59.16, heldOut: true },
  { year: 2024, p90: 60.59, heldOut: true },
  { year: 2025, p90: 62.66, heldOut: true },
];

export default function LandingPage() {
  const reduce = useReducedMotion();
  const cal = facts.calibration as Record<
    string,
    { best: { mean: number; label: string }; baseline: { mean: number }; improvement: number; n_variants: number; variants: { label: string; mean: number }[] }
  >;
  const pueblo = cal?.pueblo;
  const pool = facts.pool as { usdm_max: number; measured_coverage: number; years: number[] } | undefined;
  const lodo = (facts.lodo as Record<string, { level_mean_skill: number; n_folds: number }>)?.pueblo;
  const fires = facts.fires as { in_domain: number; in_domain_acres: number; largest: string } | undefined;

  return (
    <>
      {/* 1. Hero. Centered is allowed here: this is a launch statement and the
          message is the design (skill 4.3 override). */}
      <section className="relative flex min-h-[78dvh] items-center justify-center px-6 pt-16">
        <div className="text-center">
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
        </div>
      </section>

      {/* 2. The claim, as a display statement. */}
      <Section n="01" title="The idea">
        <p className="display max-w-[22ch] text-4xl md:text-6xl">
          Colorado dries out weeks <em>before</em> it burns.
        </p>
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
      <figure className="relative">
        <img
          src="/img/hero-highpark.jpg"
          alt="The sun seen through heavy smoke from the High Park Fire above Poudre Canyon, Colorado"
          className="h-[44vh] w-full object-cover md:h-[60vh]"
        />
        <figcaption className="mx-auto max-w-[1400px] px-6 py-3 text-xs text-mute">
          High Park Fire above Poudre Canyon. Photo CC BY 2.0 via Wikimedia Commons.
        </figcaption>
      </figure>

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

      {/* 5. The calibration story, carried by two real charts. */}
      <Section n="03" title="The honest part" tinted>
        <p className="display max-w-[24ch] text-4xl md:text-6xl">
          Most forecasts show a number. This one says when the number <em>cannot be trusted</em>.
        </p>

        <div className="mt-12 space-y-14">
          <div className="grid gap-8 lg:grid-cols-[minmax(0,26rem)_1fr] lg:items-start lg:gap-16">
            <div>
              <h3 className="font-medium">The interval was wrong, and it was our bug</h3>
              <p className="mt-3 leading-relaxed text-ink-soft">
                The adaptive update aimed at the coverage rate where it needed the miss rate. Its
                only stable point was a 90% miss rate, so intervals shrank the more they were wrong.
                One split ran the online update and the other did not, which is why it hid for so
                long. Ten regression tests now fail on the old code.
              </p>
              <p className="mt-4 leading-relaxed text-ink-soft">
                Fixing it was not enough. We pre-registered {pueblo?.n_variants ?? 6} ways to rebuild
                the calibration pool, wrote the acceptance bar down first, and hashed the document so
                the goalposts could not move. Every one was rejected, with an improvement over the
                simplest baseline of exactly{" "}
                <span className="num text-ink">
                  {pueblo ? `${pueblo.improvement >= 0 ? "+" : ""}${(pueblo.improvement * 100).toFixed(1)}%` : "n/a"}
                </span>
                .
              </p>
            </div>
            {pueblo?.variants && <CoverageFigure variants={pueblo.variants} />}
          </div>

          <div className="grid gap-8 lg:grid-cols-[minmax(0,26rem)_1fr] lg:items-start lg:gap-16">
            <div>
              <h3 className="font-medium">Why no pool can fix it</h3>
              <p className="mt-3 leading-relaxed text-ink-soft">
                Forecast error does not track how dry a year was. It tracks whether that year was
                held out of training, and every held-out year is inflated by the same amount. A pool
                built from those years inherits the inflation uniformly, so reweighting them moves
                nothing.
              </p>
            </div>
            <InflationFigure series={INFLATION} />
          </div>
        </div>

        <div className="mt-14 border-t border-rule pt-10">
          <p className="display max-w-[30ch] text-2xl md:text-3xl">
            Every held-out year carries the same <em>2.4x</em> error inflation. A leakage audit ruled
            out contamination. Because that inflation is constant across the pool years, no
            reweighting of them can recover it.
          </p>
          <p className="mt-6 max-w-prose leading-relaxed text-ink-soft">
            So the app hides the interval and states the reason, rather than drawing a band the
            record cannot back. Measured coverage on the shipping pool is{" "}
            <span className="num text-ink">{pool ? pct(pool.measured_coverage) : "n/a"}</span> against
            a 0.90 target.
          </p>
        </div>
      </Section>

      {/* 6. Discipline, as figures. Plain layout, no cards (skill 4.4). */}
      <Section n="04" title="How it was tested">
        <dl className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            v={String(facts.hindcast_looks ?? "n/a")}
            k="looks at the sealed 2026 holdout, each logged with a git SHA and a config hash"
          />
          <Stat
            v={facts.effective_n?.usdm ? String(facts.effective_n.usdm) : "n/a"}
            k="effective sample size for drought, not the 112,752 rows it superficially looks like"
          />
          <Stat v={String(lodo?.n_folds ?? "n/a")} k="leave-one-year-out folds, so method changes cost no holdout budget" />
          <Stat
            v={pct(lodo?.level_mean_skill)}
            k="mean skill against a persistence baseline. It is negative, and it is published"
            tone="ember"
          />
        </dl>

        <p className="mt-12 max-w-prose leading-relaxed text-ink-soft">
          COFIRE does not claim better forecast skill than persistence, because it does not have it.
          What it has is an audit trail: pre-registered experiments, a public look counter on the
          holdout, and an uncertainty layer that reports its own failure.
        </p>
      </Section>

      {/* 7. Close. */}
      <section className="border-t border-rule bg-ink px-6 py-20 text-paper">
        <div className="mx-auto max-w-[1400px]">
          <p className="display max-w-[20ch] text-4xl text-paper md:text-6xl">
            Open it on Pueblo County.
          </p>
          {fires && fires.in_domain > 0 && (
            <p className="mt-5 max-w-prose leading-relaxed text-paper/70">
              The domain contains {fires.in_domain} qualifying 2026 perimeters totalling{" "}
              <span className="num">{fires.in_domain_acres.toLocaleString()}</span> acres, including{" "}
              {fires.largest}.
            </p>
          )}
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
        <p className="num mb-10 text-xs text-mute">
          {n} <span className="mx-2 text-rule">/</span> {title}
        </p>
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
    <div>
      <dt className="sr-only">{k}</dt>
      <dd>
        <Numeral value={v} size="xl" tone={tone} />
        <p className="mt-2 max-w-[30ch] text-sm leading-relaxed text-mute">{k}</p>
      </dd>
    </div>
  );
}
