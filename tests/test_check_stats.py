"""The hardcoded-statistics lint catches literal figures and spares styling."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("check_stats", Path("scripts/check_stats.py"))
assert _spec and _spec.loader
check_stats = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_stats)


def _scan(tmp_path: Path, body: str) -> list[str]:
    p = tmp_path / "X.tsx"
    p.write_text(body)
    return list(check_stats.scan(p))


def test_literal_results_are_caught(tmp_path: Path) -> None:
    hits = _scan(tmp_path, '<Verdict value="30/30" label="interval tests passed" />\n<p>11 of 51 pairs, 39% of cells, reliability 0.0394</p>')
    kinds = {h.split(": ")[1].split(" ")[0] for h in hits}
    assert {"fraction", "count", "percent", "decimal"} <= kinds


def test_styling_comments_and_criteria_are_not(tmp_path: Path) -> None:
    body = (
        '<div className="w-1/2 max-h-[70dvh] opacity-90" style={{ width: "50%" }}>\n'
        "{/* 30/30 in a comment */}\n"
        "<p>The dashed line is the 0.90 target.</p></div>"
    )
    assert _scan(tmp_path, body) == []


def test_the_app_passes() -> None:
    assert check_stats.main() == 0
