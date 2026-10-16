# Pre-registration: the 2026 unseal (look 4)

Recorded on 2026-10-15, before the date it governs. The owner decided on
2026-10-04 that the 2026 seal stays until **2027-01-12**, and that what is
computed at the unseal is written down and committed before that date
(`docs/DECISIONS.md`, "App Challenge plan"). This is that record.

The scoring is carried out by one script, `scripts/unseal_2026.py`, which
pins this file's sha256. Changing a word here without changing the script
fails the test suite (`tests/test_unseal_2026.py`). The script is not run
before the date, and is run once.

## What is scored

**The forecasts as published, not recomputed.** Every issue in the forecast
record (`artifacts/forecasts/manifest.json`, mirrored in
`app/lib/forward.json`) is scored, exactly as published. Each published file
is read only after its sha256 matches the manifest; any mismatch stops the
script before an outcome is read. Backfilled issues are scored like the
rest, and are marked as backfilled in the output.

**Which forecasts count.** A forecast counts if its target week, the issue
date plus h weeks, is on or before **2026-12-29**, the week of the last 2026
drought map. A forecast for a week in 2027 is outside the sealed year and is
not scored.

**Outcomes.** Outcomes are taken from the project's own stores, through the
same builder and labels the training record used:
- `cofire.ship.build_v11.load` and `cofire.ship.fit_v11.with_targets`;
- drought categories from the U.S. Drought Monitor maps;
- dryness from gridMET ERC as the stored `erc_pct`.

Each outcome is the realized value of the forecast's own target at its
target week, in its own cell.

### 1. Probabilities

For every area and target the app showed as **this cell's forecast**
(rendering state `probability`), pooled over all counted issues and cells:

- the **Brier score**;
- its **reliability term** and **resolution term** (the Murphy
  decomposition, `cofire.model.prob_metrics.brier_decomposition`, 10 bins);
- the **base rate**, the number of scored cell-weeks, and the number of
  weeks with at least one event;
- a **reliability diagram** (10 bins, `cofire.model.stats_lib.reliability_sklearn`).

**Pass criterion, fixed here: the reliability term at most 0.05**, the same
threshold as look 3's test 5 and the app's scoreboard. It is judged only
where at least 100 cell-weeks are scored. With fewer, the result is reported
and marked "too few to judge".

Targets the app showed as the area's usual rate for the season (state
`base_rate`) are scored the same way and reported, but are not judged: they
are not a per-cell forecast. Targets the app showed with no number are not
scored, because nothing was published for them.

### 2. Dryness forecasts

For every area and horizon (2, 4 and 8 weeks), over all counted issues and
cells, the published point forecast of the dryness percentile is compared
with the measured percentile at its target week:
- mean absolute error;
- root mean square error;
- mean error (bias).

There is no pass criterion. These are reported as the errors against what
was measured, as the scoreboard promises.

## What is not done

- No model is refitted, and no rendering decision is changed by the result.
- No new statistic is computed beyond those above.
- The forecast ranges are not scored, because none were shown
  (`docs/CORRECTION_LOOK3.md`).
- No skill claim is made from this look. A claim of skill requires the
  paired shuffled-control test of the earlier preregistrations, and that is
  not part of this scoring.

## Preconditions, checked in code before any outcome is read

1. The date is on or after 2027-01-12 (UTC), the `unseal_date` in
   `app/lib/seal.json`.
2. `COFIRE_ALLOW_LOOK=4` is set. A look at the sealed year takes a
   deliberate act.
3. No file under `cofire/model/` differs from `FREEZE_COMMIT`, and the
   recomputed configuration hash equals
   `ed0c2079a5bc0eee1d0aa11869d3bc5eb0af671b9f30ee0c5114c3b9ca7be157`.
4. `docs/PREREGISTRATION_LOOK3.md` has sha256
   `c5ca907cae475c94f85928e129514593a3e1b9496c80cac45b0e68f9314a9d9a`, and
   this file has the sha256 pinned in the script.
5. The look counter for 2026 reads 3.
6. The output directory, `artifacts/unseal_2026/`, does not exist. The
   script writes to a new directory only and never overwrites a result.
7. The working tree is clean.

If any fails, the script stops, says which, and reads nothing from 2026.

## How it is recorded

- Everything is computed before anything is written.
- The script then writes `artifacts/unseal_2026/` and records the look
  (`cofire.model.freeze.record_look`), so the count becomes 4.
- The output carries the hashes above, the number of forecast files
  verified, and the vintage of every gridMET read.
- gridMET values for late 2026 will still be provisional on 2027-01-12, so
  the output says so, with the date of the data used.
