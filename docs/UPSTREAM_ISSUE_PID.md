# Draft: upstream issue for conformal-time-series

To be filed by the student on
https://github.com/aangelopoulos/conformal-time-series. Drafted by the AI
agent from `docs/LEAK_SWEEP.md`. Before filing, check that `core/methods.py`
on the upstream default branch still has the line quoted below. The copy in
this repository (`cofire/model/uncertainty/reference_pid.py`) was vendored
unmodified and may be older.

---

**Title:** `proportional_lr` step size uses scores not yet observed when `ahead > 1`

**Body:**

In `quantile_integrator_log_scorecaster` (`core/methods.py`), the comment says
the update at time `t` uses information "up to and including
`t_pred = t - ahead + 1`". The proportional step size does not follow this:

```python
t_lr = t
t_lr_min = max(t_lr - T_burnin, 0)
lr_t = lr * (scores[t_lr_min:t_lr].max() - scores[t_lr_min:t_lr].min()) if proportional_lr and t_lr > 0 else lr
```

The window ends at `t - 1`, so for `ahead > 1` it includes
`scores[t_pred + 1 .. t - 1]`, which have not been observed when the forecast
for `t + 1` is made. The quantile and integrator updates are lagged correctly;
only the step size looks ahead. With `ahead = 1` there is no problem.

**Reproduction** (run from the repository root):

```python
import numpy as np
from core.methods import quantile_integrator_log

rng = np.random.default_rng(0)
scores = rng.exponential(size=300)
ahead, t = 4, 200
bumped = scores.copy()
bumped[t - 1] = 50.0  # not yet observed when q[t + 1] is set
kw = dict(alpha=0.1, lr=0.05, Csat=5.0, KI=0.0, ahead=ahead, T_burnin=100)
print(quantile_integrator_log(scores, **kw)["q"][t + 1],
      quantile_integrator_log(bumped, **kw)["q"][t + 1])
```

Changing an unobserved score moves the quantile (2.177 to 1.947 on our copy).
With `proportional_lr=False`, both values are identical (2.110).

**Suggested fix:** end the window at `t_pred`:

```python
t_lr = t - ahead + 1
```

On our copy, this makes the two values equal and leaves the output for
`ahead = 1` unchanged, bit for bit.

**Context:** we found this with a test that changes every score not observable
at forecast time and fails if the output moves. We used it on a weekly
fire-danger forecast at 2 to 8 week horizons. Thank you for publishing the
reference code; it is what made the check possible.
