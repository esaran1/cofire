"""The explanation tables reproduce the live model exactly, from training years only."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path("artifacts/v13/explain")
EXPORT = Path("artifacts/ship/forecast_issues.parquet")
DOMAINS = ("denver", "upper_south_platte", "dillon", "larimer", "pueblo")


def _load(d: str) -> dict:
    return json.loads((ROOT / f"{d}.json").read_text())


def _event(t: str, c: int) -> np.ndarray:
    k = np.arange(5)
    return {"d_ge2": k >= 2, "d_ge3": k >= 3, "d_improve1": k <= c - 1, "d_intensify1": k >= c + 1,
            "d_intensify2": k >= c + 2, "d_nochange": k == c}[t]


@pytest.mark.parametrize("d", DOMAINS)
def test_training_window_ends_in_2021(d: str) -> None:
    assert _load(d)["train"] == ["2007-01-01", "2021-12-31"]
    for h, tab in _load(d)["drought"].items():
        years = {int(y) for r in tab["rows"].values() for y in r["cases"]}
        assert years and max(years) <= 2021 and min(years) >= 2007, h


@pytest.mark.parametrize("d", DOMAINS)
def test_the_weeks_like_this_one_reproduce_every_markov_row(d: str) -> None:
    for h, tab in _load(d)["drought"].items():
        g, ps = np.array(tab["global_row"]), tab["prior_strength"]
        for key, r in tab["rows"].items():
            if r["key"] == "persistence":
                continue
            counts = np.sum([np.array(v) for v in r["cases"].values()], axis=0)
            post = (counts + g * ps) / (counts.sum() + ps)
            assert np.allclose(post, r["row"], atol=1e-9), (d, h, key)


@pytest.mark.skipif(not EXPORT.exists(), reason="export not built")
@pytest.mark.parametrize("d", DOMAINS)
def test_the_tables_give_the_published_probabilities(d: str) -> None:
    ex = pd.read_parquet(EXPORT)
    issue = ex["time"].max()
    rows = ex[(ex["domain"] == d) & (ex["time"] == issue)]
    e = _load(d)
    for h in ("2", "4", "8"):
        tab = e["drought"][h]["rows"]
        for t in ("d_ge2", "d_ge3", "d_improve1", "d_intensify1", "d_intensify2", "d_nochange"):
            for c_raw, p, mo in zip(rows["usdm"], rows[f"{t}_h{h}_model_prob"], pd.to_datetime(rows["time"]).dt.month, strict=True):
                c = int(np.clip(np.floor(c_raw + 0.5), 0, 4))
                assert abs(float(np.array(tab[f"{c},{mo}"]["row"])[_event(t, c)].sum()) - p) < 1e-6
        for thr in ("80", "90", "97"):
            f = e["fire"][h][thr]
            x = rows["erc_pct"].to_numpy(float)
            x = np.where(np.isfinite(x), x, f["fill"])
            q = 1 / (1 + np.exp(-(f["intercept"] + f["slope"] * x)))
            state = rows[f"f_gt{thr}_h{h}_state"].iloc[0] if f"f_gt{thr}_h{h}_state" in rows else "probability"
            if state == "probability":
                assert np.allclose(q, rows[f"f_gt{thr}_h{h}_p"].to_numpy(float), atol=1e-5)
