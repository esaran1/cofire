#!/usr/bin/env python3
"""Fail the build if UI/docs claim we predict ignitions or fire locations."""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Claims that COFIRE forecasts ignitions. Always forbidden.
FORBIDDEN = (
    "predicts fires",
    "where fires will happen",
    "fire prediction",
)

# Claims of superior forecast skill, in the blanket form. These are always
# forbidden because they claim more than any result here supports: "outperforms"
# with no object, or "state of the art", is a marketing claim, not a finding.
#
# A SCOPED claim is different and is now permitted, because there is evidence
# for one. Stage 1 found 12 target-and-domain pairs whose forecasts beat their
# named baseline under multiplicity control and a shuffled-target check
# (artifacts/rerun_a/multiplicity.csv, mirrored into app/lib/facts.json). Copy
# may say a forecast beats its baseline where the survivor list supports it.
# `check_survivor_claims` enforces that the list is non-empty and that the copy
# reads it from facts.json rather than asserting a number of its own.
SUPERIORITY = (
    "more accurate than",
    "outperforms",
    "state of the art",
    "state-of-the-art",
    "beats persistence",
    "better than persistence",
)

# Em-dash is an LLM stylistic tell and is banned in app-facing copy. Only
# app/ is checked: docs and artifacts are prose written for readers, not UI.
EMDASH = ("\u2014", "\u2013")
EMDASH_ROOTS = (Path("app"),)

ROOTS = (Path("app"), Path("docs"), Path("README.md"), Path("PLAN.md"))
# Scanned for ignition claims but exempt from the superiority list: these record
# the experimental history, where "beats persistence" is the finding being
# reported (usually negated), not a marketing claim.
SUPERIORITY_EXEMPT = {
    Path("docs/PREREGISTRATION.md"),
    Path("docs/PREREGISTRATION_CALIBRATION.md"),
    Path("PLAN.md"),
}


def check_survivor_claims() -> list[str]:
    """A skill claim in app copy must be backed by the survivor list.

    The blanket ban was correct when the survivor count was zero. Now that it is
    not, the rule that replaces it is that the claim must be scoped and must
    come from the artifact: copy that mentions beating a baseline has to read
    `facts.survivors` rather than state a count of its own, so the page cannot
    drift from the result.
    """
    import json

    problems: list[str] = []
    facts_path = Path("app/lib/facts.json")
    if not facts_path.exists():
        return ["app/lib/facts.json is missing; skill claims cannot be checked"]
    facts = json.loads(facts_path.read_text())
    survivors = facts.get("survivors") or []

    claim = re.compile(r"beat(s|ing)? (its|their|the) baseline", re.IGNORECASE)
    for path in sorted(Path("app").rglob("*.tsx")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not claim.search(text):
            continue
        if not survivors:
            problems.append(
                f"{path}: claims a forecast beats its baseline, but the survivor "
                "list in facts.json is empty"
            )
        elif "facts.survivors" not in text and "survivors" not in text:
            problems.append(
                f"{path}: claims a forecast beats its baseline without reading "
                "the survivor list from facts.json"
            )
    return problems


def main() -> int:
    hits: list[str] = []
    files: list[Path] = []
    for root in ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(p for p in root.rglob("*") if p.suffix in {".md", ".tsx", ".ts", ".jsx", ".js", ".html"})
    for path in files:
        if "node_modules" in path.parts or ".next" in path.parts:
            continue
        text = path.read_text(errors="replace").lower()
        for phrase in FORBIDDEN:
            if phrase in text:
                hits.append(f"{path}: '{phrase}' (implies forecasting ignitions)")
        if path in SUPERIORITY_EXEMPT:
            continue
        for phrase in SUPERIORITY:
            if phrase in text:
                hits.append(f"{path}: '{phrase}' (implies superior forecast skill)")
        if any(str(path).startswith(str(r)) for r in EMDASH_ROOTS):
            for dash in EMDASH:
                if dash in text:
                    hits.append(f"{path}: em/en-dash '{dash}' in UI copy (use a plain hyphen)")
    hits.extend(check_survivor_claims())
    if hits:
        print("copy lint failed:")
        print("\n".join(hits))
        return 1
    print("copy lint ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
