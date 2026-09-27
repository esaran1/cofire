"use client";

import { motion, useReducedMotion } from "motion/react";
import { PidVsAciFigure, ReliabilityFigure } from "@/components/landing/PidFigure";
import { CountUp, Disclosure, StatRow, Verdict } from "@/components/ui/Controls";
import { Reveal } from "@/components/ui/Reveal";
import facts from "@/lib/facts.json";
import { domainLabel, useDomain } from "@/lib/domain";
import { countyName, targetHorizon, targetLabel } from "@/lib/targets";

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
const audit = facts.interval_audit;

/**
 * The pre-registered tests in plain words, keyed by test number.
 *
 * The artifact names each group after its first row, which mislabelled test 3
 * as "coverage | D0-D1" although its twelve checks cover both drought levels.
 * These say what each test actually checked.
 */
const CRITERIA: Record<string, string> = {
  "1": "Overall coverage (reported, not tested), void",
  "2": "Worst 13-week coverage stays at or above 0.70, void",
  "3": "Coverage within 0.05 of 0.90 in mild and in severe drought, void",
  "4": "Longest run of misses is 60 weeks or fewer, void",
  "5": "Stated odds match what happened (reliability 0.05 or less)",
};
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
  const [domain] = useDomain();
  const sealedHere = domain === "larimer" || domain === "pueblo";
  return (
    <div className="reading px-6 pb-20 pt-10">
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
        {!sealedHere ? (
          <p className="text-mute mt-3 max-w-[58ch] text-sm leading-relaxed" data-testid="hindcast-domain-note">
            This test covered Larimer and Pueblo. {domainLabel(domain)} was added after the seal, so its
            numbers were checked on 2022 and 2023 only, and nothing about it is scored on 2026.
          </p>
        ) : null}
      </motion.header>

      {/* The correction comes first. The look-3 interval results passed, but the
          test behind them used outcomes a real forecast would not have yet, so
          they are void as evidence. The record is kept below, labelled as such. */}
      {audit.retraction ? (
        <div role="note" className="border-ember/40 bg-ember/5 mt-8 border p-5">
          <p className="text-ember font-medium">{audit.retraction.title}</p>
          <p className="text-ink-soft mt-2 max-w-[62ch] text-sm leading-relaxed">
            {audit.retraction.summary}
          </p>
          <p className="text-mute mt-3 text-xs">
            Full record: {audit.retraction.doc}, and the follow-up sweep in {audit.retraction.sweep}.
          </p>
        </div>
      ) : null}

      <div className="border-rule mt-10 grid gap-8 border-y py-8 sm:grid-cols-3">
        <Verdict
          value={`${look.by_test["5"].n_pass}/${look.by_test["5"].n_total}`}
          label="probability tests passed"
          sub="written down before the look"
        />
        <Verdict value="void" label="interval tests" sub="the test itself was flawed" tone="fail" />
        <Verdict
          value={`${failures.length}`}
          label="reliability failures"
          tone="fail"
          sub="all at the longer ranges"
        />
      </div>

      <Section title="Interval coverage: as tested, and in real time">
        <p className="text-ink-soft mt-2 max-w-[58ch] text-sm leading-relaxed">
          On the unsealed years 2022 to 2025, the test as run never fell below{" "}
          <span className="num text-ink">
            {Math.min(...audit.as_tested.map((r) => r.roll13_min)).toFixed(4)}
          </span>
          . With the delay a real forecaster faces, the same controller fell to{" "}
          <span className="num text-ember">{audit.real_time_roll13_min?.toFixed(4)}</span>.
        </p>
        <div className="mt-6">
          <PidVsAciFigure
            rows={[...audit.as_tested.map((r) => ({ ...r, impl: "reference_pid" })), ...audit.real_time.map((r) => ({ ...r, impl: "aci" }))]}
            floor={0}
            target={0.7}
            caption="Worst 13-week coverage on 2022 to 2025. Dark is the test as it was run, pale is the same test with the real 2 to 8 week delay. The dashed line is the 0.70 floor set in advance."
          />
        </div>
        <div className="mt-4">
          <Disclosure summary={<span className="sr-only">As-tested detail</span>} detail="The void 2026 numbers">
            <div className="mt-2">
              {pid.map((r) => (
                <StatRow
                  key={`${r.domain}-${r.horizon}`}
                  label={`${r.domain} ${r.horizon}w, as tested`}
                  value={`${r.coverage.toFixed(4)} overall · ${r.roll13_min.toFixed(4)} worst`}
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
                  label={`${countyName(r.domain)}: ${targetLabel(r.target)}, ${targetHorizon(r.target)}w`}
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
              label={CRITERIA[k] ?? t.name.replace(/^\d+\s/, "")}
              value={`${t.n_pass}/${t.n_total}`}
              tone={k !== "5" || t.n_pass !== t.n_total ? "fail" : "pass"}
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
