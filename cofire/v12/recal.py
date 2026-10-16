"""Stage 1 recalibration: q = sigmoid(a + b * logit(p)), with delayed feedback.

The variants are fixed by docs/PREREGISTRATION_V12.md:

* static: (a, b) fitted once on nested out-of-fold predictions and never
  updated (intercept only, or intercept and slope);
* online SGD: from the warm start, one step per newly resolved issue week on
  the mean log-loss gradient over that week's cells;
* EW: (a, b) refitted each issue week on resolved weeks, exponentially
  weighted, held toward the warm start by a penalty worth 10 resolved weeks.

An issue week's outcomes at horizon h become usable at the issue h weeks
later, every cell at once. `run_online` takes the delay as a parameter so the
delayed-feedback gate can show that removing it leaks.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

EPS = 1e-4
WARM_L2 = 1.0  # penalty toward (0, 1), weight on the mean log loss
EW_PRIOR_WEEKS = 10.0


def logit(p: np.ndarray) -> np.ndarray:
    """The logit of probabilities clipped to [EPS, 1 - EPS]."""
    q = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.asarray(np.log(q / (1 - q)), dtype=float)


def sigmoid(z: np.ndarray) -> np.ndarray:
    """The logistic function, with its input clipped to [-30, 30]."""
    return np.asarray(1.0 / (1.0 + np.exp(-np.clip(z, -30, 30))), dtype=float)


def apply(theta: tuple[float, float], p: np.ndarray) -> np.ndarray:
    """Recalibrated probabilities: sigmoid(a + b * logit(p)) for theta = (a, b)."""
    a, b = theta
    return sigmoid(a + b * logit(p))


def _loss_grad(theta: np.ndarray, x: np.ndarray, y: np.ndarray, w: np.ndarray | None,
               slope: bool) -> tuple[float, np.ndarray]:
    a, b = (theta[0], theta[1]) if slope else (theta[0], 1.0)
    z = a + b * x
    q = sigmoid(z)
    ww = np.ones_like(y) if w is None else w
    s = ww.sum()
    ll = -(ww * (y * np.log(np.clip(q, 1e-12, 1)) + (1 - y) * np.log(np.clip(1 - q, 1e-12, 1)))).sum() / s
    r = ww * (q - y)
    g = np.array([r.sum() / s, (r * x).sum() / s]) if slope else np.array([r.sum() / s])
    return float(ll), g


def fit_static(p: np.ndarray, y: np.ndarray, slope: bool) -> tuple[float, float]:
    """Warm start: mean log loss plus WARM_L2 * ||theta - (0, 1)||^2."""
    m = np.isfinite(p) & np.isfinite(y)
    x, yy = logit(p[m]), y[m].astype(float)
    if yy.size == 0 or yy.min() == yy.max():
        return 0.0, 1.0
    centre = np.array([0.0, 1.0]) if slope else np.array([0.0])

    def f(th: np.ndarray) -> tuple[float, np.ndarray]:
        ll, g = _loss_grad(th, x, yy, None, slope)
        d = th - centre
        return ll + WARM_L2 * float(d @ d), g + 2 * WARM_L2 * d

    res = minimize(f, centre.copy(), jac=True, method="L-BFGS-B")
    th = res.x
    return (float(th[0]), float(th[1])) if slope else (float(th[0]), 1.0)


@dataclass(frozen=True)
class Online:
    """One online variant: 'sgd' (lr) or 'ew' (half-life), intercept-only or not."""

    kind: str
    slope: bool
    lr: float = 0.0
    half_life: float = 0.0


def run_online(variant: Online, theta0: tuple[float, float], p: np.ndarray, y: np.ndarray,
               week: np.ndarray, delay: int) -> np.ndarray:
    """Recalibrated q for every row, rows of one stream ordered by issue week.

    `week` is an integer issue-week index. The forecast for issue week t uses
    only outcomes of issue weeks w <= t - delay (a NaN outcome is unresolved
    and skipped). `delay` is the horizon in weeks in every real run.
    """
    x = logit(p)
    yy = np.asarray(y, dtype=float)
    q = np.empty_like(x)
    weeks = np.unique(week)
    by_week = {int(w): np.flatnonzero(week == w) for w in weeks}
    theta = np.array([theta0[0], theta0[1]], dtype=float)
    centre = theta.copy()
    resolved: list[int] = []
    used = 0  # index into `weeks` of the next week whose outcome is not yet used

    # A penalty worth EW_PRIOR_WEEKS resolved weeks: that many weeks' Fisher
    # information at the warm start, from the stream's own predictions.
    h0 = np.zeros((1, 1))
    if variant.kind == "ew":
        qq = sigmoid(theta[0] + theta[1] * x)
        v = qq * (1 - qq)
        h0 = np.array([[v.sum(), (v * x).sum()], [(v * x).sum(), (v * x * x).sum()]]) / len(x) * EW_PRIOR_WEEKS
        if not variant.slope:
            h0 = h0[:1, :1]

    for t in weeks:
        # Bring in every week resolved by issue week t.
        while used < len(weeks) and weeks[used] <= t - delay:
            w = int(weeks[used])
            ok = by_week[w][np.isfinite(yy[by_week[w]])]
            if ok.size:
                if variant.kind == "sgd":
                    _ll, g = _loss_grad(theta if variant.slope else theta[:1], x[ok], yy[ok], None, variant.slope)
                    if variant.slope:
                        theta = theta - variant.lr * g
                    else:
                        theta[0] -= variant.lr * g[0]
                else:
                    resolved.append(w)
            used += 1
        if variant.kind == "ew" and resolved:
            # Each resolved week weighs 0.5 ** (age / half-life), split evenly over its cells.
            parts = [by_week[w][np.isfinite(yy[by_week[w]])] for w in resolved]
            idx = np.concatenate(parts)
            wts = np.concatenate([np.full(pp.size, 0.5 ** ((t - w) / variant.half_life) / pp.size)
                                  for pp, w in zip(parts, resolved, strict=True)])
            c = centre if variant.slope else centre[:1]

            def f(th: np.ndarray, idx: np.ndarray = idx, wts: np.ndarray = wts, c: np.ndarray = c) -> tuple[float, np.ndarray]:
                ll, g = _loss_grad(th, x[idx], yy[idx], wts, variant.slope)
                tot = wts.sum()  # summed over weeks, each week's weights summing to its decay
                d = th - c
                return ll * tot + 0.5 * float(d @ h0 @ d), g * tot + h0 @ d

            start = theta.copy() if variant.slope else theta[:1].copy()
            th = minimize(f, start, jac=True, method="L-BFGS-B").x
            if variant.slope:
                theta = th
            else:
                theta[0] = th[0]
        rows = by_week[int(t)]
        b = theta[1] if variant.slope else 1.0
        q[rows] = sigmoid(theta[0] + b * x[rows])
    return q


VARIANTS: dict[str, Online | str] = {
    "S1-static-a": "static-a",
    "S1-static-ab": "static-ab",
    **{f"S1-online-a@{lr}": Online("sgd", False, lr=lr) for lr in (0.05, 0.2, 0.5)},
    **{f"S1-online-ab@{lr}": Online("sgd", True, lr=lr) for lr in (0.05, 0.2, 0.5)},
    **{f"S1-ew@{hl}": Online("ew", True, half_life=float(hl)) for hl in (8, 26)},
}

FAMILIES = {
    "S1-static-a": ["S1-static-a"],
    "S1-static-ab": ["S1-static-ab"],
    "S1-online-a": [k for k in VARIANTS if k.startswith("S1-online-a@")],
    "S1-online-ab": [k for k in VARIANTS if k.startswith("S1-online-ab@")],
    "S1-ew": [k for k in VARIANTS if k.startswith("S1-ew@")],
}
