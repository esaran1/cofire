"""Export forecasts from the frozen configuration, scoring nothing.

What makes this not a look at the holdout: it reads issue-time features and
emits predictions and interval radii. It never reads a realized `*_h{2,4,8}`
outcome, never computes a metric, and never updates controller state from an
outcome. `assert_no_scoring` checks the first of those structurally, by
dropping the realized columns before anything downstream can see them.

The PID radius shown for a 2026 issue comes from the controller's state at the
end of the calibration split, frozen. Running the controller forward through
2026 would require observing 2026 outcomes, which is exactly what this path
must not do.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.ship.rendering import (  # noqa: E402
    BASE_RATE,
    all_decisions,
)

LOGGER = logging.getLogger("cofire.ship.export")

OUT = Path("artifacts/ship")
# Denver first: it is the district being judged. The three v1.1 domains are
# registered into the frozen config at runtime and served from v1.1 choices.
DOMAINS = ("denver", "upper_south_platte", "dillon", "larimer", "pueblo")
# The last issue before the refresh existed; the export now runs to the latest
# issue whose inputs are published (`latest_published`).
LAST_ISSUE = pd.Timestamp("2026-09-22")
HORIZONS = (2, 4, 8)

# Realized outcomes. Present in the built frame because the builder emits
# labels for every split; this module drops them before use.
def realized_columns(frame: pd.DataFrame) -> list[str]:
    import re

    pat = re.compile(r"^(erc_pct|usdm|d_|f_).*_h\d+$")
    return [c for c in frame.columns if pat.match(c)]


def assert_no_scoring(frame: pd.DataFrame) -> None:
    left = realized_columns(frame)
    if left:
        raise AssertionError(
            f"realized outcome columns survived into the export frame: {left[:6]}. "
            "The export path must not be able to read a holdout outcome."
        )


def _woy(times: pd.Series) -> np.ndarray:
    weeks: np.ndarray = (
        pd.to_datetime(times).dt.isocalendar().week.astype(int).clip(1, 52).to_numpy()
    )
    return weeks


def regional_base_rate(train: pd.DataFrame, target: str, index: pd.DataFrame) -> np.ndarray:
    """How often the event happened in this county at this time of year.

    The training-era (train split only) share of cell-weeks where `target`
    occurred, pooled over the whole domain and over weeks of year within the
    project's usual +/- 3 week window of each issue. One number per issue,
    identical across cells.

    This replaces the average of the model's own 2026 predictions over every
    issue, which is not a base rate and mixed seasons: it showed a 64% chance
    of Larimer reaching D2 within four weeks on 22 September, where the record
    for late September says 11%.
    """
    from cofire.model.erc_pct import window_weeks

    y = pd.to_numeric(train[target], errors="coerce")
    tw = _woy(train["time"])
    ok = np.isfinite(y.to_numpy(dtype=float))
    rate_by_woy: dict[int, float] = {}
    for w in range(1, 53):
        m = ok & np.isin(tw, window_weeks(w))
        rate_by_woy[w] = float(y.to_numpy(dtype=float)[m].mean()) if m.any() else float("nan")
    return np.array([rate_by_woy[int(w)] for w in _woy(index["time"])])


def climatological_bounds(
    train: pd.DataFrame, horizon: int, index: pd.DataFrame, lo: float = 5.0, hi: float = 95.0
) -> tuple[np.ndarray, np.ndarray]:
    """The actual 5th and 95th percentiles of the typical range, per cell and week.

    Same pooling as `climatological_width`: a cell's training values within
    +/- 3 weeks of year, at least 10 of them, else the domain-wide pool. The
    Place Card used to draw the range as median +/- half the width, which is
    only right for a symmetric distribution; these are the real bounds.
    """
    from cofire.model.erc_pct import window_weeks

    col = f"erc_pct_h{horizon}"
    v = pd.to_numeric(train[col], errors="coerce").to_numpy(dtype=float)
    cells = train["cell_id"].astype(str).to_numpy()
    tw = _woy(train["time"])
    ok = np.isfinite(v)
    pools: dict[tuple[str, int], np.ndarray] = {}
    frame = pd.DataFrame({"c": cells[ok], "w": tw[ok], "v": v[ok]})
    by = {(c, int(w)): g["v"].to_numpy() for (c, w), g in frame.groupby(["c", "w"])}
    g_lo, g_hi = np.percentile(v[ok], lo), np.percentile(v[ok], hi)
    out_lo = np.full(len(index), g_lo)
    out_hi = np.full(len(index), g_hi)
    icells = index["cell_id"].astype(str).to_numpy()
    iw = _woy(index["time"])
    for i, (c, w) in enumerate(zip(icells, iw, strict=True)):
        key = (c, int(w))
        if key not in pools:
            parts = [by[(c, x)] for x in window_weeks(int(w)) if (c, x) in by]
            pools[key] = np.concatenate(parts) if parts else np.array([])
        pool = pools[key]
        if pool.size >= 10:
            out_lo[i], out_hi[i] = np.percentile(pool, lo), np.percentile(pool, hi)
    return out_lo, out_hi


HISTORY_LAST_ALLOWED = pd.Timestamp("2023-12-31")


def historical_erc_range(
    train: pd.DataFrame,
    index: pd.DataFrame,
    horizon: int,
    train_end: pd.Timestamp,
    lo: float = 5.0,
    hi: float = 95.0,
) -> tuple[np.ndarray, np.ndarray]:
    """The usual range of raw ERC for the week a horizon forecasts, from history.

    For each row, the week being forecast is the issue week plus `horizon`.
    The range is the 5th to 95th percentile of this cell's raw weekly ERC over
    the training years, pooled over weeks of year within +/- 3 of that week,
    with at least 10 values, else the domain-wide pool for that window.

    Training years only, asserted: every value in any pool must fall on or
    before `train_end`, and `train_end` must fall before 2024, so nothing from
    the calibration split or the sealed year can enter. It is history, not a
    forecast, and the Place Card labels it that way.
    """
    from cofire.model.erc_pct import window_weeks

    times = pd.to_datetime(train["time"])
    if train_end > HISTORY_LAST_ALLOWED:
        raise AssertionError(f"history window ends {train_end.date()}, after 2023")
    if (times > train_end).any():
        raise AssertionError(
            f"historical ERC range was handed rows up to {times.max().date()}, "
            f"past the training end {train_end.date()}"
        )
    v = pd.to_numeric(train["erc"], errors="coerce").to_numpy(dtype=float)
    ok = np.isfinite(v)
    cells = train["cell_id"].astype(str).to_numpy()[ok]
    tw = _woy(train["time"])[ok]
    vals = v[ok]
    by_cell: dict[tuple[str, int], np.ndarray] = {
        (str(c), int(w)): g.to_numpy()
        for (c, w), g in pd.Series(vals).groupby([cells, tw])
    }
    by_week: dict[int, np.ndarray] = {int(w): g.to_numpy() for w, g in pd.Series(vals).groupby(tw)}
    target = pd.to_datetime(index["time"]) + pd.Timedelta(weeks=horizon)
    iw = _woy(pd.Series(target))
    icells = index["cell_id"].astype(str).to_numpy()
    out_lo = np.full(len(index), np.nan)
    out_hi = np.full(len(index), np.nan)
    cache: dict[tuple[str, int], tuple[float, float]] = {}
    for i, (c, w) in enumerate(zip(icells, iw, strict=True)):
        key = (c, int(w))
        if key not in cache:
            win = window_weeks(int(w))
            parts = [by_cell[(c, x)] for x in win if (c, x) in by_cell]
            pool = np.concatenate(parts) if parts else np.array([])
            if pool.size < 10:
                wide = [by_week[x] for x in win if x in by_week]
                pool = np.concatenate(wide) if wide else np.array([])
            cache[key] = (
                (float(np.percentile(pool, lo)), float(np.percentile(pool, hi)))
                if pool.size
                else (float("nan"), float("nan"))
            )
        out_lo[i], out_hi[i] = cache[key]
    return out_lo, out_hi


# ------------------------------------------------ inputs complete at issue time
#
# The export used to emit the issue of 2026-09-22 with USDM coded 0 in every
# cell: that week's map was not in the archive, and the frozen rasterizer fills
# a missing week with "none" without a word. Larimer and Pueblo's ERC for the
# same week was a three-day mean, because their daily record ended on the 18th
# and the frozen weekly builder lets the store's partial week win. An issue is
# now emitted only when its inputs were complete and published: the USDM map
# for that Tuesday is in the archive, and all seven ERC days of the week ending
# that Tuesday are in the daily record.

USDM_RELEASE_LAG = pd.Timedelta(days=2, hours=13, minutes=30)  # Thursday 08:30 ET, as UTC


def usdm_weeks_available(raw: Path, years: range) -> set[pd.Timestamp]:
    """Tuesdays whose USDM map is in the yearly archives."""
    import re
    import zipfile

    out: set[pd.Timestamp] = set()
    for y in years:
        z = raw / "usdm" / f"{y}_USDM_M.zip"
        if not z.exists():
            continue
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                m = re.search(r"(\d{8})", n)
                if m and n.lower().endswith((".zip", ".shp")):
                    out.add(pd.Timestamp(m.group(1)))
    return out


class MissingInputError(RuntimeError):
    """A week inside the published history has no USDM map."""


def publishable_weeks(domain: str, weeks: list[pd.Timestamp], usdm_ok: set[pd.Timestamp]) -> list[pd.Timestamp]:
    """Every published week must have its map; only the trailing edge may wait.

    A missing map at the end means it has not been fetched yet, and those weeks
    are held back. A missing map inside the history is a hole the frozen
    rasterizer would fill with "none", so the export refuses rather than
    publish around it.
    """
    weeks = sorted(pd.Timestamp(w) for w in weeks)
    have = [w for w in weeks if w in usdm_ok]
    if not have:
        return []
    interior = [w for w in weeks if w not in usdm_ok and w < have[-1]]
    if interior:
        raise MissingInputError(
            f"{domain}: USDM map missing for published week(s) {[str(w.date()) for w in interior]}"
        )
    held = [w for w in weeks if w > have[-1]]
    if held:
        LOGGER.warning("%s: holding back %d trailing issue(s) until their maps arrive: %s",
                       domain, len(held), [str(w.date()) for w in held])
    return have


def available_at(issue: pd.Timestamp) -> pd.Timestamp:
    """When every input of an issue had been published (the USDM map is last), UTC."""
    return pd.Timestamp(issue) + USDM_RELEASE_LAG


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None)


def latest_published(now: pd.Timestamp | None = None) -> pd.Timestamp:
    """The latest Tuesday whose USDM map had been released by `now` (UTC)."""
    now = utc_now() if now is None else now
    t = now.normalize() - pd.Timedelta(days=(now.weekday() - 1) % 7)
    while available_at(t) > now:
        t -= pd.Timedelta(weeks=1)
    return t


CURRENT_YEAR = 2026
STORE_DOMAINS = ("larimer", "pueblo")


def erc_complete_issue(domain: str, year: int = CURRENT_YEAR) -> pd.Timestamp:
    """The last Tuesday whose seven ERC days are all in the domain's latest vintage."""
    from cofire.ship import vintages

    last = pd.Timestamp(vintages.assemble(domain, year)["day"].values[-1])
    return last.normalize() - pd.Timedelta(days=(last.weekday() - 1) % 7)


