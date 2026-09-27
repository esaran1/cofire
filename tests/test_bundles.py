"""Per-domain bundles carry the export faithfully, and Denver carries its water."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from cofire.ship import bundles

ROOT = bundles.OUT
pytestmark = pytest.mark.skipif(not (ROOT / "index.json").exists(), reason="bundles not built")


def _latest(dom: str) -> dict:
    idx = json.loads((ROOT / "index.json").read_text())
    return json.loads((ROOT / dom / f"{idx['issues'][-1]}.json").read_text())


def test_denver_is_the_default_and_first() -> None:
    idx = json.loads((ROOT / "index.json").read_text())
    assert idx["default"] == "denver" and idx["order"][0] == "denver"
    assert idx["domains"]["denver"]["ember_zone"] == "city"
    assert idx["domains"]["upper_south_platte"]["evaluation"] == "validation"
    assert idx["domains"]["larimer"]["evaluation"] == "look3"


def test_denver_carries_both_source_watersheds() -> None:
    b = _latest("denver")
    assert set(b["sources"]) == {"upper_south_platte", "dillon"}
    for s in b["sources"].values():
        assert s["summary"]["4"]["f_gt90_h4"]["mean"] is not None


def test_decisions_match_the_rendering_table() -> None:
    r = pd.read_csv("artifacts/ship/rendering.csv")
    for dom in ("denver", "dillon", "pueblo"):
        b = _latest(dom)
        for t, (state, _reason) in b["decisions"]["targets"].items():
            want = r[(r["domain"] == dom) & (r["target"] == t)]["state"]
            assert len(want) == 1 and want.iloc[0] == state, (dom, t)


def test_legacy_view_matches_the_export() -> None:
    e = pd.read_parquet(bundles.EXPORT)
    last = e[e["time"] == e["time"].max()]
    view = bundles.legacy_cells(ROOT)
    cells = [c for c in view["cells"] if c["issue"] == str(last["time"].iloc[0].date())]
    assert len(cells) == len(last)
    row = last[(last["domain"] == "denver")].iloc[0]
    c = next(c for c in cells if c["domain"] == "denver" and c["cell_id"] == row["cell_id"])
    assert c["targets"]["d_ge2_h4"]["p"] == pytest.approx(row["d_ge2_h4_p"], abs=1e-4)
    assert c["horizons"]["8"]["point"] == pytest.approx(row["erc_pct_h8_point"], abs=0.05)


def test_no_bundle_reads_a_realized_outcome() -> None:
    e = pd.read_parquet(bundles.EXPORT)
    assert not [c for c in e.columns if c.endswith(("_h2", "_h4", "_h8")) and not c.endswith("_p")]


def test_new_domain_bundles_hold_footprint_cells_only() -> None:
    from cofire.ship import domains

    for dom in domains.NEW:
        b = _latest(dom)
        assert len(b["cells"]) == len(domains.load()[dom]["cells"])
        assert Path(ROOT / dom).is_dir()
