"""v1.1 fitting: embargo, strict fit windows, and the recorded choices."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest
from cofire.model.fit_window import FitWindowError, checked_load
from cofire.ship import fit_v11


def test_embargo_drops_exactly_the_rows_whose_label_crosses_the_boundary() -> None:
    t = pd.date_range("2011-11-01", "2012-02-28", freq="W-TUE")
    kept = fit_v11.embargo(pd.DataFrame({"time": t}), pd.Timestamp("2012-01-01"), 4)
    kt = pd.to_datetime(kept["time"])
    before = kt[kt < pd.Timestamp("2012-01-01")]
    assert (before + pd.Timedelta(weeks=4) < pd.Timestamp("2012-01-01")).all()
    assert len(kt[kt >= pd.Timestamp("2012-01-01")]) == len(t[t >= pd.Timestamp("2012-01-01")])


def test_v11_artifacts_declare_a_training_window_and_load_strictly() -> None:
    for name in ("choices.json", "continuous_arms.json"):
        w = checked_load(fit_v11.OUT / name, strict=True)
        assert (w.fit_start.isoformat(), w.fit_end.isoformat()) == ("2007-01-01", "2021-12-31")


def test_strict_loader_refuses_a_window_past_the_training_split(tmp_path: Path) -> None:
    p = tmp_path / "choices.json"
    shutil.copy(fit_v11.OUT / "choices.json", p)
    side = json.loads((fit_v11.OUT / "choices.json.fitwindow.json").read_text())
    side["fit_end"] = "2023-12-31"
    (tmp_path / "choices.json.fitwindow.json").write_text(json.dumps(side))
    with pytest.raises(FitWindowError):
        checked_load(p, strict=True)


def test_folds_follow_the_rule_and_the_shared_years_are_recorded() -> None:
    fl = json.loads((fit_v11.OUT / "folds.json").read_text())
    for d in ("denver", "upper_south_platte", "dillon", "larimer", "pueblo"):
        med = fl[d]["median"]
        assert fl[d]["folds"] == [int(y) for y, v in fl[d]["annual_mean"].items() if v > med]
    assert fl["shared"] == [2012, 2013, 2020, 2021]


def test_new_domains_use_new_choices_and_old_domains_keep_frozen_ones() -> None:
    new = fit_v11.load_choices("denver")
    old = fit_v11.load_choices("larimer")
    assert len(new) == 27 and all(c.family == "damped" for (t, _), c in new.items() if t.startswith("f_gt"))
    assert fit_v11.continuous_arms("dillon") == {2: "damped_regression", 4: "damped_regression", 8: "damped_regression"}
    assert old and all(c.family in ("markov", "damped", "transition") for c in old.values())
