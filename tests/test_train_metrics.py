from __future__ import annotations

from cofire.model.train import pick_shipping


def test_pick_shipping_uses_validation_erc_mae() -> None:
    rows: list[dict[str, object]] = [
        {"arm": "lightgbm", "erc_h4_mae": 12.0, "usdm_h4_mae": 0.40},
        {"arm": "pi_convlstm_none", "erc_h4_mae": 8.0, "usdm_h4_mae": 0.30},
        {"arm": "pi_convlstm_both", "erc_h4_mae": 10.0, "usdm_h4_mae": 0.50},
        {"arm": "ensemble", "erc_h4_mae": 11.0, "usdm_h4_mae": 0.35},
        {"arm": "persistence", "erc_h4_mae": 7.0},
    ]
    # Ablation/baseline arms are not eligible; none is reported but does not ship.
    assert pick_shipping(rows) == "pi_convlstm_both"


def test_pick_shipping_tie_breaks_on_drought_mae() -> None:
    rows: list[dict[str, object]] = [
        {"arm": "lightgbm", "erc_h4_mae": 10.0, "usdm_h4_mae": 0.40},
        {"arm": "ensemble", "erc_h4_mae": 10.0, "usdm_h4_mae": 0.20},
        {"arm": "pi_convlstm_both", "erc_h4_mae": 10.0, "usdm_h4_mae": 0.50},
    ]
    assert pick_shipping(rows) == "ensemble"
