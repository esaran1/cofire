"use client";

import facts from "@/lib/facts.json";

/**
 * What ships, what it was built from, and what it is allowed to claim.
 *
 * Every figure comes from facts.json, generated from artifacts. The survivor
 * list is stated plainly because it is the only place this project claims its
 * forecasts beat a baseline, and a reader should be able to check that claim
 * against the same list the copy lint checks against.
 */

const gb = (b: number) => `${(b / 1e9).toFixed(2)} GB`;

export default function AboutPage() {
  const survivors = facts.survivors;
  const byDomain = survivors.reduce<Record<string, typeof survivors>>((acc, s) => {
    (acc[s.domain] ||= []).push(s);
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-3xl px-4 pb-16 pt-6">
      <h1 className="display text-4xl font-normal">About COFIRE</h1>
      <p className="mt-4 text-lg leading-relaxed">
        COFIRE forecasts drought and fire-spread conditions in two Colorado counties, 2 to 8 weeks
        ahead, and states how uncertain each forecast is. Where the uncertainty cannot be supported
        by the record, it says so and shows the historical range instead. It is not a forecast of
        ignitions.
      </p>

      <h2 className="mt-10 text-xl font-medium">What ships, by target family</h2>
      <dl className="border-rule mt-3 divide-y divide-rule border-y text-sm">
        {Object.entries(facts.configuration).map(([k, v]) => (
          <div key={k} className="grid grid-cols-[10rem_1fr] gap-4 py-3">
            <dt className="text-mute capitalize">{k.replace(/_/g, " ")}</dt>
            <dd className="text-ink-soft">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="text-ink-soft mt-3 text-sm leading-relaxed">
        The forecasts are empirical conditional models, not machine learning. On this record a
        transition table and a damped persistence rule beat every trained arm that was tried, so
        those are what ship.
      </p>

      <h2 className="mt-10 text-xl font-medium">Where the forecasts beat their baselines</h2>
      <p className="text-ink-soft mt-2 text-sm leading-relaxed">
        <span className="num text-ink">{survivors.length}</span> of{" "}
        <span className="num text-ink">{facts.multiplicity.n_comparisons}</span> comparisons
        survived, after multiplicity control at q={facts.multiplicity.q} and a shuffled-target
        check. Skill is claimed here and nowhere else. A comparison had to beat its own targets
        shuffled in place, because a forecast can beat a baseline through probability spread alone.
      </p>
      {Object.entries(byDomain).map(([dom, rows]) => (
        <div key={dom} className="mt-4">
          <h3 className="text-sm font-medium capitalize">{dom}</h3>
          <table className="mt-1 w-full text-sm">
            <thead className="text-mute border-rule border-b text-left text-xs">
              <tr>
                <th className="py-2 font-normal">Target</th>
                <th className="py-2 font-normal">Range</th>
                <th className="py-2 text-right font-normal">Margin over baseline</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={`${s.target}`} className="border-rule border-b">
                  <td className="num py-2 text-xs">{s.target.replace(/_h\d+$/, "")}</td>
                  <td className="py-2">{s.horizon}w</td>
                  <td className="num py-2 text-right text-xs">
                    {s.paired_diff.toFixed(3)}{" "}
                    <span className="text-mute">
                      [{s.paired_lo.toFixed(3)}, {s.paired_hi.toFixed(3)}]
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      <h2 className="mt-10 text-xl font-medium">Data sources</h2>
      <table className="mt-3 w-full text-sm">
        <thead className="text-mute border-rule border-b text-left text-xs">
          <tr>
            <th className="py-2 font-normal">Source</th>
            <th className="py-2 font-normal">Record span</th>
            <th className="py-2 font-normal">Role</th>
          </tr>
        </thead>
        <tbody>
          {facts.sources.map((s) => (
            <tr key={s.name} className="border-rule border-b">
              <td className="py-2">{s.name}</td>
              <td className="num py-2 text-xs">{s.span}</td>
              <td className="text-ink-soft py-2 text-xs">{s.role}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-ink-soft mt-3 text-sm leading-relaxed">
        A sub-seasonal weather model was evaluated once, by a rule fixed in advance:{" "}
        <span className="num text-ink">{facts.subx.n_ci_above_zero}</span> of{" "}
        <span className="num text-ink">{facts.subx.n_comparisons}</span> comparisons cleared zero in
        one county and none cleared it in both, so{" "}
        <span className="num text-ink">{facts.subx.n_switched}</span> targets adopted it.
      </p>

      <h2 className="mt-10 text-xl font-medium">Download ledger</h2>
      <p className="text-ink-soft mt-2 text-sm leading-relaxed">
        Every byte fetched over the network is recorded.{" "}
        <span className="num text-ink">{gb(facts.ledger.total_bytes)}</span> across{" "}
        <span className="num text-ink">{facts.ledger.n_transfers.toLocaleString()}</span> transfers,
        against a <span className="num text-ink">{gb(facts.ledger.budget_bytes)}</span> cap. The
        ledger is append-only: a mis-estimate is corrected by appending a correction with its
        evidence, never by rewriting the original entry.
      </p>

      <h2 className="mt-10 text-xl font-medium">Provenance</h2>
      <dl className="border-rule mt-3 grid grid-cols-1 gap-y-3 border-y py-4 text-xs">
        <div>
          <dt className="text-mute">Splits</dt>
          <dd className="num text-ink">
            train {facts.split.train} · validate {facts.split.validate} · calibrate{" "}
            {facts.split.calibrate} · holdout {facts.split.holdout}
          </dd>
        </div>
        <div>
          <dt className="text-mute">Looks at the sealed holdout</dt>
          <dd className="num text-ink">{facts.hindcast_looks}</dd>
        </div>
        <div>
          <dt className="text-mute">Pre-registration sha256</dt>
          <dd className="num text-ink break-all">{facts.preregistration_sha256}</dd>
        </div>
        <div>
          <dt className="text-mute">Configuration hash</dt>
          <dd className="num text-ink break-all">{facts.config_hash}</dd>
        </div>
        <div>
          <dt className="text-mute">Freeze commit</dt>
          <dd className="num text-ink break-all">{facts.freeze_commit}</dd>
        </div>
      </dl>
      <p className="text-mute mt-4 text-xs leading-relaxed">
        Not a forecast of ignitions. Forecasts are for {facts.domains.join(" and ")} counties at{" "}
        {facts.resolution_m / 1000} km resolution, and the displayed value is the cell's own, not an
        interpolation to a point.
      </p>
    </div>
  );
}
