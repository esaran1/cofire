"use client";

import { PidVsAciFigure, ReliabilityFigure } from "@/components/landing/PidFigure";
import facts from "@/lib/facts.json";

/**
 * Look 3 on the sealed 2026 holdout, reported against each criterion that was
 * written down before the look.
 *
 * Every number here comes from facts.json, generated from artifacts/look3/.
 * Nothing on this page is typed by hand, and nothing is summarised in a way the
 * artifact does not support: the failures are listed as plainly as the passes.
 */

const look = facts.look3;
const cov = look.coverage_series;
const rel = look.reliability;

function Verdict({ pass: ok }: { pass: boolean }) {
  return (
    <span
      className={`num rounded px-1.5 py-0.5 text-[11px] ${ok ? "bg-ink/10 text-ink" : "bg-ember/15 text-ember"}`}
    >
      {ok ? "pass" : "fail"}
    </span>
  );
}

export default function HindcastPage() {
  const pid = cov.filter((r) => r.impl === "reference_pid");
  const failures = rel.filter((r) => r.reliability > 0.05);

  return (
    <div className="mx-auto max-w-3xl px-4 pb-16 pt-6">
      <h1 className="display text-4xl font-normal">The sealed year, opened once</h1>
      <p className="text-ink-soft mt-2 leading-relaxed">
        2026 was held out of every fitting and selection decision this project made. It was examined{" "}
        <span className="num text-ink">{facts.hindcast_looks}</span> times in total, the last under a
        configuration frozen and hashed beforehand, against tests written down before the data was
        read. {look.criteria_passed} of {look.criteria_total} passed.
      </p>

      <dl className="border-rule mt-6 grid grid-cols-2 gap-x-6 gap-y-3 border-y py-4 text-xs">
        <div>
          <dt className="text-mute">Look count</dt>
          <dd className="num text-ink">{facts.hindcast_looks}</dd>
        </div>
        <div>
          <dt className="text-mute">Criteria passed</dt>
          <dd className="num text-ink">
            {look.criteria_passed} of {look.criteria_total}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-mute">Pre-registration sha256</dt>
          <dd className="num text-ink break-all text-[11px]">{facts.preregistration_sha256}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-mute">Configuration hash</dt>
          <dd className="num text-ink break-all text-[11px]">{facts.config_hash}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-mute">Freeze commit</dt>
          <dd className="num text-ink break-all text-[11px]">{facts.freeze_commit}</dd>
        </div>
      </dl>

      <h2 className="mt-10 text-xl font-medium">Each criterion, as written down</h2>
      <table className="mt-3 w-full text-sm">
        <thead className="text-mute border-rule border-b text-left text-xs">
          <tr>
            <th className="py-2 font-normal">Test</th>
            <th className="py-2 font-normal">Threshold</th>
            <th className="py-2 text-right font-normal">Passed</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(look.by_test).map(([k, t]) => (
            <tr key={k} className="border-rule border-b">
              <td className="py-2">{t.name}</td>
              <td className="num text-ink-soft py-2 text-xs">{t.threshold}</td>
              <td className="py-2 text-right">
                <span className="num mr-2 text-xs">
                  {t.n_pass}/{t.n_total}
                </span>
                <Verdict pass={t.n_pass === t.n_total} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className="mt-10 text-xl font-medium">Coverage on 2026: PID against ACI</h2>
      <p className="text-ink-soft mt-2 text-sm leading-relaxed">
        Both controllers ran on the same rows. The adaptive method fell to{" "}
        <span className="num text-ink">{look.aci.roll13_min.toFixed(4)}</span> at its worst thirteen
        weeks and missed <span className="num text-ink">{look.aci.miss_run_max}</span> cell-weeks in
        a row; the reference PID controller held{" "}
        <span className="num text-ink">{look.pid.roll13_min.toFixed(4)}</span> and{" "}
        <span className="num text-ink">{look.pid.miss_run_max}</span>.
      </p>
      <div className="mt-4">
        <PidVsAciFigure rows={cov} />
      </div>

      <table className="mt-6 w-full text-sm">
        <thead className="text-mute border-rule border-b text-left text-xs">
          <tr>
            <th className="py-2 font-normal">County</th>
            <th className="py-2 font-normal">Range</th>
            <th className="py-2 text-right font-normal">Coverage</th>
            <th className="py-2 text-right font-normal">Worst 13wk</th>
            <th className="py-2 text-right font-normal">D0-D1</th>
            <th className="py-2 text-right font-normal">D2+</th>
            <th className="py-2 text-right font-normal">Miss run</th>
          </tr>
        </thead>
        <tbody>
          {pid.map((r) => (
            <tr key={`${r.domain}-${r.horizon}`} className="border-rule border-b">
              <td className="py-2">{r.domain}</td>
              <td className="py-2">{r.horizon}w</td>
              <td className="num py-2 text-right">{r.coverage.toFixed(4)}</td>
              <td className="num py-2 text-right">{r.roll13_min.toFixed(4)}</td>
              <td className="num py-2 text-right">{r.cov_d01.toFixed(4)}</td>
              <td className="num py-2 text-right">{r.cov_d2p.toFixed(4)}</td>
              <td className="num py-2 text-right">{r.miss_run}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className="mt-10 text-xl font-medium">Reliability, the test that failed</h2>
      <p className="text-ink-soft mt-2 text-sm leading-relaxed">
        A probability should be right as often as it claims. That held at two weeks and broke
        further out. <span className="num text-ink">{failures.length}</span> of{" "}
        <span className="num text-ink">{rel.length}</span> targets exceeded the 0.05 threshold set
        before the look; every one of them now shows a regional base rate instead of a per-cell
        number, which is the consequence the pre-registration fixed in advance.
      </p>
      <div className="mt-4">
        <ReliabilityFigure byHorizon={look.reliability_by_horizon} />
      </div>

      <h3 className="mt-6 text-sm font-medium">Every target that failed</h3>
      <table className="mt-2 w-full text-sm">
        <thead className="text-mute border-rule border-b text-left text-xs">
          <tr>
            <th className="py-2 font-normal">County</th>
            <th className="py-2 font-normal">Target</th>
            <th className="py-2 text-right font-normal">Reliability</th>
            <th className="py-2 text-right font-normal">Threshold</th>
          </tr>
        </thead>
        <tbody>
          {failures.map((r) => (
            <tr key={`${r.domain}-${r.target}`} className="border-rule border-b">
              <td className="py-2">{r.domain}</td>
              <td className="num py-2 text-xs">{r.target}</td>
              <td className="num text-ember py-2 text-right">{r.reliability.toFixed(4)}</td>
              <td className="num text-mute py-2 text-right">0.05</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className="mt-10 text-xl font-medium">Width ratio on 2026</h2>
      <p className="text-ink-soft mt-2 text-sm leading-relaxed">
        Reported, and by the rule fixed before the look it changes nothing about what the app shows.
        Every ratio is below 1, meaning the intervals were narrower than the historical range on the
        sealed year, including the two Larimer ranges that the training record classified the other
        way.
      </p>
      <table className="mt-3 w-full text-sm">
        <thead className="text-mute border-rule border-b text-left text-xs">
          <tr>
            <th className="py-2 font-normal">County</th>
            <th className="py-2 font-normal">Range</th>
            <th className="py-2 text-right font-normal">Ratio</th>
            <th className="py-2 text-right font-normal">95% interval</th>
          </tr>
        </thead>
        <tbody>
          {look.width_ratio.map((r) => (
            <tr key={`${r.domain}-${r.horizon}`} className="border-rule border-b">
              <td className="py-2">{r.domain}</td>
              <td className="py-2">{r.horizon}w</td>
              <td className="num py-2 text-right">{r.ratio.toFixed(3)}</td>
              <td className="num text-ink-soft py-2 text-right text-xs">
                {r.ratio_lo.toFixed(3)} to {r.ratio_hi.toFixed(3)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <a
        href="/?issue=2026-05-05&horizon=2"
        className="bg-ochre text-ink mt-10 inline-block rounded-lg px-4 py-2 font-medium"
      >
        Replay the 2026-05-05 issue
      </a>
    </div>
  );
}
