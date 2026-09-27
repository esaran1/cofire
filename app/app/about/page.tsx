"use client";

import { motion, useReducedMotion } from "motion/react";
import { Disclosure, StatRow, Verdict } from "@/components/ui/Controls";
import { Reveal } from "@/components/ui/Reveal";
import facts from "@/lib/facts.json";
import { domainLabel } from "@/lib/domainNames";
import { targetLabel } from "@/lib/targets";

/**
 * What ships, and what it is allowed to claim.
 *
 * The previous version was five tables, including raw target identifiers like
 * `d_ge2` that mean nothing outside the codebase. A reader wants three things:
 * what the thing does, where it is trustworthy, and where the data came from.
 * Everything else is provenance and sits behind a disclosure.
 */

const gb = (b: number) => `${(b / 1e9).toFixed(2)} GB`;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Reveal className="border-rule mt-14 border-t pt-8">
      <h2 className="text-xl font-medium">{title}</h2>
      {children}
    </Reveal>
  );
}

export default function AboutPage() {
  const reduce = useReducedMotion();
  const survivors = facts.survivors;
  const byDomain = survivors.reduce<Record<string, typeof survivors>>((acc, s) => {
    (acc[s.domain] ||= []).push(s);
    return acc;
  }, {});

  return (
    <div className="reading px-6 pb-20 pt-10">
      <motion.header
        initial={reduce ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        <h1 className="display text-4xl font-normal md:text-5xl">How it works</h1>
        <p className="text-ink-soft mt-3 max-w-[58ch] leading-relaxed">
          Drought and fire-spread conditions for Denver, the two watersheds its water comes from, and
          Larimer and Pueblo counties, 2 to 8 weeks out, with an honest account of how far to trust
          each number. Not a forecast of ignitions.
        </p>
      </motion.header>

      <div className="border-rule mt-10 grid gap-8 border-y py-8 sm:grid-cols-3">
        <Verdict
          value={String(survivors.length)}
          label="forecasts beat their baseline"
          sub={`of ${facts.multiplicity.n_comparisons} tested`}
        />
        <Verdict value={String(facts.hindcast_looks)} label="looks at the sealed year" sub="the last one pre-registered" />
        <Verdict value={gb(facts.ledger.total_bytes)} label="data downloaded" sub={`against a ${gb(facts.ledger.budget_bytes)} cap`} />
      </div>

      <Section title="Where the forecasts beat their baselines">
        <p className="text-ink-soft mt-2 max-w-[58ch] text-sm leading-relaxed">
          Skill is claimed here and nowhere else. Each of these had to beat its own outcomes
          shuffled in place, because a forecast can beat a baseline on spread alone.
        </p>
        {facts.multiplicity.withdrawn_by_leak_free_refit.length > 0 ? (
          <p className="text-mute mt-2 max-w-[58ch] text-xs leading-relaxed">
            {facts.multiplicity.n_survivors_original} passed the original test.{" "}
            {facts.multiplicity.withdrawn_by_leak_free_refit.length} no longer passes once training
            labels are kept out of the evaluation period, so it is not claimed:{" "}
            {facts.multiplicity.withdrawn_by_leak_free_refit.join(", ")}.
          </p>
        ) : null}
        <p className="text-mute mt-2 max-w-[58ch] text-xs leading-relaxed" data-testid="agreement-note">
          {facts.multiplicity.agreeing_targets.length === 0
            ? "None of these holds in every area where it can be tested, so each is claimed for its own area only."
            : `Holding in every area where it can be tested: ${facts.multiplicity.agreeing_targets.map((t) => targetLabel(t)).join(", ")}.`}
        </p>
        {Object.entries(byDomain).map(([dom, rows]) => (
          <div key={dom} className="mt-6">
            <h3 className="text-mute text-xs">{domainLabel(dom)}</h3>
            <div className="mt-1">
              {rows.map((s) => (
                <StatRow
                  key={s.target}
                  label={`${targetLabel(s.target)}, ${s.horizon}w`}
                  value={s.paired_diff.toFixed(3)}
                />
              ))}
            </div>
          </div>
        ))}
      </Section>

      {facts.interval_audit.retraction ? (
        <Section title={facts.interval_audit.retraction.title}>
          <p className="text-ink-soft mt-2 max-w-[58ch] text-sm leading-relaxed">
            {facts.interval_audit.retraction.summary}
          </p>
          <p className="text-mute mt-3 text-xs">
            Full record: {facts.interval_audit.retraction.doc}, and{" "}
            {facts.interval_audit.retraction.sweep}.
          </p>
        </Section>
      ) : null}

      <Section title="What ships">
        <dl className="border-rule mt-4 divide-y divide-rule border-y">
          {Object.entries(facts.configuration).map(([k, v]) => (
            <div key={k} className="grid gap-1 py-2.5 sm:grid-cols-[9rem_1fr] sm:gap-4">
              <dt className="text-mute text-sm capitalize">{k.replace(/_/g, " ")}</dt>
              <dd className="text-ink-soft text-sm">{String(v)}</dd>
            </div>
          ))}
        </dl>
        <p className="text-ink-soft mt-4 max-w-[58ch] text-sm leading-relaxed">
          These are empirical conditional models, not machine learning. On this record a
          transition table and a damped persistence rule beat every trained arm tried.
        </p>
      </Section>

      <Section title="Where the data comes from">
        <div className="mt-4">
          {facts.sources.map((s) => (
            <StatRow key={s.name} label={s.name} value={s.span} />
          ))}
        </div>
        <p className="text-ink-soft mt-4 max-w-[58ch] text-sm leading-relaxed">
          A sub-seasonal weather model was tested once by a rule fixed in advance and did not
          qualify, so no target uses it.
        </p>
      </Section>

      <Section title="Credits and licenses">
        <ul className="border-rule mt-4 divide-y divide-rule border-y" data-testid="credits">
          {facts.credits.map((c) => (
            <li key={c.name} className="py-3">
              <p className="text-sm">
                <a href={c.url} className="underline underline-offset-2">
                  {c.name}
                </a>
                <span className="text-mute">, {c.use}. {c.license}.</span>
              </p>
              <p className="text-ink-soft mt-1 text-xs leading-relaxed">{c.credit}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Provenance">
        <div className="mt-4">
          <StatRow label="Training" value={facts.split.train} />
          <StatRow label="Validation" value={facts.split.validate} />
          <StatRow label="Calibration" value={facts.split.calibrate} />
          <StatRow label="Held out" value={facts.split.holdout} />
        </div>
        <div className="mt-4">
          <Disclosure summary={<span className="sr-only">Hashes</span>} detail="Hashes and ledger">
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
              <div>
                <dt>Download ledger</dt>
                <dd>
                  {gb(facts.ledger.total_bytes)} across{" "}
                  {facts.ledger.n_transfers.toLocaleString()} transfers. Append-only: a
                  mis-estimate is corrected by appending evidence, never by rewriting an entry.
                </dd>
              </div>
            </dl>
          </Disclosure>
        </div>
      </Section>
    </div>
  );
}
