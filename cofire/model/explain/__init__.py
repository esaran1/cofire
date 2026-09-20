"""Grouped TreeSHAP for the Place Card Why bars.

Bars are summed group SHAP of the LightGBM ERC-percentile model at the
selected horizon, signed and normalized per cell. One-line copy is templated
from the top feature in that group and its sign.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from cofire.model.features import FEATURE_COLUMNS, available_features

GROUP_ORDER = (
    "precipitation_deficit",
    "snowpack",
    "soil_dryness",
    "vegetation_fuel_dryness",
    "heat",
)

TEMPLATES: dict[str, dict[str, str]] = {
    "precipitation_deficit": {
        "pos": "Precipitation has been running below this cell's own normal.",
        "neg": "Recent precipitation is above this cell's own normal.",
    },
    "snowpack": {
        "pos": "Basin snowpack is below median for this date, so soils will dry faster.",
        "neg": "Basin snowpack is above median for this date.",
    },
    "soil_dryness": {
        "pos": "1,000-hour fuels are drier than this cell's seasonal mean.",
        "neg": "1,000-hour fuels hold more moisture than this cell's seasonal mean.",
    },
    "vegetation_fuel_dryness": {
        "pos": "Energy release and live-fuel dryness are elevated versus this cell's climatology.",
        "neg": "Fuel moisture is higher than this cell's climatology, lowering spread conditions.",
    },
    "heat": {
        "pos": "Maximum temperatures are running hot relative to this week of year.",
        "neg": "Maximum temperatures are cooler than this week of year.",
    },
}

GROUP_LABELS = {
    "precipitation_deficit": "precipitation deficit",
    "snowpack": "snowpack",
    "soil_dryness": "soil dryness",
    "vegetation_fuel_dryness": "vegetation and fuel dryness",
    "heat": "heat",
}


def groups_path() -> Path:
    return Path(__file__).with_name("feature_groups.yaml")


def load_groups(path: Path | None = None) -> dict[str, list[str]]:
    raw = yaml.safe_load((path or groups_path()).read_text())
    return {str(k): [str(x) for x in v] for k, v in raw.items()}


def feature_to_group(path: Path | None = None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for group, feats in load_groups(path).items():
        for feat in feats:
            if feat in mapping:
                raise ValueError(f"{feat} mapped twice")
            mapping[feat] = group
    return mapping


def assert_exhaustive(columns: list[str] | None = None, path: Path | None = None) -> None:
    mapping = feature_to_group(path)
    cols = columns or list(FEATURE_COLUMNS)
    missing = [c for c in cols if c not in mapping]
    extra_groups = set(mapping)  # noqa: F841
    if missing:
        raise AssertionError(f"unmapped features: {missing}")


def grouped_shap(shap_row: pd.Series, mapping: dict[str, str]) -> dict[str, float]:
    sums = {g: 0.0 for g in GROUP_ORDER}
    for feat, val in shap_row.items():
        group = mapping.get(str(feat))
        if group is None or not np.isfinite(val):
            continue
        sums[group] += float(val)
    return sums


def normalize_signed(values: dict[str, float]) -> dict[str, float]:
    mag = sum(abs(v) for v in values.values()) or 1.0
    return {k: v / mag for k, v in values.items()}


def explain_row(shap_row: pd.Series, mapping: dict[str, str]) -> list[dict[str, Any]]:
    grouped = grouped_shap(shap_row, mapping)
    normed = normalize_signed(grouped)
    bars = []
    for group in GROUP_ORDER:
        # top feature in this group by |SHAP|
        members = [f for f, g in mapping.items() if g == group and f in shap_row.index]
        top = max(members, key=lambda f: abs(float(shap_row.get(f, 0.0)))) if members else ""
        polarity = "pos" if grouped[group] >= 0 else "neg"
        top_sign = float(shap_row.get(top, 0.0)) if top else 0.0
        feat_bit = (
            f" Leading feature: {top} ({'positive' if top_sign >= 0 else 'negative'} SHAP)."
            if top
            else ""
        )
        bars.append(
            {
                "group": group,
                "label": GROUP_LABELS[group],
                "value": normed[group],
                "raw": grouped[group],
                "top_feature": top,
                "text": TEMPLATES[group][polarity] + feat_bit,
                "sign": polarity,
            }
        )
    return bars


def shap_for_booster(booster: object, frame: pd.DataFrame) -> pd.DataFrame:
    """TreeExplainer on a LightGBM booster. Returns a DataFrame of SHAP values."""
    import shap

    cols = available_features(frame)
    x = frame.reindex(columns=cols).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    explainer = shap.TreeExplainer(booster)
    values = explainer.shap_values(x)
    if isinstance(values, list):
        values = values[0]
    return pd.DataFrame(values, columns=cols, index=frame.index)


def cache_why(
    booster: object,
    frame: pd.DataFrame,
    out_path: Path,
    sample: int = 400,
) -> pd.DataFrame:
    """Stratified sample of cells/weeks, cache per-row grouped SHAP."""
    mapping = feature_to_group()
    work = frame
    if len(work) > sample:
        work = work.sample(n=sample, random_state=2026)
    shap_df = shap_for_booster(booster, work)
    recs = []
    for idx, row in shap_df.iterrows():
        src = work.loc[idx]
        recs.append(
            {
                "cell_id": src["cell_id"],
                "time": str(pd.Timestamp(src["time"]).date()),
                "bars": explain_row(row, mapping),
            }
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = pd.DataFrame(recs)
    payload.to_json(out_path, orient="records")
    return payload
