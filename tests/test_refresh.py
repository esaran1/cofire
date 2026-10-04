"""The weekly refresh: release timing, archive weeks, and a pack that stays in data/."""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from cofire.ship import datapack
from cofire.ship.export import available_at, latest_published, usdm_weeks_available
from cofire.ship.safe_fetch import FetchRefused


@pytest.mark.parametrize(
    ("now", "issue"),
    [
        ("2026-09-24 13:29", "2026-09-15"),  # Thursday, a minute before the 08:30 ET release
        ("2026-09-24 13:30", "2026-09-22"),
        ("2026-09-27 12:00", "2026-09-22"),
        ("2026-09-29 20:00", "2026-09-22"),  # the next Tuesday's map is not out until Thursday
        ("2026-10-01 14:00", "2026-09-29"),
    ],
)
def test_latest_published_issue(now: str, issue: str) -> None:
    assert latest_published(pd.Timestamp(now)) == pd.Timestamp(issue)


def test_available_at_is_the_thursday_release() -> None:
    assert available_at(pd.Timestamp("2026-09-22")) == pd.Timestamp("2026-09-24 13:30")


def test_archive_weeks_are_read_from_member_names(tmp_path: Path) -> None:
    (tmp_path / "usdm").mkdir()
    with zipfile.ZipFile(tmp_path / "usdm" / "2026_USDM_M.zip", "w") as zf:
        zf.writestr("USDM_20260908_M.zip", b"x")
        zf.writestr("USDM_20260915_M.zip", b"x")
    weeks = usdm_weeks_available(tmp_path, range(2026, 2027))
    assert weeks == {pd.Timestamp("2026-09-08"), pd.Timestamp("2026-09-15")}
    assert pd.Timestamp("2026-09-22") not in weeks


def _tar(tmp_path: Path, name: str) -> Path:
    out = tmp_path / "pack.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        info = tarfile.TarInfo(name)
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    return out


@pytest.mark.parametrize("bad", ["../escape.nc", "/etc/passwd", "data/../../escape", "elsewhere/file.nc"])
def test_pack_restore_refuses_entries_outside_data(tmp_path: Path, bad: str) -> None:
    with pytest.raises(FetchRefused):
        datapack.restore(_tar(tmp_path, bad))


def test_the_clip_gate_passed_for_every_domain() -> None:
    import json

    gate = json.loads(datapack.GATE.read_text())
    assert set(gate) == {"denver", "upper_south_platte", "dillon", "larimer", "pueblo"}
    assert all(v["ok"] and v["n_different"] == 0 for v in gate.values())


def test_export_comparison_ignores_platform_noise_only(tmp_path: Path) -> None:
    from cofire.ship.refresh import same_export

    base = pd.DataFrame({"domain": ["denver", "dillon"], "p": [0.25, 0.5]})
    prev = tmp_path / "prev.parquet"
    base.to_parquet(prev)
    cur = tmp_path / "cur.parquet"
    base.assign(p=base["p"] + 1e-12).to_parquet(cur)
    assert same_export(prev.read_bytes(), cur)
    base.assign(p=base["p"] + 1e-6).to_parquet(cur)
    assert not same_export(prev.read_bytes(), cur)
    base.assign(domain=["denver", "pueblo"]).to_parquet(cur)
    assert not same_export(prev.read_bytes(), cur)


def test_export_refuses_a_missing_map_inside_the_history() -> None:
    from cofire.ship.export import MissingInputError, publishable_weeks

    weeks = list(pd.date_range("2026-01-06", "2026-09-15", freq="W-TUE"))
    mid = pd.Timestamp("2026-05-05")
    with pytest.raises(MissingInputError, match="2026-05-05"):
        publishable_weeks("denver", weeks, set(weeks) - {mid})


def test_export_holds_back_only_the_trailing_edge() -> None:
    from cofire.ship.export import publishable_weeks

    weeks = list(pd.date_range("2026-01-06", "2026-09-22", freq="W-TUE"))
    have = set(weeks) - {pd.Timestamp("2026-09-22")}
    assert publishable_weeks("denver", weeks, have) == sorted(have)


def test_the_export_guard_is_the_one_build_export_calls() -> None:
    import inspect

    from cofire.ship import export

    assert "publishable_weeks(" in inspect.getsource(export.build_export)


def test_the_ci_ceiling_is_three_times_the_measured_run() -> None:
    from cofire.ship import ci_budget

    assert ci_budget.CEILING_BYTES == 3 * ci_budget.PER_RUN_BYTES == 10_778_277


def test_the_ci_check_fails_a_run_over_its_ceiling(tmp_path: Path) -> None:
    import json

    from cofire.ship import ci_budget

    led = tmp_path / "ci.json"
    rows = [{"source": "USDM-weekly", "url": "https://x", "bytes": b, "timestamp": "t",
             "note": f"session={s}; sha256=0"} for s, b in (("refresh-1", 3_000_000), ("refresh-2", 12_000_000))]
    led.write_text(json.dumps({"transfers": rows}))
    assert ci_budget.check("refresh-1", led)["ok"]
    over = ci_budget.check("refresh-2", led)
    assert not over["ok"] and over["bytes"] == 12_000_000


def test_ci_transfers_go_to_their_own_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    from cofire.ship import ci_budget, refresh

    monkeypatch.setenv("COFIRE_LEDGER_PATH", str(ci_budget.CI_LEDGER))
    led = refresh._ledger()
    assert led.path == ci_budget.CI_LEDGER and led.budget_bytes == ci_budget.CI_BUDGET_BYTES
    monkeypatch.delenv("COFIRE_LEDGER_PATH")
    assert refresh._ledger().path == Path("data/ledger.json")


def test_size_peers_are_national_maps_even_when_the_archive_is_the_clip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """In CI the archive is the Colorado clip; its entries must not be the peers."""
    import json
    import zipfile

    from cofire.ship import refresh

    usdm = tmp_path / "usdm"
    usdm.mkdir()
    archive = usdm / "2026_USDM_M.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("USDM_20260922_M.zip", b"x" * 17_000)
    sizes = tmp_path / "sizes.json"
    sizes.write_text(json.dumps({"USDM_20260915_M.zip": 3_264_340, "USDM_20260922_M.zip": 3_000_870}))
    monkeypatch.setattr(refresh, "NATIONAL_SIZES", sizes)
    assert refresh.national_peers(archive) == [3_264_340, 3_000_870]
    refresh.record_national_size("USDM_20260929_M.zip", 3_012_266)
    assert refresh.national_peers(archive)[-1] == 3_012_266
    from cofire.ship.safe_fetch import check_peer_size

    check_peer_size(3_012_266, refresh.national_peers(archive))


def test_the_committed_national_sizes_are_national() -> None:
    import json

    from cofire.ship.refresh import NATIONAL_SIZES

    sizes = json.loads(NATIONAL_SIZES.read_text())
    assert len(sizes) >= 8 and min(sizes.values()) > 500_000
