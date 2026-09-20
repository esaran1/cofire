from __future__ import annotations

import pandas as pd
from cofire.model.explain import assert_exhaustive, explain_row, feature_to_group, load_groups
from cofire.model.features import FEATURE_COLUMNS


def test_every_feature_maps_to_exactly_one_group() -> None:
    mapping = feature_to_group()
    groups = load_groups()
    seen: dict[str, str] = {}
    for group, feats in groups.items():
        for f in feats:
            assert f not in seen, f"{f} in {seen[f]} and {group}"
            seen[f] = group
    assert_exhaustive(list(FEATURE_COLUMNS))
    for f in FEATURE_COLUMNS:
        assert f in mapping


def test_explain_row_templates_top_feature() -> None:
    mapping = feature_to_group()
    row = pd.Series({feat: 0.0 for feat in mapping})
    row["spi_90"] = 1.5
    bars = explain_row(row, mapping)
    precip = next(b for b in bars if b["group"] == "precipitation_deficit")
    assert precip["top_feature"] == "spi_90"
    assert "spi_90" in precip["text"]
