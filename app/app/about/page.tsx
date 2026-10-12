"use client";

import { motion, useReducedMotion } from "motion/react";
import { Disclosure, StatRow, Verdict } from "@/components/ui/Controls";
import { Reveal } from "@/components/ui/Reveal";
import facts from "@/lib/facts.json";
import { domainLabel } from "@/lib/domainNames";
import { targetLabel } from "@/lib/targets";
import { V12Results } from "@/components/V12Results";
import { useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";

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
  const { lang, t } = useT();
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
        <h1 className="display text-4xl font-normal md:text-5xl">{t("meth.title")}</h1>
        <p className="text-ink-soft mt-3 max-w-[58ch] leading-relaxed">{t("meth.lede")}</p>
      </motion.header>

      <div className="border-rule mt-10 grid gap-8 border-y py-8 sm:grid-cols-3">
        <Verdict
          value={String(survivors.length)}
          label={t("meth.beat")}
          sub={t("meth.ofTested", { n: facts.multiplicity.n_comparisons })}
        />
        <Verdict value={String(facts.hindcast_looks)} label={t("meth.looks")} sub={t("meth.looksSub")} />
        <Verdict value={gb(facts.ledger.total_bytes)} label={t("meth.data")} sub={t("meth.cap", { cap: gb(facts.ledger.budget_bytes) })} />
      </div>

      <Section title={t("meth.skillTitle")}>
        <p className="text-ink-soft mt-2 max-w-[58ch] text-sm leading-relaxed">{t("meth.skillText")}</p>
        {facts.multiplicity.withdrawn_by_leak_free_refit.length > 0 ? (
          <p className="text-mute mt-2 max-w-[58ch] text-xs leading-relaxed">
            {t("meth.withdrawn", {
              orig: facts.multiplicity.n_survivors_original,
              n: facts.multiplicity.withdrawn_by_leak_free_refit.length,
              list: facts.multiplicity.withdrawn_by_leak_free_refit.join(", "),
            })}
          </p>
        ) : null}
        <p className="text-mute mt-2 max-w-[58ch] text-xs leading-relaxed" data-testid="agreement-note">
          {facts.multiplicity.agreeing_targets.length === 0
            ? t("meth.noAgree")
            : t("meth.agree", { list: facts.multiplicity.agreeing_targets.map((x) => targetLabel(x, null, lang)).join(", ") })}
        </p>
        {Object.entries(byDomain).map(([dom, rows]) => (
          <div key={dom} className="mt-6">
            <h3 className="text-mute text-xs">{domainLabel(dom)}</h3>
            <div className="mt-1">
              {rows.map((s) => (
                <StatRow
                  key={s.target}
                  label={`${targetLabel(s.target, null, lang)}, ${s.horizon}w`}
                  value={s.paired_diff.toFixed(3)}
                />
              ))}
            </div>
          </div>
        ))}
      </Section>

      {facts.interval_audit.retraction ? (
        <Section title={lang === "es" ? t("hind.retractionTitle") : facts.interval_audit.retraction.title}>
          <p className="text-ink-soft mt-2 max-w-[58ch] text-sm leading-relaxed">
            {lang === "es" ? t("hind.retractionSummary") : facts.interval_audit.retraction.summary}
          </p>
          <p className="text-mute mt-3 text-xs">
            {t("meth.fullRecord", { doc: facts.interval_audit.retraction.doc, sweep: facts.interval_audit.retraction.sweep })}
          </p>
        </Section>
      ) : null}

      <Section title={t("v12.title")}>
        <V12Results />
      </Section>

      <Section title={t("meth.shipsTitle")}>
        <dl className="border-rule mt-4 divide-y divide-rule border-y">
          {Object.entries(facts.configuration).map(([k, v]) => (
            <div key={k} className="grid gap-1 py-2.5 sm:grid-cols-[9rem_1fr] sm:gap-4">
              <dt className="text-mute text-sm">{t(`meth.cfg.${k}` as MessageKey)}</dt>
              <dd className="text-ink-soft text-sm">{lang === "es" ? t(`meth.cfgv.${k}` as MessageKey) : String(v)}</dd>
            </div>
          ))}
        </dl>
        <p className="text-ink-soft mt-4 max-w-[58ch] text-sm leading-relaxed">
          {t("meth.notML")}
        </p>
      </Section>

      <Section title={t("meth.dataTitle")}>
        <div className="mt-4">
          {facts.sources.map((s) => (
            <StatRow key={s.name} label={s.name} value={lang === "es" ? s.span.replace(" to ", " a ") : s.span} />
          ))}
        </div>
        <p className="text-ink-soft mt-4 max-w-[58ch] text-sm leading-relaxed">
          {t("meth.subx")}
        </p>
      </Section>

      <Section title={t("meth.creditsTitle")}>
        {lang === "es" ? <p className="text-mute mt-2 text-xs">{t("meth.creditsNote")}</p> : null}
        <ul className="border-rule mt-4 divide-y divide-rule border-y" data-testid="credits" lang="en">
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

      <Section title={t("meth.provTitle")}>
        <div className="mt-4">
          <StatRow label={t("meth.training")} value={facts.split.train} />
          <StatRow label={t("meth.validation")} value={facts.split.validate} />
          <StatRow label={t("meth.calibration")} value={facts.split.calibrate} />
          <StatRow label={t("meth.heldOut")} value={facts.split.holdout} />
        </div>
        <div className="mt-4">
          <Disclosure summary={<span className="sr-only">{t("meth.hashes")}</span>} detail={t("meth.hashes")}>
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
              <div>
                <dt>{t("meth.ledger")}</dt>
                <dd>{t("meth.ledgerText", { gb: gb(facts.ledger.total_bytes), n: facts.ledger.n_transfers.toLocaleString() })}</dd>
              </div>
            </dl>
          </Disclosure>
        </div>
      </Section>
    </div>
  );
}
