"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, Eye, EyeSlash, ShieldCheck } from "@phosphor-icons/react";
import { Act, Figure, Reveal } from "@/components/landing/Act";
import facts from "@/lib/facts.json";

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : `${(v * 100).toFixed(1)}%`);

export default function LandingPage() {
  const reduce = useReducedMotion();
  const cal = facts.calibration as Record<string, { best: { mean: number; label: string }; baseline: { mean: number }; improvement: number; gap_to_target: number; n_variants: number }>;
  const pueblo = cal?.pueblo;
  const pool = facts.pool as { usdm_min: number; usdm_max: number; measured_coverage: number; years: number[] } | undefined;
  const lodo = (facts.lodo as Record<string, { level_mean_skill: number; delta_mean_skill: number; n_folds: number }>)?.pueblo;

  return (
    <main className="bg-ink text-paper">
      {/* ACT 1: the problem, stated plainly */}
      <section className="relative flex min-h-[100dvh] flex-col justify-center px-6 pt-24">
        <div className="mx-auto w-full max-w-6xl">
          <div className="grid gap-12 lg:grid-cols-12 lg:gap-8">
            <div className="lg:col-span-7">
              <motion.h1
                initial={reduce ? false : { opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-4xl font-semibold leading-[1.05] tracking-tight md:text-6xl"
              >
                Colorado dries out weeks
                <br />
                before it burns.
              </motion.h1>
              <motion.p
                initial={reduce ? false : { opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.12, ease: [0.16, 1, 0.3, 1] }}
                className="mt-6 max-w-[52ch] text-lg leading-relaxed text-mute"
              >
                COFIRE forecasts drought and fire-spread conditions 2 to 8 weeks out, and tells you
                how much to trust each number.
              </motion.p>
              <motion.div
                initial={reduce ? false : { opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.22, ease: [0.16, 1, 0.3, 1] }}
                className="mt-10 flex flex-wrap items-center gap-3"
              >
                <Link
                  href="/"
                  className="inline-flex items-center gap-2 rounded-lg bg-fire px-5 py-3 font-medium text-ink transition-transform active:scale-[0.98]"
                >
                  Open the map
                  <ArrowRight size={18} weight="bold" />
                </Link>
                <Link
                  href="/hindcast"
                  className="inline-flex items-center gap-2 rounded-lg border border-white/15 px-5 py-3 font-medium text-paper transition-colors hover:border-white/30"
                >
                  See the 2026 replay
                </Link>
              </motion.div>
            </div>

            <div className="lg:col-span-5 lg:pt-4">
              <motion.div
                initial={reduce ? false : { opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.8, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
                className="overflow-hidden rounded-2xl border border-white/10"
              >
                <img
                  src="/img/hero-highpark.jpg"
                  alt="The sun seen through heavy smoke from the High Park Fire above Poudre Canyon, Colorado"
                  className="h-[420px] w-full object-cover md:h-[520px]"
                  loading="eager"
                />
              </motion.div>
            </div>
          </div>
          <p className="mt-6 text-xs text-mute/70">
            High Park Fire above Poudre Canyon. Photo CC BY 2.0 via Wikimedia Commons.
          </p>
        </div>
      </section>

      {/* ACT 2: what it actually does */}
      <Act id="what" className="border-t border-white/10">
        <Reveal>
          <h2 className="max-w-[20ch] text-3xl font-semibold tracking-tight md:text-4xl">
            A forecast, an honest error bar, and something to do about it.
          </h2>
        </Reveal>
        <div className="mt-14 grid gap-10 md:grid-cols-3">
          <Reveal delay={0.05}>
            <h3 className="text-lg font-medium">Predict</h3>
            <p className="mt-2 max-w-[34ch] leading-relaxed text-mute">
              Put your own call on a cell before the model shows its own, then watch both settle
              against what actually happened.
            </p>
          </Reveal>
          <Reveal delay={0.12}>
            <h3 className="text-lg font-medium">Observe</h3>
            <p className="mt-2 max-w-[34ch] leading-relaxed text-mute">
              Report a dry stock tank or a crisp lawn. Ground truth from people who live on the
              cell, not just the satellite over it.
            </p>
          </Reveal>
          <Reveal delay={0.19}>
            <h3 className="text-lg font-medium">Harden</h3>
            <p className="mt-2 max-w-[34ch] leading-relaxed text-mute">
              Turn a bad outlook into a checklist for your own property, scored so progress is
              visible.
            </p>
          </Reveal>
        </div>
      </Act>

      {/* ACT 3: the evidence discipline */}
      <Act id="method" className="border-t border-white/10 bg-white/[0.02]">
        <div className="grid gap-12 lg:grid-cols-12">
          <Reveal className="lg:col-span-5">
            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
              Held out, counted, and published.
            </h2>
            <p className="mt-5 max-w-[46ch] leading-relaxed text-mute">
              2026 is a sealed holdout. Every time it is scored, the counter goes up and the number
              is published, so nobody can quietly retry until the answer looks good.
            </p>
          </Reveal>
          <div className="grid gap-10 sm:grid-cols-2 lg:col-span-7">
            <Reveal delay={0.06}>
              <Figure value={String(facts.hindcast_looks ?? "n/a")} label="looks taken at the 2026 holdout, logged with a git SHA and a config hash" />
            </Reveal>
            <Reveal delay={0.12}>
              <Figure value={facts.effective_n?.usdm ? String(facts.effective_n.usdm) : "n/a"} tone="drought" label="effective sample size for drought, not the 125,280 cell-weeks it superficially looks like" />
            </Reveal>
            <Reveal delay={0.18}>
              <Figure value={String(lodo?.n_folds ?? "n/a")} label="leave-one-drought-year-out folds, so model changes are tested without spending holdout budget" />
            </Reveal>
            <Reveal delay={0.24}>
              <Figure value={pct(lodo?.level_mean_skill)} tone="fire" label="mean skill against a persistence baseline. It is negative, and it is reported that way" />
            </Reveal>
          </div>
        </div>
      </Act>

      {/* ACT 4: the calibration story: a bug, six variants, a null result, and the response */}
      <Act id="calibration" className="border-t border-white/10">
        <Reveal>
          <h2 className="max-w-[24ch] text-3xl font-semibold tracking-tight md:text-4xl">
            The interval was wrong. Here is what we did about it.
          </h2>
        </Reveal>

        <div className="mt-16 space-y-16">
          <Reveal>
            <div className="grid gap-8 md:grid-cols-12 md:items-start">
              <div className="md:col-span-4">
                <h3 className="text-lg font-medium">Two splits, two different code paths</h3>
              </div>
              <div className="md:col-span-8">
                <p className="max-w-[62ch] leading-relaxed text-mute">
                  The adaptive update aimed at the coverage rate where it needed the miss rate. Its
                  only stable point was a 90% miss rate, so intervals shrank the more they were
                  wrong. Calibration looked healthy purely because that split ran with the online
                  update switched off. Ten regression tests now fail on the old code.
                </p>
              </div>
            </div>
          </Reveal>

          <Reveal>
            <div className="grid gap-8 md:grid-cols-12 md:items-start">
              <div className="md:col-span-4">
                <h3 className="text-lg font-medium">Six variants, registered before the run</h3>
              </div>
              <div className="md:col-span-8">
                <p className="max-w-[62ch] leading-relaxed text-mute">
                  Fixing the bug was not enough, so we pre-registered {pueblo?.n_variants ?? 6}{" "}
                  ways to build the calibration pool, wrote down the acceptance bar first, and
                  hashed the document so the goalposts could not move. Every one was rejected. Every
                  year held out of training carries the same ~2.4x error inflation, a leakage audit
                  ruled out contamination, and because that inflation is constant across the pool
                  years no reweighting of them can recover it.
                </p>
                <div className="mt-8 grid gap-8 sm:grid-cols-3">
                  <Figure value={pct(pueblo?.best.mean)} tone="fire" label={`best coverage reached, against a 90% target`} />
                  <Figure value={pueblo ? `${pueblo.improvement >= 0 ? "+" : ""}${(pueblo.improvement * 100).toFixed(1)}%` : "n/a"} label="improvement over the simplest baseline" />
                  <Figure value={String(pueblo?.n_variants ?? "n/a")} label="variants tested, and rejected, every one reported" />
                </div>
              </div>
            </div>
          </Reveal>

          <Reveal>
            <div className="grid gap-8 md:grid-cols-12 md:items-start">
              <div className="md:col-span-4">
                <h3 className="text-lg font-medium">So the app hides the number</h3>
              </div>
              <div className="md:col-span-8">
                <p className="max-w-[62ch] leading-relaxed text-mute">
                  Measured coverage on the shipping pool is {pool ? pct(pool.measured_coverage) : "n/a"}.
                  That is not an error bar anyone should act on, so COFIRE does not draw one. The
                  point forecast and the drivers stay; the band is replaced by the reason it is
                  missing.
                </p>
                <div className="mt-8 grid gap-4 sm:grid-cols-3">
                  <StateCard icon={<ShieldCheck size={18} weight="bold" />} name="Calibrated" body="Conditions sit inside the range the interval was checked against." tone="ok" />
                  <StateCard icon={<Eye size={18} weight="bold" />} name="Extrapolating" body="Past that range. The band widens and says so." tone="warn" />
                  <StateCard icon={<EyeSlash size={18} weight="bold" />} name="Uncalibrated" body="The record cannot back a band here, so none is drawn." tone="stop" />
                </div>
              </div>
            </div>
          </Reveal>
        </div>

        <Reveal delay={0.1}>
          <div className="mt-20 border-t border-white/10 pt-10">
            <p className="max-w-[58ch] text-xl leading-relaxed">
              Most forecasts show you a number. This one also shows you when the number is not worth
              showing.
            </p>
            <Link
              href="/"
              className="mt-8 inline-flex items-center gap-2 rounded-lg bg-fire px-5 py-3 font-medium text-ink transition-transform active:scale-[0.98]"
            >
              Open the map
              <ArrowRight size={18} weight="bold" />
            </Link>
          </div>
        </Reveal>
      </Act>
    </main>
  );
}

function StateCard({
  icon,
  name,
  body,
  tone,
}: {
  icon: React.ReactNode;
  name: string;
  body: string;
  tone: "ok" | "warn" | "stop";
}) {
  const ring =
    tone === "ok"
      ? "border-emerald-500/40 text-emerald-300"
      : tone === "warn"
        ? "border-amber-500/40 text-amber-300"
        : "border-fire/50 text-fire";
  return (
    <div className={`rounded-lg border p-4 ${ring}`}>
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide">
        {icon}
        {name}
      </div>
      <p className="mt-2 text-sm leading-snug text-mute">{body}</p>
    </div>
  );
}
