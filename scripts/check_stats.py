#!/usr/bin/env python3
"""Fail the build if app copy states a statistic as a literal.

Every figure the site shows is written to `app/lib/facts.json` or
`app/lib/story.json` from artifacts (cofire/ship/facts.py, story.py). A number
typed into a component cannot follow the artifact when a result changes, which
is how "30/30 interval tests passed" outlived the retraction that voided it.

Scanned: JSX text and string literals in `app/**/*.tsx`. Skipped: comments and
styling or geometry attributes. Flagged: fractions (30/30), counts (11 of 51),
percentages (90%) and decimals with two or more places (0.0394).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path("app")
SKIP_ATTRS = {
    "className", "style", "d", "viewBox", "points", "fill", "stroke", "href", "src",
    "width", "height", "x", "y", "cx", "cy", "r", "transform", "key", "id", "data-testid",
    "strokeWidth", "strokeDasharray", "sizes", "type", "role", "srcSet",
}
PATTERNS = {
    "fraction": re.compile(r"(?<![\w/.:-])\d+\s*/\s*\d+(?![\w/.:-])"),
    "count": re.compile(r"\b\d+ of (?:the )?\d+\b"),
    "percent": re.compile(r"(?<![\w.\-\[])\d+(?:\.\d+)?\s?%"),
    "decimal": re.compile(r"(?<![\w.])\d+\.\d{2,}(?![\w.])"),
}
# Preregistered criteria (docs/PREREGISTRATION_LOOK3.md), not results: they
# were fixed before the look and do not move when a result does. Each entry is
# the exact phrase allowed, so a result that happens to equal a criterion is
# still caught anywhere else.
ALLOWED = {
    "floor of 0.70",
    "0.70 floor",
    "0.90 target",
    "target 0.90",
    "0.05 threshold",
    "reliability 0.05 or less",
    "within 0.05 of 0.90",
    "at or above 0.70",
}
# Class lists and CSS values inside expressions, which the attribute filter
# cannot see: tailwind arbitrary values and easing curves.
CSS = re.compile(r"cubic-bezier|\w\[[^\]]+\]|rgba\(")

COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*|\{/\*.*?\*/\}", re.S)
ATTR = re.compile(r"([\w-]+)=(\"[^\"]*\"|'[^']*'|\{`[^`]*`\})")
JSX_TEXT = re.compile(r">([^<>{}]+)<")
STRING = re.compile(r"\"([^\"\n]*)\"|'([^'\n]*)'|`([^`]*)`")


def scan(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    text = COMMENT.sub(" ", raw)
    # Drop styling and geometry attributes, and imports, before looking at text.
    text = ATTR.sub(lambda m: " " if m.group(1) in SKIP_ATTRS else m.group(0), text)
    text = re.sub(r"^\s*import .*$", " ", text, flags=re.M)
    chunks = [m.group(1) for m in JSX_TEXT.finditer(text)]
    chunks += [next(g for g in m.groups() if g is not None) for m in STRING.finditer(text)]
    hits: list[str] = []
    for chunk in chunks:
        if CSS.search(chunk):
            continue
        wordy = bool(re.search(r"[A-Za-z]", chunk))
        for name, pat in PATTERNS.items():
            # A bare "6%" is almost always an offset or a formatter output; a
            # percentage in words is a claim. Fractions like "30/30" are
            # claims even standing alone.
            if name == "percent" and not wordy:
                continue
            for m in pat.finditer(chunk):
                window = chunk[max(0, m.start() - 20): m.end() + 20]
                if any(a in window for a in ALLOWED):
                    continue
                hits.append(f"{path}: {name} '{m.group(0)}' in \"{chunk.strip()[:80]}\"")
    return hits


def main() -> int:
    hits: list[str] = []
    for path in sorted(ROOT.rglob("*.tsx")):
        if "node_modules" in path.parts or ".next" in path.parts:
            continue
        hits.extend(scan(path))
    if hits:
        print("hardcoded-statistics lint failed; read the figure from facts.json:")
        print("\n".join(sorted(set(hits))))
        return 1
    print("hardcoded-statistics lint ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
