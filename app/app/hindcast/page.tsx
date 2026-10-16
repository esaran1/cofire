"use client";

import { motion, useReducedMotion } from "motion/react";
import { PidVsAciFigure, ReliabilityFigure } from "@/components/landing/PidFigure";
import { Disclosure, StatRow, Verdict } from "@/components/ui/Controls";
import { CountUp } from "@/components/ui/Animated";
import { Reveal } from "@/components/ui/Reveal";
import facts from "@/lib/facts.json";
import { domainLabel, useDomain } from "@/lib/domain";
import { countyName, targetHorizon, targetLabel } from "@/lib/targets";
import { useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";

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
const CRITERIA: Record<string, MessageKey> = {
  "1": "hind.crit1",
  "2": "hind.crit2",
  "3": "hind.crit3",
  "4": "hind.crit4",
  "5": "hind.crit5",
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
  const { lang, t } = useT();
  const [domain] = useDomain();
  const sealedHere = domain === "larimer" || domain === "pueblo";
  return (
    <div className="reading px-6 pb-20 pt-10">
      <motion.header
        initial={reduce ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        <h1 className="display text-4xl font-normal md:text-5xl">{t("hind.title")}</h1>
        <p className="text-ink-soft mt-3 max-w-[58ch] leading-relaxed">{t("hind.lede")}</p>
        {!sealedHere ? (
          <p className="text-mute mt-3 max-w-[58ch] text-sm leading-relaxed" data-testid="hindcast-domain-note">
            {t("hind.domainNote", { area: domainLabel(domain) })}
          </p>
        ) : null}
      </motion.header>

      {/* The correction comes first. The look-3 interval results passed, but the
          test behind them used outcomes a real forecast would not have yet, so
          they are void as evidence. The record is kept below, labelled as such. */}
      {audit.retraction ? (
        <div role="note" className="border-ember/40 bg-ember/5 mt-8 border p-5">
          {/* The English comes from facts.json; the Spanish is a translation of it, and a test
              fails if the English moves away from the version that was translated. */}
          <p className="text-ember font-medium">{lang === "es" ? t("hind.retractionTitle") : audit.retraction.title}</p>
          <p className="text-ink-soft mt-2 max-w-[62ch] text-sm leading-relaxed">
            {lang === "es" ? t("hind.retractionSummary") : audit.retraction.summary}
          </p>
          <p className="text-mute mt-3 text-xs">
            {t("hind.fullRecord", { doc: audit.retraction.doc, sweep: audit.retraction.sweep })}
          </p>
        </div>
      ) : null}

      <div className="border-rule mt-10 grid gap-8 border-y py-8 sm:grid-cols-3">
        <Verdict
          value={`${look.by_test["5"].n_pass}/${look.by_test["5"].n_total}`}
          label={t("hind.probPassed")}
          sub={t("hind.probSub")}
        />
        <Verdict value={t("hind.void")} label={t("hind.intervalTests")} sub={t("hind.intervalSub")} tone="fail" />
        <Verdict
          value={`${failures.length}`}
          label={t("hind.relFailures")}
          tone="fail"
          sub={t("hind.relSub")}
        />
      </div>

      <Section title={t("hind.covTitle")}>
        <p className="text-ink-soft mt-2 max-w-[58ch] text-sm leading-relaxed">
          {t("hind.covLead")}{" "}
          <span className="num text-ink">
            {Math.min(...audit.as_tested.map((r) => r.roll13_min)).toFixed(4)}
          </span>
          {t("hind.covMid")}{" "}
          <span className="num text-ember">{audit.real_time_roll13_min?.toFixed(4)}</span>.
        </p>
        <div className="mt-6">
          <PidVsAciFigure
            rows={[...audit.as_tested.map((r) => ({ ...r, impl: "reference_pid" })), ...audit.real_time.map((r) => ({ ...r, impl: "aci" }))]}
            floor={0}
            target={0.7}
            caption={t("hind.covCaption")}
          />
        </div>
        <div className="mt-4">
          <Disclosure summary={<span className="sr-only">As-tested detail</span>} detail={t("hind.voidNumbers")}>
            <div className="mt-2">
              {pid.map((r) => (
                <StatRow
                  key={`${r.domain}-${r.horizon}`}
                  label={t("hind.asTested", { d: r.domain, h: r.horizon })}
                  value={t("hind.asTestedValue", { c: r.coverage.toFixed(4), w: r.roll13_min.toFixed(4) })}
                />
              ))}
            </div>
          </Disclosure>
        </div>
      </Section>

      <Section title={t("hind.relTitle")}>
        <p className="text-ink-soft mt-2 max-w-[58ch] text-sm leading-relaxed">
          {t("hind.relText")}
        </p>
        <div className="mt-6">
          <ReliabilityFigure byHorizon={look.reliability_by_horizon} caption={t("hind.relCaption")} />
        </div>
        <div className="mt-4">
          <Disclosure summary={<span className="sr-only">Failure detail</span>} detail={t("hind.allFailures", { n: failures.length })}>
            <div className="mt-2">
              {failures.map((r) => (
                <StatRow
                  key={`${r.domain}-${r.target}`}
                  label={`${countyName(r.domain)}: ${targetLabel(r.target, null, lang)}, ${targetHorizon(r.target)}w`}
                  value={r.reliability.toFixed(4)}
                  tone="fail"
                />
              ))}
            </div>
          </Disclosure>
        </div>
      </Section>

      <Section title={t("hind.critTitle")}>
        <div className="mt-4">
          {Object.entries(look.by_test).map(([k, test]) => (
            <StatRow
              key={k}
              label={CRITERIA[k] ? t(CRITERIA[k]) : test.name.replace(/^\d+\s/, "")}
              value={`${test.n_pass}/${test.n_total}`}
              tone={k !== "5" || test.n_pass !== test.n_total ? "fail" : "pass"}
            />
          ))}
        </div>
      </Section>

      <Section title={t("hind.provTitle")}>
        <div className="mt-4">
          <StatRow label={t("hind.looks")} value={String(facts.hindcast_looks)} />
          <StatRow label={t("hind.prereg")} value={`${facts.preregistration_sha256.slice(0, 12)}…`} />
          <StatRow label={t("hind.config")} value={`${facts.config_hash.slice(0, 12)}…`} />
          <StatRow label={t("hind.freeze")} value={`${facts.freeze_commit.slice(0, 12)}…`} />
        </div>
        <div className="mt-4">
          <Disclosure summary={<span className="sr-only">{t("hind.fullHashes")}</span>} detail={t("hind.fullHashes")}>
            <dl className="space-y-2">
              <div>
                <dt>{t("hind.preregSha")}</dt>
                <dd className="num text-ink break-all">{facts.preregistration_sha256}</dd>
              </div>
              <div>
                <dt>{t("hind.configHash")}</dt>
                <dd className="num text-ink break-all">{facts.config_hash}</dd>
              </div>
              <div>
                <dt>{t("hind.freeze")}</dt>
                <dd className="num text-ink break-all">{facts.freeze_commit}</dd>
              </div>
            </dl>
          </Disclosure>
        </div>
      </Section>

      <a
        href="/?issue=2026-05-05&horizon=2"
        className="bg-ochre text-paper mt-12 inline-block rounded-full px-5 py-2.5 text-sm font-medium transition-transform active:scale-[0.98]"
      >
        {t("hind.replay")}
      </a>
    </div>
  );
}
