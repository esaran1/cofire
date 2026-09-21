# Pre-registration: look 3 on the 2026 holdout

**This session does not take this look.** It ends at a frozen configuration
ready for it. A human approves before anything here runs.

The 2026 holdout stands at **2 looks** on config `0957e415fa7f3fad`, recorded in
`artifacts/hindcast/run_log.json`. Nothing in this session evaluated on 2026,
and `run_pid.py` asserts the absence of 2026 rows before it computes anything.

## Why a third look needs permission at all

A holdout stops being a holdout once it has been consulted enough times to
steer decisions. Two looks have been spent. Every additional look buys
information about 2026 at the cost of some of the guarantee that 2026 is an
honest estimate of future performance. Spending the third look on a
configuration that is still moving would waste it, so the configuration is
frozen first and the questions are fixed here.

## What is frozen

The configuration hash `0957e415fa7f3fad` covers the shipping arm, the
features, the horizons and the conformal settings. The additions from this
session sit **outside** that hash and are therefore not part of look 3 unless a
human decides otherwise:

- the v1 feature groups (ESI, RCI) and their availability guard,
- the probabilistic event targets and the Markov baseline,
- the conformal PID arms.

This is deliberate. Those components have not been validated on two domains
(see `docs/DECISIONS.md` on the Larimer prediction gap), and a look 3 that
mixed validated and unvalidated components could not be attributed either way.

## The questions look 3 answers

Fixed here, in order, with nothing added afterwards.

1. **Coverage.** Does the shipping interval hold its nominal 0.90 on 2026, and
   at which horizons does it fail?
2. **Point accuracy.** MAE and RMSE on `erc_pct` at horizons 2, 4 and 8,
   against the persistence and climatology baselines already defined.
3. **The regime question.** The validation work found held-out years carrying a
   roughly 2.4x residual inflation. Does 2026 show the same inflation, a larger
   one, or none?

## What is not asked

- No comparison between arms. The shipping arm was chosen before this holdout
  and is not reopened by look 3.
- No tuning of any kind. If coverage fails, the finding is that coverage fails.
  The correct response is a new configuration, a new hash, and a fresh holdout
  period, not an adjustment fitted to 2026.
- No per-cell inspection. Look 3 reports domain-level aggregates only. Reading
  individual cells invites exactly the pattern-matching the holdout exists to
  prevent.

## Predictions, recorded before the look

So that a surprising result is visibly surprising rather than accommodated
after the fact:

- Coverage will **fail** at h=8, substantially. Phase 4 measured split conformal
  and ACI collapsing to about 0.36 coverage at h=8 on the validation stream,
  and nothing about 2026 should repair that.
- Coverage at h=2 will land closer to nominal but still below it, somewhere in
  0.75 to 0.88.
- The 2.4x residual inflation will be present in 2026 at a similar magnitude.
  It has appeared in every held-out year tested so far and is not specific to
  any one of them.

If coverage at h=8 comes back near 0.90, that is not a success to be reported
as one. It is evidence that something is wrong with the evaluation, and it must
be investigated before it is believed.

## Stopping rule

One run. The run log gains exactly one record, `look_index` 3. If the run fails
for a technical reason, the failure is recorded and no retry is attempted until
a human reviews the cause, because a retry after a partial look is a fourth
look wearing the name of the third.

## What this session leaves behind

- Config `0957e415fa7f3fad`, unmoved, at 2 looks.
- This document, hashed in STATUS.md.
- A pipeline that refuses to read 2026 rows in the uncertainty path.
