#!/usr/bin/env python3
"""Fail the build if UI/docs claim we predict ignitions or fire locations."""

from __future__ import annotations

import sys
from pathlib import Path

FORBIDDEN = (
    "predicts fires",
    "where fires will happen",
    "fire prediction",
)

ROOTS = (Path("app"), Path("docs"), Path("README.md"), Path("PLAN.md"))


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
                hits.append(f"{path}: '{phrase}'")
    if hits:
        print("copy lint failed — COFIRE must not claim to predict ignitions:")
        print("\n".join(hits))
        return 1
    print("copy lint ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
