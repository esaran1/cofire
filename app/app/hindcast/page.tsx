"use client";

import { motion, useReducedMotion } from "motion/react";
import { PidVsAciFigure, ReliabilityFigure } from "@/components/landing/PidFigure";
import { CountUp, Disclosure, StatRow, Verdict } from "@/components/ui/Controls";
import { Reveal } from "@/components/ui/Reveal";
import facts from "@/lib/facts.json";

/**
 * Look 3 on the sealed 2026 holdout.
 *
 * The earlier version of this page was four stacked tables and three
 * paragraphs. Every number in it was real, and almost none of it was read,
 * because the reader had to parse prose to find out whether the thing passed.
 *
 * This version leads with the verdict, shows the two figures that carry the
 * finding, and puts the underlying tables behind disclosures for the reader
 * who wants to check the work. Nothing was deleted; it was ranked.
 */

const look = facts.look3;
const cov = look.coverage_series;
const rel = look.reliability;
const pid = cov.filter((r) => r.impl === "reference_pid");
const failures = rel.filter((r) => r.reliability > 0.05);

/** Section wrapper with a single scroll-reveal. Sequence matches reading order. */
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Reveal className="border-rule mt-14 border-t pt-8">
      <h2 className="text-xl font-medium">{title}</h2>
      {children}
    </Reveal>
  );
}

export default function HindcastPage() {
  const reduce = useReducedMotion();
  return (
    <div className="mx-auto max-w-3xl px-6 pb-20 pt-10">
      <motion.header
        initial={reduce ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        <h1 className="display text-4xl font-normal md:text-5xl">
          The sealed year, opened once
        </h1>
        <p className="text-ink-soft mt-3 max-w-[58ch] leading-relaxed">
          2026 was held back from every fitting decision, then tested once against criteria
          written down in advance.
        </p>
      </motion.header>

      <div className="border-rule mt-10 grid gap-8 border-y py-8 sm:grid-cols-3">
        <Verdict
          value={`${look.criteria_passed}/${look.criteria_total}`}
          label="criteria passed"
          sub="written down before the look"
        />
        <Verdict value="30/30" label="interval tests passed" sub="both counties, all ranges" />
        <Verdict
          value={`${failures.length}`}
          label="reliability failures"
          tone="fail"
          sub="all at the longer ranges"
        />
      </div>

      <Section title="Coverage held. The alternative collapsed.">
        <p className="text-ink-soft mt-2 max-w-[58ch] text-sm leading-relaxed">
          Both controllers ran on identical rows. The adaptive method dropped to{" "}
          <span className="num text-ink">
            <CountUp to={look.aci.roll13_min} decimals={4} />
          </span>{" "}
          coverage at its worst stretch and was wrong{" "}
          <span className="num text-ink">{look.aci.miss_run_max}</span> weeks running. The one
          that ships never fell below{" "}
          <span className="num text-ink">
            <CountUp to={look.pid.roll13_min} decimals={4} />
          </span>
          .
        </p>
        <div className="mt-6">
          <PidVsAciFigure rows={cov} />
        </div>
        <div className="mt-4">
          <Disclosure summary={<span className="sr-only">Coverage detail</span>} detail="Per-county numbers">
            <div className="mt-2">
              {pid.map((r) => (
                <StatRow
                  key={`${r.domain}-${r.horizon}`}
                  label={`${r.domain} ${r.horizon}w`}
                  value={`${r.coverage.toFixed(4)} overall · ${r.roll13_min.toFixed(4)} worst · ${r.miss_run} longest miss`}
                />
              ))}
            </div>
          </Disclosure>
        </div>
      </Section>

      <Section title="Reliability broke at the longer ranges">
        <p className="text-ink-soft mt-2 max-w-[58ch] text-sm leading-relaxed">
          A probability should be right as often as it claims. That held at two weeks and broke
          further out. The targets that failed now show a county-wide rate instead of a per-cell
          number, which is what the pre-registration said would happen.
        </p>
        <div className="mt-6">
          <ReliabilityFigure byHorizon={look.reliability_by_horizon} />
        </div>
        <div className="mt-4">
          <Disclosure summary={<span className="sr-only">Failure detail</span>} detail={`All ${failures.length} failures`}>
            <div className="mt-2">
              {failures.map((r) => (
                <StatRow
                  key={`${r.domain}-${r.target}`}
                  label={`${r.domain} · ${r.target}`}
                  value={r.reliability.toFixed(4)}
                  tone="fail"
                />
              ))}
            </div>
          </Disclosure>
        </div>
      </Section>

      <Section title="Every criterion, as written down">
        <div className="mt-4">
          {Object.entries(look.by_test).map(([k, t]) => (
            <StatRow
              key={k}
              label={t.name.replace(/^\d+\s/, "")}
              value={`${t.n_pass}/${t.n_total}`}
              tone={t.n_pass === t.n_total ? "pass" : "fail"}
            />
          ))}
        </div>
      </Section>

      <Section title="Provenance">
        <div className="mt-4">
          <StatRow label="Looks at the sealed year" value={String(facts.hindcast_looks)} />
          <StatRow label="Pre-registration" value={`${facts.preregistration_sha256.slice(0, 12)}…`} />
          <StatRow label="Configuration" value={`${facts.config_hash.slice(0, 12)}…`} />
          <StatRow label="Freeze commit" value={`${facts.freeze_commit.slice(0, 12)}…`} />
        </div>
        <div className="mt-4">
          <Disclosure summary={<span className="sr-only">Full hashes</span>} detail="Full hashes">
            <dl className="space-y-2">
              <div>
                <dt>Pre-registration sha256</dt>
                <dd className="num text-ink break-all">{facts.preregistration_sha256}</dd>
              </div>
              <div>
                <dt>Configuration hash</dt>
                <dd className="num text-ink break-all">{facts.config_hash}</dd>
              </div>
              <div>
                <dt>Freeze commit</dt>
                <dd className="num text-ink break-all">{facts.freeze_commit}</dd>
              </div>
            </dl>
          </Disclosure>
        </div>
      </Section>

      <a
        href="/?issue=2026-05-05&horizon=2"
        className="bg-ochre text-ink mt-12 inline-block rounded-full px-5 py-2.5 text-sm font-medium transition-transform active:scale-[0.98]"
      >
        Replay a 2026 issue
      </a>
    </div>
  );
}
