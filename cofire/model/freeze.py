"""The configuration hash, the freeze, and the conditions for look 3.

Three things live here because they are one mechanism:

1. **`config_hash`** over every file under `cofire/model/` plus every fitted
   artifact the shipped path loads. The hash in `hindcast.py` covers a handful
   of hyperparameters and would not change if the model code changed, so it
   cannot certify a freeze.
2. **`look_count`** keyed on the holdout year rather than the configuration.
   The existing counter in `hindcast.py` counts looks per config hash, which
   means changing the configuration resets the counter to zero and silently
   unseals the holdout. The seal belongs to the year: 2026 has been looked at
   twice, whatever code did the looking.
3. **`freeze_conditions`**, which reports each precondition for look 3 with its
   observed value, so the decision to look is made on verified facts.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

LOGGER = logging.getLogger("cofire.freeze")

HOLDOUT_YEAR = 2026
SEALED_LOOKS = 2
MODEL_DIR = Path("cofire/model")
LOOK_LOG = Path("artifacts/look_log.json")

# Every fitted artifact the shipped path loads. Listed rather than globbed, so
# that adding a fitted artifact without adding it here is a visible omission
# instead of a silent change in what the hash covers.
SHIPPED_ARTIFACTS = (
    Path("artifacts/rerun_a/choices.json"),
    Path("artifacts/rerun_a/continuous_arms.json"),
)


def _iter_model_files() -> list[Path]:
    """Every source file under `cofire/model/`, sorted, caches excluded."""
    return sorted(
        p
        for p in MODEL_DIR.rglob("*.py")
        if "__pycache__" not in p.parts
    )


def config_hash(extra: dict[str, object] | None = None) -> str:
    """sha256 over the model source and the fitted artifacts it loads.

    Path and contents both, so that renaming a file changes the hash. A hash
    over contents alone would be unchanged by a rename that alters which module
    the shipped path imports.
    """
    digest = hashlib.sha256()
    for path in _iter_model_files():
        digest.update(str(path.as_posix()).encode())
        digest.update(path.read_bytes())
    for path in SHIPPED_ARTIFACTS:
        digest.update(str(path.as_posix()).encode())
        digest.update(path.read_bytes() if path.exists() else b"<absent>")
        side = path.with_suffix(path.suffix + ".fitwindow.json")
        digest.update(side.read_bytes() if side.exists() else b"<no-window>")
    if extra:
        digest.update(json.dumps(extra, sort_keys=True, default=str).encode())
    return digest.hexdigest()


def look_count(year: int = HOLDOUT_YEAR, path: Path = LOOK_LOG) -> int:
    """How many looks the holdout YEAR has had, across every configuration.

    Keyed on the year, deliberately. A counter keyed on the configuration hash
    resets whenever the configuration changes, which would let any code change
    hand back a fresh set of looks at data that has already been seen.
    """
    legacy = _legacy_look_count(year)
    if not path.exists():
        return legacy
    try:
        records = json.loads(path.read_text())
    except json.JSONDecodeError:
        return legacy
    if not isinstance(records, list):
        return legacy
    own = sum(1 for r in records if isinstance(r, dict) and r.get("holdout_year") == year)
    return max(legacy, own) if own == 0 else legacy + own


def _legacy_look_count(year: int) -> int:
    """Looks recorded by the pre-freeze counter in `hindcast.py`.

    Those two looks at 2026 happened and are carried forward. They were logged
    per config hash; every record in that log is a look at the sealed year.
    """
    path = Path("artifacts/hindcast/run_log.json")
    if not path.exists() or year != HOLDOUT_YEAR:
        return 0
    try:
        records = json.loads(path.read_text())
    except json.JSONDecodeError:
        return 0
    return sum(1 for r in records if isinstance(r, dict))


def record_look(year: int, cfg: str, note: str, path: Path = LOOK_LOG) -> int:
    """Append a look and return the new count. Append only."""
    from datetime import UTC, datetime

    records: list[dict[str, object]] = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text())
            if isinstance(loaded, list):
                records = loaded
        except json.JSONDecodeError:
            records = []
    records.append(
        {
            "holdout_year": year,
            "config_hash": cfg,
            "git_sha": git_sha(),
            "timestamp": datetime.now(UTC).isoformat(),
            "note": note,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2))
    return look_count(year, path)


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def working_tree_clean() -> bool:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        ).stdout.strip()
        return out == ""
    except Exception:  # noqa: BLE001
        return False


def model_files_match(ref: str) -> tuple[bool, list[str]]:
    """Whether every file under `cofire/model/` matches commit `ref`.

    The post-look invariant: nothing about the model changes after the freeze.
    """
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", ref, "--", str(MODEL_DIR)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return False, [f"git diff failed: {exc}"]
    changed = [line for line in out.splitlines() if line.strip()]
    return (not changed), changed


@dataclass
class Condition:
    name: str
    ok: bool
    observed: str
    expected: str


@dataclass
class FreezeReport:
    conditions: list[Condition] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.conditions)

    def render(self) -> str:
        return "\n".join(
            f"{'PASS' if c.ok else 'FAIL'}  {c.name}: {c.observed} (expected {c.expected})"
            for c in self.conditions
        )


def freeze_conditions(freeze_commit: str, prereg_hash: str) -> FreezeReport:
    """Each precondition for look 3, checked in code and reported with its value."""
    rep = FreezeReport()

    rep.conditions.append(
        Condition("working tree clean", working_tree_clean(),
                  "clean" if working_tree_clean() else "dirty", "clean")
    )
    # HEAD need not equal FREEZE_COMMIT: recording the freeze commit's own hash
    # necessarily creates a commit after it, and so does anything else outside
    # the model. What the condition is for is that the model tree being run is
    # the frozen one, which is what `model_files_match` tests directly. A later
    # commit that leaves cofire/model/ untouched does not unfreeze anything.
    head = git_sha()
    same_tree, changed = model_files_match(freeze_commit)
    rep.conditions.append(
        Condition(
            "cofire/model/ matches FREEZE_COMMIT", same_tree,
            f"HEAD {head[:12]}, "
            + ("no model file differs" if same_tree else f"differs: {changed}"),
            f"no diff against {freeze_commit[:12]}",
        )
    )
    cfg = config_hash()
    rep.conditions.append(
        Condition("config hash matches preregistration", cfg == prereg_hash,
                  cfg[:16], prereg_hash[:16])
    )
    violations = fit_window_violations()
    rep.conditions.append(
        Condition("fit-window loader strict, no violations", not violations,
                  "none" if not violations else "; ".join(violations), "none")
    )
    n = look_count()
    rep.conditions.append(
        Condition("look counter reads 2", n == SEALED_LOOKS, str(n), str(SEALED_LOOKS))
    )
    return rep


def fit_window_violations() -> list[str]:
    """Run the fit-window loader in strict mode over every declared artifact."""
    from cofire.model.fit_window import FitWindowError, checked_load

    out: list[str] = []
    for path in SHIPPED_ARTIFACTS:
        if not path.exists():
            out.append(f"{path.name}: absent")
            continue
        try:
            checked_load(path, strict=True)
        except FitWindowError as exc:
            out.append(str(exc))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("config_hash:", config_hash())
    print("look_count:", look_count())
    print("git_sha:", git_sha())
