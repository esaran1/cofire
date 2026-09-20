#!/usr/bin/env python3
"""Fail the build if UI/docs claim we predict ignitions or fire locations."""

from __future__ import annotations

import sys
from pathlib import Path

# Claims that COFIRE forecasts ignitions. Always forbidden.
FORBIDDEN = (
    "predicts fires",
    "where fires will happen",
    "fire prediction",
)

# Claims of superior forecast skill. COFIRE does not beat persistence at 4 or 8
# weeks (artifacts/lodo/lodo.md), so product-facing copy must not imply it.
# The persistence comparison itself stays in metrics.md, reported as the negative
# result it is -- which is why artifacts/ is not scanned.
SUPERIORITY = (
    "more accurate than",
    "outperforms",
    "beats",
    "state of the art",
    "state-of-the-art",
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
    if hits:
        print("copy lint failed:")
        print("\n".join(hits))
        return 1
    print("copy lint ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