class _vintage_view:
    """Run the frozen issue-frame builder on one domain's ERC as of one vintage.

    The frozen `look3.build_holdout` stops at its own LAST_ISSUE, reads the
    daily extension record from `data/cache/erc_ext` (relative to the working
    directory) and takes Larimer and Pueblo's current-year weeks from the
    processed cube. This builds a throwaway data directory whose current-year
    daily file for `domain` is the series as of `as_of` and which holds no
    current-year cube, so every current-year week comes from that vintage,
    complete weeks only (`n_per_week >= 7` in `features_a.weekly_erc`). Nothing
    under cofire/model is edited; the constant, the environment and the working
    directory are set for the call and restored.
    """

    def __init__(self, last: pd.Timestamp, domain: str, as_of: pd.Timestamp, year: int = CURRENT_YEAR) -> None:
        self.last, self.domain, self.as_of, self.year = last, domain, as_of, year

    def __enter__(self) -> _vintage_view:
        import tempfile

        from cofire.model import look3
        from cofire.model.config import get_settings
        from cofire.ship import vintages

        self._look3, self._prev = look3, look3.LAST_ISSUE
        look3.LAST_ISSUE = self.last.date()
        self._env = os.environ.get("COFIRE_DATA_DIR")
        self._cwd = Path.cwd()
        self._tmp = tempfile.TemporaryDirectory(prefix="cofire_view_")
        root = Path(self._tmp.name)
        data = (self._cwd / "data").resolve()
        (root / "data").mkdir()
        (root / "data" / "raw").symlink_to(data / "raw")
        for proc in data.glob("processed*"):
            gd = root / "data" / proc.name / "gridmet"
            gd.mkdir(parents=True)
            for cube in (proc / "gridmet").glob("weekly_*.nc"):
                if cube.name != f"weekly_{self.year}.nc":
                    (gd / cube.name).symlink_to(cube)
        cache = root / "data" / "cache" / "erc_ext"
        cache.mkdir(parents=True)
        mine = f"{self.domain}_{self.year}.nc"
        for f in (data / "cache" / "erc_ext").glob("*.nc"):
            if f.name != mine:
                (cache / f.name).symlink_to(f)
        if self.domain in STORE_DOMAINS:
            # Larimer and Pueblo's stores hold one weekly cube per year,
            # resampled from that year's days only, with the later year's cube
            # winning the week that straddles New Year (frozen convention,
            # `features_a.weekly_erc`). Their current-year cube is rebuilt from
            # the vintage the same way, so a published issue reproduces exactly
            # and a new one follows the convention its training data follows.
            proc = root / "data" / ("processed" if self.domain == "larimer" else f"processed_{self.domain}")
            daily = vintages.assemble(self.domain, self.year, self.as_of).rename({"day": "time"})
            daily.resample(time="W-TUE").mean().to_dataset(name="erc").to_netcdf(
                proc / "gridmet" / f"weekly_{self.year}.nc"
            )
        else:
            vintages.materialize(self.domain, self.year, cache / mine, self.as_of)
        os.chdir(root)
        os.environ["COFIRE_DATA_DIR"] = str(root / "data")
        get_settings.cache_clear()
        return self

    def __exit__(self, *exc: object) -> None:
        from cofire.model.config import get_settings

        os.chdir(self._cwd)
        self._look3.LAST_ISSUE = self._prev
        if self._env is None:
            os.environ.pop("COFIRE_DATA_DIR", None)
        else:
            os.environ["COFIRE_DATA_DIR"] = self._env
        get_settings.cache_clear()
        self._tmp.cleanup()


