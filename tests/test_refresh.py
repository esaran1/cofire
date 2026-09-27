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
