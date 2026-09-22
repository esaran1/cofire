"""Probabilistic targets and their baselines. INTENDED FOR HAND-REWRITE.

Why the targets changed
-----------------------
MAE on a drought *level* structurally favours persistence: USDM categories are
piecewise constant for weeks at a time, so "same as today" is close to optimal
on most rows and the loss is dominated by the many rows where nothing happened.
Regressing the *delta* failed for the mirror-image reason: most deltas are
exactly zero, so the regression learns to predict zero and the informative rows
are drowned.

Both failures share a cause. The learnable signal is not in the level or in the
mean change; it is in the probability of a transition. So the headline targets
are events:

  drought   P(intensify by >= 1 category), P(>= 2), P(improve by >= 1),
            P(no change), P(category >= D2), P(category >= D3)
  fire      P(ERC percentile > 80), P(> 90), P(> 97)

Fire thresholds follow operational fire-danger practice: ERC percentile bands
against the local climatological distribution are how agencies set staffing and
restriction levels, and the 80th, 90th and 97th percentiles are the common
break points for elevated, high and extreme. The choice is documented rather
than tuned.

The Markov baseline
-------------------
For transition targets, persistence is a weak opponent and climatology is only
slightly better. The honest baseline is the empirical transition matrix: given
the current USDM category and the calendar month, how often did the category
move by that much over h weeks in the training years? That encodes the real
persistence-and-drift structure of drought, and it is hard to beat. If the
models do not beat it, that is the finding.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

HORIZONS = (2, 4, 8)
N_CATEGORIES = 5  # USDM 0..4 after the None/D0 merge documented in DECISIONS.md

# Operational fire-danger percentile break points.
ERC_THRESHOLDS = (80, 90, 97)


# ----------------------------------------------------------------- targets


def drought_event_targets(frame: pd.DataFrame, horizon: int) -> dict[str, np.ndarray]:
    """Binary drought events at t+h, as 0/1 arrays aligned to `frame`.

    NaN where the future label is missing, so downstream masking is explicit
    rather than an accidental zero.
    """
    now = pd.to_numeric(frame.get("usdm"), errors="coerce").to_numpy(dtype=float)
    fut = pd.to_numeric(frame.get(f"usdm_h{horizon}"), errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(now) & np.isfinite(fut)
    delta = np.where(valid, fut - now, np.nan)

    def ev(mask: np.ndarray) -> np.ndarray:
        out = np.full(now.shape, np.nan, dtype="float32")
        out[valid] = mask[valid].astype("float32")
        return out

    return {
        f"d_intensify1_h{horizon}": ev(delta >= 1),
        f"d_intensify2_h{horizon}": ev(delta >= 2),
        f"d_improve1_h{horizon}": ev(delta <= -1),
        f"d_nochange_h{horizon}": ev(delta == 0),
        f"d_ge2_h{horizon}": ev(fut >= 2),
        f"d_ge3_h{horizon}": ev(fut >= 3),
    }


def fire_event_targets(frame: pd.DataFrame, horizon: int) -> dict[str, np.ndarray]:
    """Binary ERC-percentile exceedance events at t+h."""
    fut = pd.to_numeric(frame.get(f"erc_pct_h{horizon}"), errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(fut)
    out: dict[str, np.ndarray] = {}
    for thr in ERC_THRESHOLDS:
        a = np.full(fut.shape, np.nan, dtype="float32")
        a[valid] = (fut[valid] > thr).astype("float32")
        out[f"f_gt{thr}_h{horizon}"] = a
    return out


def all_event_targets(frame: pd.DataFrame, horizons: tuple[int, ...] = HORIZONS) -> pd.DataFrame:
    """Attach every event target for every horizon."""
    out = frame.copy()
    for h in horizons:
        for k, v in drought_event_targets(frame, h).items():
            out[k] = v
        for k, v in fire_event_targets(frame, h).items():
            out[k] = v
    return out


def target_names(horizons: tuple[int, ...] = HORIZONS) -> list[str]:
    names: list[str] = []
    for h in horizons:
        names += [
            f"d_intensify1_h{h}",
            f"d_intensify2_h{h}",
            f"d_improve1_h{h}",
            f"d_nochange_h{h}",
            f"d_ge2_h{h}",
            f"d_ge3_h{h}",
        ]
        names += [f"f_gt{t}_h{h}" for t in ERC_THRESHOLDS]
    return names


# ---------------------------------------------------------------- baselines


SEASONS = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
           6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}


def _season(month: int) -> str:
    return SEASONS[int(month)]


@dataclass
class MarkovBaseline:
    """Empirical h-week USDM transition probabilities, pooled across cells.

    Conditioned on (current category, season), with a month refinement only
    where enough *independent* transitions support it. Estimated on training
    rows only, and direct at h steps rather than a one-step matrix raised to the
    h power, so no first-order assumption is imposed.

    Why weeks and not rows
    ----------------------
    USDM moves in spatially coherent blocks. Measured on Pueblo training data,
    84% of (category, month, week) blocks are more than 98% unanimous across all
    432 cells: a week contributes roughly one observation, not 432. Counting
    rows made a single drought episode look like a thousand independent
    transitions, so `min_count=30` was satisfied by one week of one county and
    the estimator memorised specific episodes. Its training Brier was 0.0758
    against a constant's 0.1272, and its validation Brier 0.2245 against 0.0936:
    the bound held in sample and inverted out of sample, which is the signature
    of overfitting rather than of degenerate probabilities.

    The counts are therefore *week-weighted*: each (week, category) contributes
    its share once, no matter how many cells carried it.

    The prior
    ---------
    A Dirichlet prior centred on the pooled unconditional h-step transition
    rates, not on a uniform row. Uniform smoothing pulls a rare-category row
    toward "equally likely to land anywhere", which is a worse forecast than the
    marginal it replaces. `prior_strength` is expressed in effective weeks.
    """

    horizon: int
    # Minimum independent transitions, counted in weeks rather than rows.
    # Selected on validation across both domains and all drought targets: 32 is
    # the largest gate at which neither domain violates the training bound.
    # Pueblo would prefer 48 (validation Brier 0.0892 against 0.0901), but at 48
    # Larimer falls back for every category and fails 12 of 18 targets, so 32 is
    # the value that holds on both. Never tuned against the holdout.
    min_weeks: int = 32
    # Dirichlet prior strength in effective weeks, centred on the pooled rates.
    prior_strength: float = 4.0
    by_cat_month: dict[tuple[int, int], np.ndarray] = field(default_factory=dict)
    by_cat_season: dict[tuple[int, str], np.ndarray] = field(default_factory=dict)
    by_cat: dict[int, np.ndarray] = field(default_factory=dict)
    global_row: np.ndarray = field(default_factory=lambda: np.full(N_CATEGORIES, 1.0 / N_CATEGORIES))

    def _counts_and_support(
        self, ci: np.ndarray, fi: np.ndarray, weeks: np.ndarray, mask: np.ndarray
    ) -> tuple[np.ndarray, int]:
        """Row transition counts, plus the number of independent weeks behind them.

        The two units do different jobs, and conflating them was the bug:

        - **Weeks measure support.** USDM moves in spatially coherent blocks, so
          432 cells in one week carry roughly one week's worth of information.
          The week count gates whether a cell may be estimated at all.
        - **Rows estimate the rate.** The score is Brier over rows, and the
          minimiser of row-level Brier is the row mean. Estimating from
          week-weighted counts instead made every category row off by up to
          0.05 in a consistent direction, because weeks with many cells in a
          category were downweighted in fitting but not in scoring. That, not
          degenerate probabilities and not the prior, is what broke the
          training bound.

        So: gate on weeks, estimate on rows.
        """
        if not mask.any():
            return np.zeros(N_CATEGORIES, dtype=float), 0
        counts = np.bincount(fi[mask], minlength=N_CATEGORIES).astype(float)
        return counts, int(np.unique(weeks[mask]).size)

    def _posterior(self, counts: np.ndarray, n_weeks: int) -> np.ndarray:
        """Dirichlet posterior centred on the pooled unconditional rates.

        The prior strength is scaled by how much independent support the cell
        has. A cell backed by many weeks is allowed to depart from the pooled
        rates; a thin one is held close to them. Without this the prior is a
        fixed nudge that pulls even well-supported rows off their own evidence,
        which is what made the estimator fail the training bound by a small but
        real margin on the short-horizon intensify targets.
        """
        if n_weeks <= 0:
            return np.asarray(self.global_row, dtype=float)
        prior = self.global_row * self.prior_strength
        post = counts + prior
        return np.asarray(post / post.sum(), dtype=float)

    def fit(self, frame: pd.DataFrame) -> MarkovBaseline:
        now = pd.to_numeric(frame["usdm"], errors="coerce").to_numpy(dtype=float)
        fut = pd.to_numeric(frame[f"usdm_h{self.horizon}"], errors="coerce").to_numpy(dtype=float)
        t = pd.to_datetime(frame["time"])
        month = t.dt.month.to_numpy()
        week = t.to_numpy()
        ok = np.isfinite(now) & np.isfinite(fut)
        ci = np.clip(np.round(now[ok]), 0, N_CATEGORIES - 1).astype(int)
        fi = np.clip(np.round(fut[ok]), 0, N_CATEGORIES - 1).astype(int)
        mi, wi = month[ok], week[ok]

        # Pooled unconditional rates are the prior centre.
        glob, _ = self._counts_and_support(ci, fi, wi, np.ones(ci.shape, dtype=bool))
        self.global_row = glob / glob.sum() if glob.sum() > 0 else self.global_row

        seasons = np.array([_season(m) for m in mi])
        for c in range(N_CATEGORIES):
            m = ci == c
            cnt, nw = self._counts_and_support(ci, fi, wi, m)
            if nw >= self.min_weeks:
                self.by_cat[c] = self._posterior(cnt, nw)
            for sea in ("DJF", "MAM", "JJA", "SON"):
                ms = m & (seasons == sea)
                cnt_s, nw_s = self._counts_and_support(ci, fi, wi, ms)
                if nw_s >= self.min_weeks:
                    self.by_cat_season[(c, sea)] = self._posterior(cnt_s, nw_s)
            for mo in range(1, 13):
                mm = m & (mi == mo)
                cnt_m, nw_m = self._counts_and_support(ci, fi, wi, mm)
                # Month is a refinement of season, so it needs its own support.
                if nw_m >= self.min_weeks:
                    self.by_cat_month[(c, mo)] = self._posterior(cnt_m, nw_m)
        return self

    # How much mass the last-resort fallback puts on staying put. Selected on
    # validation across both real domains: Larimer needs at least 0.75 to
    # satisfy the training bound on the improve targets, and Pueblo is
    # indifferent across the whole range. Never tuned against the holdout.
    persistence_weight: float = 0.75

    def _persistence_row(self, c: int) -> np.ndarray:
        """Blend persistence with the unconditional marginal. Last resort only.

        Two failure modes bracket this, and the blend avoids both:

        - Pure `global_row` is the marginal over *destinations* and forgets
          where the chain started. It told a D2 cell it would most likely be D0,
          because D0 is the commonest state overall, and inflated
          `d_improve1_h2` Brier by 642% over the constant on Larimer.
        - Pure persistence is a point mass, so it states P(category >= 3) = 1
          for a cell sitting at D3. That is overconfident for absolute-level
          targets, and it broke the bound on `d_ge3_h8` in the synthetic test.

        A drought category is persistent but not immovable, so the fallback says
        both: half the mass stays, half follows the pooled rates.
        """
        idx = int(np.clip(c, 0, N_CATEGORIES - 1))
        stay = np.zeros(N_CATEGORIES, dtype=float)
        stay[idx] = 1.0
        w = float(np.clip(self.persistence_weight, 0.0, 1.0))
        row = w * stay + (1.0 - w) * np.asarray(self.global_row, dtype=float)
        return np.asarray(row / row.sum(), dtype=float)

    def row(self, category: int, month: int) -> np.ndarray:
        """Most specific row with enough independent support.

        month, then season, then category, then persistence. Each step up is
        taken only when the finer cell lacked enough *independent weeks* to be
        estimated, so specificity is bought with evidence rather than assumed.
        """
        c = int(np.clip(category, 0, N_CATEGORIES - 1))
        if (c, int(month)) in self.by_cat_month:
            return self.by_cat_month[(c, int(month))]
        sea = _season(month)
        if (c, sea) in self.by_cat_season:
            return self.by_cat_season[(c, sea)]
        if c in self.by_cat:
            return self.by_cat[c]
        return self._persistence_row(c)

    def predict_matrix(self, frame: pd.DataFrame) -> np.ndarray:
        """(n_rows, N_CATEGORIES) distribution over the category at t+h."""
        now = pd.to_numeric(frame["usdm"], errors="coerce").to_numpy(dtype=float)
        month = pd.to_datetime(frame["time"]).dt.month.to_numpy()
        out = np.empty((len(frame), N_CATEGORIES), dtype="float32")
        for i in range(len(frame)):
            c = 0 if not np.isfinite(now[i]) else int(np.clip(round(now[i]), 0, N_CATEGORIES - 1))
            out[i] = self.row(c, int(month[i]))
        return out

    def predict_events(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        """Event probabilities implied by the transition distribution."""
        p = self.predict_matrix(frame)
        now = pd.to_numeric(frame["usdm"], errors="coerce").to_numpy(dtype=float)
        cur = np.clip(np.nan_to_num(np.round(now)), 0, N_CATEGORIES - 1).astype(int)
        h = self.horizon
        cats = np.arange(N_CATEGORIES)[None, :]
        cur_col = cur[:, None]
        return {
            f"d_intensify1_h{h}": (p * (cats >= cur_col + 1)).sum(axis=1),
            f"d_intensify2_h{h}": (p * (cats >= cur_col + 2)).sum(axis=1),
            f"d_improve1_h{h}": (p * (cats <= cur_col - 1)).sum(axis=1),
            f"d_nochange_h{h}": (p * (cats == cur_col)).sum(axis=1),
            f"d_ge2_h{h}": p[:, 2:].sum(axis=1),
            f"d_ge3_h{h}": p[:, 3:].sum(axis=1),
        }


def climatology_event_baseline(
    train: pd.DataFrame, target: str, index: pd.DataFrame
) -> np.ndarray:
    """Per-cell week-of-year base rate for an event, fit on training rows."""
    tr = train[["cell_id", "time", target]].copy()
    tr["woy"] = pd.to_datetime(tr["time"]).dt.isocalendar().week.astype(int)
    rate = tr.groupby(["cell_id", "woy"])[target].mean()
    overall = float(pd.to_numeric(tr[target], errors="coerce").mean())

    idx = index[["cell_id", "time"]].copy()
    idx["woy"] = pd.to_datetime(idx["time"]).dt.isocalendar().week.astype(int)
    joined = idx.join(rate, on=["cell_id", "woy"])
    vals: np.ndarray = pd.to_numeric(joined[target], errors="coerce").fillna(overall).to_numpy(dtype="float32")
    return vals


def persistence_event_baseline(frame: pd.DataFrame, target: str) -> np.ndarray:
    """Current state as a 0/1 forecast for exceedance targets.

    For transition targets persistence means "nothing changes", which is a
    probability of 0 for intensify/improve and 1 for no-change. Stated that way
    it is obviously a weak forecast, which is exactly why the Markov baseline
    exists.
    """
    n = len(frame)
    if target.startswith("d_nochange"):
        return np.ones(n, dtype="float32")
    if target.startswith("d_intensify") or target.startswith("d_improve"):
        return np.zeros(n, dtype="float32")
    if target.startswith("d_ge"):
        k = int(target.split("_ge")[1].split("_")[0])
        now = pd.to_numeric(frame["usdm"], errors="coerce").to_numpy(dtype=float)
        ge: np.ndarray = (np.nan_to_num(now) >= k).astype("float32")
        return ge
    if target.startswith("f_gt"):
        thr = int(target.split("_gt")[1].split("_")[0])
        now = pd.to_numeric(frame.get("erc_pct"), errors="coerce").to_numpy(dtype=float)
        gt: np.ndarray = (np.nan_to_num(now) > thr).astype("float32")
        return gt
    return np.full(n, 0.5, dtype="float32")


def constant_event_baseline(
    train: pd.DataFrame, target: str, index: pd.DataFrame
) -> np.ndarray:
    """The training base rate, forecast everywhere.

    The dullest possible forecast, and the one that matters most. Brier is
    dominated by calibration rather than discrimination, so a constant at the
    right level is extremely hard to beat on rare events: it has zero resolution
    but also zero reliability error. A model that cannot beat it has bought
    ranking ability at the cost of calibration, and the Brier score will say so
    even when the AUC looks respectable.

    Including this as a baseline is what stops "skill against Markov" from being
    reported as skill when the real story is that Markov was miscalibrated.
    """
    rate = float(pd.to_numeric(train[target], errors="coerce").mean())
    if not np.isfinite(rate):
        rate = 0.0
    return np.full(len(index), rate, dtype="float32")


def seasonal_climatology_baseline(
    train: pd.DataFrame,
    target: str,
    index: pd.DataFrame,
    half_window: int = 3,
    min_positives: float = 5.0,
) -> np.ndarray:
    """Domain-wide week-of-year event rate, smoothed on the circle.

    The right primary reference. A flat training constant credits a model for
    knowing the calendar, and these targets are strongly seasonal even though
    `erc_pct` is already week-of-year relative: measured on Pueblo, the monthly
    rate of `f_gt90_h4` varies 4.5x and `d_intensify1_h4` 11.6x.

    Domain-wide rather than per cell, for the same reason the Markov baseline
    gates on weeks: within a week the cells are near duplicates, so a per-cell
    week-of-year rate would rest on a handful of independent observations and
    fit the episodes. Smoothed with a circular window because week 52 and week 1
    are adjacent, and shrunk toward the overall training rate wherever a window
    holds too few positives to estimate a rate at all.
    """
    tr = train[["time", target]].copy()
    tr["woy"] = pd.to_datetime(tr["time"]).dt.isocalendar().week.astype(int).clip(1, 52)
    y = pd.to_numeric(tr[target], errors="coerce")
    tr = tr.assign(_y=y).dropna(subset=["_y"])
    overall = float(tr["_y"].mean()) if len(tr) else 0.0

    by_woy = tr.groupby("woy")["_y"].agg(["sum", "count"])
    sums = np.zeros(53, dtype=float)
    counts = np.zeros(53, dtype=float)
    for w, row in by_woy.iterrows():
        sums[int(w)] = float(row["sum"])
        counts[int(w)] = float(row["count"])

    rate = np.full(53, overall, dtype=float)
    for w in range(1, 53):
        # Circular window: weeks 52 and 1 are neighbours.
        idx = [((w - 1 + d) % 52) + 1 for d in range(-half_window, half_window + 1)]
        s = float(sums[idx].sum())
        n = float(counts[idx].sum())
        if n <= 0:
            continue
        # Shrink toward the overall rate when the window is thin on positives.
        w_obs = s / max(s + min_positives, 1e-9)
        rate[w] = w_obs * (s / n) + (1.0 - w_obs) * overall

    woy_idx = pd.to_datetime(index["time"]).dt.isocalendar().week.astype(int).clip(1, 52)
    return np.asarray(rate[woy_idx.to_numpy()], dtype="float32")


ERC_DECILES = 10


def fire_transition_baseline(
    train: pd.DataFrame,
    target: str,
    index: pd.DataFrame,
    min_weeks: int = 32,
    persistence_weight: float = 0.75,
) -> np.ndarray:
    """Empirical exceedance rate by current ERC decile and season.

    The fire analogue of the Markov drought baseline, and it needs the same
    three corrections that one needed:

    - **Support is counted in weeks, not rows.** Cells within a week move
      together, so a (decile, season) cell backed by 400 rows from two weeks has
      two observations of evidence, not four hundred.
    - **Rates are estimated from rows.** Row-level Brier is minimised by the row
      mean, so the gate and the estimate use different units deliberately.
    - **The fallback blends toward staying put**, rather than falling back to
      the unconditional rate, which forgets where the series started.

    Conditioning on the current ERC decile is the right structure for an
    exceedance target: a cell already at the 95th percentile has a very
    different chance of exceeding the 97th in four weeks than one at the 20th.
    """
    tr = train[["time", "erc_pct", target]].copy()
    tr["time"] = pd.to_datetime(tr["time"])
    tr["season"] = tr["time"].dt.month.map(SEASONS)
    pct = pd.to_numeric(tr["erc_pct"], errors="coerce")
    tr["dec"] = np.clip((pct // ERC_DECILES).astype("float"), 0, ERC_DECILES - 1)
    y = pd.to_numeric(tr[target], errors="coerce")
    tr = tr.assign(_y=y).dropna(subset=["_y", "dec"])
    overall = float(tr["_y"].mean()) if len(tr) else 0.0

    by_ds: dict[tuple[float, str], float] = {}
    by_d: dict[float, float] = {}
    for (dec, sea), g in tr.groupby(["dec", "season"]):
        if g["time"].nunique() >= min_weeks:
            by_ds[(float(dec), str(sea))] = float(g["_y"].mean())
    for dec, g in tr.groupby("dec"):
        if g["time"].nunique() >= min_weeks:
            by_d[float(dec)] = float(g["_y"].mean())

    idx = index[["time", "erc_pct"]].copy()
    idx["time"] = pd.to_datetime(idx["time"])
    idx["season"] = idx["time"].dt.month.map(SEASONS)
    ipct = pd.to_numeric(idx["erc_pct"], errors="coerce")
    idx["dec"] = np.clip((ipct // ERC_DECILES).astype("float"), 0, ERC_DECILES - 1)

    out = np.full(len(idx), overall, dtype="float32")
    for i, (dec, sea) in enumerate(zip(idx["dec"].to_numpy(), idx["season"].to_numpy(), strict=True)):
        if not np.isfinite(dec):
            continue
        key = (float(dec), str(sea))
        if key in by_ds:
            out[i] = by_ds[key]
        elif float(dec) in by_d:
            out[i] = by_d[float(dec)]
        else:
            # Blend toward the decile's own implied persistence rather than
            # collapsing to the overall rate.
            implied = 1.0 if float(dec) >= ERC_DECILES - 1 else 0.0
            out[i] = persistence_weight * implied + (1.0 - persistence_weight) * overall
    return out


def damped_persistence_baseline(
    train: pd.DataFrame, target: str, index: pd.DataFrame
) -> np.ndarray:
    """Logistic regression of the target on the current ERC percentile alone.

    One predictor, two parameters. It asks whether anything beyond today's fire
    danger is needed at all, and on an exceedance target that is a serious
    question: a model that cannot clear this has learned nothing the current
    percentile did not already say.
    """
    from sklearn.linear_model import LogisticRegression

    x = pd.to_numeric(train["erc_pct"], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(train[target], errors="coerce").to_numpy(dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 50 or len(np.unique(y[m])) < 2:
        rate = float(np.nanmean(y)) if np.isfinite(y).any() else 0.0
        return np.full(len(index), rate, dtype="float32")
    lr = LogisticRegression(max_iter=400)
    lr.fit(x[m].reshape(-1, 1), y[m])
    xi = pd.to_numeric(index["erc_pct"], errors="coerce").to_numpy(dtype=float)
    xi = np.where(np.isfinite(xi), xi, float(np.nanmedian(x[m])))
    return np.asarray(lr.predict_proba(xi.reshape(-1, 1))[:, 1], dtype="float32")