def build_export(last_issue: pd.Timestamp | None = None, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Every complete issue through `last_issue`, every domain, from the frozen model."""
    from cofire.ship import domains as _d

    now = utc_now() if now is None else now
    last_issue = latest_published(now) if last_issue is None else last_issue
    from cofire.ship.usdm_calendar import assert_complete

    assert_complete(range(2007, pd.Timestamp(last_issue).year), Path("data/raw"))
    # Stop at the last issue whose ERC week is complete in every domain.
    last_issue = min([pd.Timestamp(last_issue), *[erc_complete_issue(d) for d in _d.ORDER]])
    from cofire.model.calibration_stages import arms
    from cofire.model.look3 import build_holdout
    from cofire.model.shipping import (
        _drought_prediction,
        _fire_prediction,
        climatological_median,
        climatological_width,
        continuous_predict,
    )
    from cofire.model.shipping import load as load_choices
    from cofire.ship import domains, fit_v11

    domains.register()
    frozen_choices = load_choices(out_dir=Path("artifacts/rerun_a"))
    frozen_arms = arms()
    decisions = all_decisions()
    out_frames: list[pd.DataFrame] = []

    from cofire.ship import vintages

    pins = vintages.issue_vintages()
    for dom in DOMAINS:
        new = dom in domains.NEW
        choices = fit_v11.load_choices(dom) if new else frozen_choices
        arm_by_h = (
            {str(h): a for h, a in fit_v11.continuous_arms(dom).items()} if new else frozen_arms
        )
        latest = vintages.latest(dom, CURRENT_YEAR)
        frames: dict[pd.Timestamp, tuple[pd.DataFrame, Any]] = {}

        def frame_as_of(
            as_of: pd.Timestamp, dom: str = dom, new: bool = new,
            frames: dict[pd.Timestamp, tuple[pd.DataFrame, Any]] = frames,
        ) -> tuple[pd.DataFrame, Any]:
            if as_of not in frames:
                with _vintage_view(pd.Timestamp(last_issue), dom, as_of):
                    f, st = build_holdout(dom)
                f["time"] = pd.to_datetime(f["time"])
                if new:
                    cells = {f"{la:.4f}_{lo:.4f}" for la, lo in domains.load()[dom]["cells"]}
                    f = f[f["cell_id"].astype(str).isin(cells)].reset_index(drop=True)
                    assert f["cell_id"].nunique() == len(cells), f"{dom}: footprint cells missing"
                frames[as_of] = (f, st)
            return frames[as_of]

        frame, st = frame_as_of(latest)
        usdm_ok = usdm_weeks_available(Path("data/raw"), range(CURRENT_YEAR, pd.Timestamp(last_issue).year + 1))
        t = frame["time"]
        weeks = sorted(t[(t > pd.Timestamp(st.calibrate_end)) & (t <= pd.Timestamp(last_issue))].unique())
        pinned = pins.get(dom, {})
        for w in pinned:
            if pd.Timestamp(w) <= pd.Timestamp(last_issue) and pd.Timestamp(w) not in set(weeks):
                weeks.append(pd.Timestamp(w))
        keep = publishable_weeks(dom, sorted(pd.Timestamp(w) for w in weeks), usdm_ok)
        if not keep:
            raise SystemExit(f"{dom}: no complete issues after {st.calibrate_end}")
        # An issue is built from the vintage it was first produced from; only
        # issues never produced before use the latest.
        groups: dict[pd.Timestamp, list[pd.Timestamp]] = {}
        for w in keep:
            as_of = pd.Timestamp(pinned.get(str(pd.Timestamp(w).date()), latest))
            groups.setdefault(as_of, []).append(pd.Timestamp(w))

        for as_of, group in sorted(groups.items()):
            frame, st = frame_as_of(as_of)
            t = frame["time"]
            train = frame[t <= pd.Timestamp(st.train_end)]
            issues = frame[t.isin(group)].copy()
            missing_here = sorted(set(group) - set(issues["time"].unique()))
            assert not missing_here, f"{dom}: vintage {as_of} lacks pinned issue(s) {missing_here}"

            base = issues[["time", "cell_id", "lat", "lon", "erc", "erc_pct", "usdm", "woy"]].copy()
            base["domain"] = dom
            base["erc_vintage"] = pd.Timestamp(as_of).isoformat()
            base["available_at"] = base["time"].map(available_at)
            late = base.loc[base["available_at"] > now, "time"].unique()
            assert len(late) == 0, f"{dom}: issue(s) {late} not yet published at {now}"
            per_issue: dict[str, np.ndarray] = {}

            # Continuous ERC percentile, one column set per horizon.
            for h in HORIZONS:
                arm = arm_by_h[str(h)]
                pred = continuous_predict(arm, train, h, issues)
                per_issue[f"erc_pct_h{h}_point"] = pred
                # No interval radius is carried into the export. It used to be the
                # last state of a PID controller run with same-week updates, which
                # the delayed-feedback gate shows leaks, and nothing renders a band.
                per_issue[f"erc_pct_h{h}_clim_median"] = climatological_median(train, h, issues)
                per_issue[f"erc_pct_h{h}_clim_width"] = climatological_width(train, h, issues)
                e_lo, e_hi = historical_erc_range(train, issues, h, pd.Timestamp(st.train_end))
                per_issue[f"erc_h{h}_hist_lo"] = e_lo
                per_issue[f"erc_h{h}_hist_hi"] = e_hi
                b_lo, b_hi = climatological_bounds(train, h, issues)
                per_issue[f"erc_pct_h{h}_clim_lo"] = b_lo
                per_issue[f"erc_pct_h{h}_clim_hi"] = b_hi

            # Probabilistic targets.
            for (target, h), c in sorted(choices.items()):
                pred = (
                    _drought_prediction(h, train, target, issues)
                    if c.family == "markov"
                    else _fire_prediction(c.family, train, target, issues)
                )
                per_issue[f"{target}_p"] = pred
                per_issue[f"{target}_base_rate"] = regional_base_rate(train, target, issues)

            for col, vals in per_issue.items():
                base[col] = vals
            out_frames.append(base)

    export = pd.concat(out_frames, ignore_index=True).sort_values(["domain", "time", "cell_id"])
    export = export.reset_index(drop=True)
    assert_no_scoring(export)
    export = attach_rendering(export, decisions)
    return export


def attach_rendering(frame: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    """Store the rendering state and reason per target, horizon and domain.

    Applied here rather than in the app so that the rule lives in one place and
    the export is self-describing: a reader of the parquet can see what each
    number is allowed to be shown as, and why.
    """
    out = frame.copy()
    for _, d in decisions.iterrows():
        dom, target, h, state, reason = (
            str(d["domain"]), str(d["target"]), int(d["horizon"]),
            str(d["state"]), str(d["reason"]),
        )
        m = out["domain"] == dom
        if target == "erc_pct":
            key = f"erc_pct_h{h}"
        else:
            key = target
            if f"{key}_p" not in out.columns:
                continue
        out.loc[m, f"{key}_state"] = state
        out.loc[m, f"{key}_reason"] = reason

    # A base-rate target shows the regional base rate: how often the event
    # happened in this county at this time of year in the training record.
    # Identical across cells by construction, and seasonal, so it moves with
    # the issue date instead of being one number for the whole year.
    for col in [c for c in out.columns if c.endswith("_state")]:
        key = col[: -len("_state")]
        pcol, bcol = f"{key}_p", f"{key}_base_rate"
        if pcol not in out.columns or bcol not in out.columns:
            continue
        m = out[col] == BASE_RATE
        out[pcol] = out[pcol].astype("float64")
        out.loc[m, pcol] = out.loc[m, bcol].astype("float64")
    return out


def write(out_dir: Path = OUT, last_issue: pd.Timestamp | None = None, now: pd.Timestamp | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    from cofire.ship import vintages

    frame = build_export(last_issue, now)
    path = out_dir / "forecast_issues.parquet"
    frame.to_parquet(path, index=False)
    # Pin every issue to the vintage it was produced from. Existing pins never move.
    pins = frame.groupby(["domain", "time"])["erc_vintage"].first()
    vintages.pin_issues({
        d: {str(pd.Timestamp(t).date()): v for (dd, t), v in pins.items() if dd == d}
        for d in frame["domain"].unique()
    })
    states = {
        c[: -len("_state")]: frame[c].dropna().unique().tolist()
        for c in frame.columns if c.endswith("_state")
    }
    LOGGER.info(
        "%d rows, %d issues %s..%s, %d cells, %d targets with a rendering state",
        len(frame), frame["time"].nunique(),
        frame["time"].min().date(), frame["time"].max().date(),
        frame["cell_id"].nunique(), len(states),
    )
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(write())
