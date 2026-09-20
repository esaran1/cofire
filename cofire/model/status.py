"""Honest Go / Partial / No-go from artifacts on disk. Never invents numbers."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from cofire.model.config import COVERAGE_TARGET, get_settings
from cofire.model.eval import _as_float
from cofire.model.train import git_sha


def _row(rows: list[object], arm: str) -> dict[str, object]:
    for item in rows:
        if isinstance(item, dict) and item.get("arm") == arm:
            return item
    return {}


def _overall_cov(payload: dict[str, object], split: str, method: str, horizon: int = 4) -> float:
    block = payload.get(split)
    if not isinstance(block, dict):
        return float("nan")
    blob = block.get(method)
    if not isinstance(blob, dict):
        return float("nan")
    for row in blob.get("rows", []):
        if row.get("stratum") == "overall" and int(row.get("horizon", -1)) == horizon:
            return _as_float(row.get("coverage"))
    return float("nan")


def write_status() -> Path:
    settings = get_settings()
    artifacts = settings.artifacts_dir
    sanity = json.loads((artifacts / "sanity.json").read_text()) if (artifacts / "sanity.json").exists() else {}
    metrics = json.loads((artifacts / "metrics.json").read_text()) if (artifacts / "metrics.json").exists() else {}
    comparison = (
        json.loads((artifacts / "uncertainty" / "comparison.json").read_text())
        if (artifacts / "uncertainty" / "comparison.json").exists()
        else {}
    )
    runtime = json.loads((artifacts / "runtime.json").read_text()) if (artifacts / "runtime.json").exists() else {}

    sanity_ok = bool(sanity.get("all_passed"))
    shipping = str(metrics.get("shipping_arm") or "unknown")
    val_rows = metrics.get("validation") if isinstance(metrics.get("validation"), list) else []
    hc_rows = metrics.get("hindcast") if isinstance(metrics.get("hindcast"), list) else []
    val = _row(val_rows, shipping)  # type: ignore[arg-type]
    hc = _row(hc_rows, shipping)  # type: ignore[arg-type]

    beats: dict[str, dict[str, bool]] = {"validation": {}, "hindcast": {}}
    details: list[str] = []
    for split_name, row in (("validation", val), ("hindcast", hc)):
        for target, label in (("usdm", "drought"), ("erc", "fire-condition ERC")):
            for h in (2, 4, 8):
                sk = _as_float(row.get(f"{target}_h{h}_skill_pers"))
                key = f"{label} h={h}"
                beats[split_name][key] = bool(np.isfinite(sk) and sk > 0)
                if row:
                    details.append(
                        f"{split_name} {shipping} {key} skill vs persistence = {sk:.3f}"
                        if np.isfinite(sk)
                        else f"{split_name} {shipping} {key} skill vs persistence could not be computed"
                    )

    hc_conf = _overall_cov(comparison, "hindcast", "conformal")
    hc_boot = _overall_cov(comparison, "hindcast", "bootstrap")
    cal_conf = _overall_cov(comparison, "calibrate", "conformal")
    cal_boot = _overall_cov(comparison, "calibrate", "bootstrap")
    conf_ok = bool(np.isfinite(hc_conf) and abs(hc_conf - COVERAGE_TARGET) <= 0.03)

    hc_beats_48 = [
        beats["hindcast"].get("drought h=4", False),
        beats["hindcast"].get("drought h=8", False),
        beats["hindcast"].get("fire-condition ERC h=4", False),
        beats["hindcast"].get("fire-condition ERC h=8", False),
    ]
    any_8 = beats["hindcast"].get("drought h=8", False) or beats["hindcast"].get("fire-condition ERC h=8", False)
    all_48 = all(hc_beats_48)

    if not sanity_ok:
        verdict = "No-go"
        reason = (
            "Sanity gates failed. Downstream metrics are not meaningful until the pipeline is fixed. "
            f"Failed: {[g.get('name') for g in sanity.get('gates', []) if isinstance(g, dict) and not g.get('passed')]}."
        )
        ship = "Do not ship. Cheapest diagnostic: read artifacts/sanity.md and fix the failing gate, not the model."
    elif not hc:
        verdict = "No-go"
        reason = "Hindcast 2026 has not been scored. Run `make hindcast` after freezing on validation."
        ship = "Do not ship."
    elif not any_8:
        verdict = "No-go"
        reason = (
            f"Shipping arm `{shipping}` does not beat persistence at 8 weeks on the 2026 hindcast "
            "for drought or fire-condition ERC. That is a model-quality failure, not a 2-week persistence floor."
        )
        ship = "Cheapest diagnostic: compare 8-week MAE to persistence in artifacts/metrics.md; check leakage only if sanity already passed."
    elif all_48 and conf_ok and sanity_ok:
        verdict = "Go"
        reason = (
            f"Shipping arm `{shipping}` beats persistence at 4 and 8 weeks for drought and ERC on hindcast, "
            f"conformal 4-week ERC coverage is {hc_conf:.3f} (within 3 points of {COVERAGE_TARGET:.2f}), "
            "and sanity gates passed."
        )
        ship = "Proceed to statewide (`COFIRE_DEV_SUBSET=0`)."
    else:
        verdict = "Partial"
        work = [k for k, v in beats["hindcast"].items() if v]
        fail = [k for k, v in beats["hindcast"].items() if not v]
        reason = (
            f"Some targets/horizons work on hindcast ({work}); others do not ({fail}). "
            f"Conformal hindcast coverage {hc_conf:.3f}; bootstrap {hc_boot:.3f}."
        )
        ship_bits = []
        if beats["hindcast"].get("fire-condition ERC h=4") or beats["hindcast"].get("fire-condition ERC h=8"):
            ship_bits.append("keep the fire-condition layer for horizons that beat persistence")
        else:
            ship_bits.append("cut the fire-condition layer from the UI")
        if beats["hindcast"].get("drought h=4") or beats["hindcast"].get("drought h=8"):
            ship_bits.append("keep drought for horizons that beat persistence")
        else:
            ship_bits.append("cut the drought layer from the UI")
        if not conf_ok:
            ship_bits.append("show interval width as experimental; do not claim 90% coverage")
        ship = "Recommend: " + "; ".join(ship_bits) + "."

    lines = [
        f"# STATUS: {verdict}",
        "",
        f"Git `{git_sha()}`. Domain: {'Larimer' if settings.dev_subset else 'Colorado statewide'}.",
        f"Shipping arm: `{shipping}`.",
        "",
        reason,
        "",
        ship,
        "",
        "## Evidence",
        "",
        f"Sanity: {'PASS' if sanity_ok else 'FAIL'}.",
        f"Calibrate coverage (ERC h=4): conformal {cal_conf:.3f}, bootstrap {cal_boot:.3f}.",
        f"Hindcast coverage (ERC h=4): conformal {hc_conf:.3f}, bootstrap {hc_boot:.3f} (target {COVERAGE_TARGET:.2f}).",
        "",
        *[f"- {d}" for d in details],
        "",
        "No post-hindcast hyperparameter change was made in this session unless DECISIONS.md says otherwise.",
        "",
    ]
    if runtime.get("stages"):
        lines.append("## Runtime")
        lines.append("")
        for rec in runtime["stages"]:
            if isinstance(rec, dict):
                lines.append(
                    f"- {rec.get('stage')}: {rec.get('wall_seconds')} s, peak RSS {rec.get('peak_rss_mb')} MB, exit {rec.get('exit_code')}"
                )
        lines.append("")
    root = Path("STATUS.md")
    root.write_text("\n".join(lines))
    return root


if __name__ == "__main__":
    write_status()
