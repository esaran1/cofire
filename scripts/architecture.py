"""The architecture diagram, from one definition, as Mermaid and as SVG.

    python scripts/architecture.py          # write docs/architecture.svg and the README's Mermaid block
    python scripts/architecture.py --check  # fail if either is out of date

The README carries the diagram as Mermaid (between the architecture markers),
which GitHub draws; docs/architecture.svg is the same diagram drawn here
without any outside tool, for places that do not render Mermaid.
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

README = Path("README.md")
SVG = Path("docs/architecture.svg")
BEGIN, END = "<!-- architecture:begin -->", "<!-- architecture:end -->"

# Columns, left to right: (title, [(node id, label lines)]).
COLUMNS: list[tuple[str, list[tuple[str, list[str]]]]] = [
    ("Public data", [
        ("gridmet", ["gridMET", "fuel dryness (ERC)"]),
        ("usdm", ["U.S. Drought Monitor", "weekly categories"]),
        ("bounds", ["USGS WBD, Census", "area footprints"]),
        ("osm", ["OpenStreetMap", "via Protomaps"]),
    ]),
    ("Fetch, logged", [
        ("fetch", ["safe_fetch", "allowlist and ledger"]),
        ("vintages", ["vintages", "every fetch kept,", "each issue pinned"]),
    ]),
    ("Frozen model", [
        ("model", ["cofire/model @ 46c17ae", "configuration A:", "Markov drought, damped", "logistic fire, damped", "regression dryness"]),
        ("seal", ["2026 sealed", "looks counted;", "unseal 2027-01-12"]),
    ]),
    ("Ship layer", [
        ("export", ["export", "weekly forecasts,", "live v1.2 arm"]),
        ("render", ["rendering decisions", "survivors, reliability"]),
        ("bundles", ["bundles", "per area and issue"]),
        ("explain", ["explain tables", "weeks like this one"]),
        ("open", ["open data", "CSV, GeoJSON, JSON"]),
        ("record", ["forecast record", "timestamp and sha256"]),
        ("tiles", ["basemap extract", "Colorado, self-hosted"]),
    ]),
    ("Delivered", [
        ("refresh", ["weekly refresh", "GitHub Actions"]),
        ("site", ["static site", "Vercel"]),
        ("api", ["API", "local demo"]),
    ]),
    ("Readers", [
        ("map", ["map and Place Card"]),
        ("brief", ["weekly brief"]),
        ("scoreboard", ["forecast record page"]),
        ("data", ["open data page"]),
    ]),
]
EDGES: list[tuple[str, str]] = [
    ("gridmet", "fetch"), ("usdm", "fetch"), ("bounds", "fetch"), ("osm", "tiles"),
    ("fetch", "vintages"), ("vintages", "model"), ("model", "export"), ("seal", "export"),
    ("export", "render"), ("render", "bundles"), ("bundles", "explain"), ("bundles", "open"), ("export", "record"),
    ("refresh", "export"), ("bundles", "site"), ("explain", "site"), ("open", "site"), ("record", "site"), ("tiles", "site"),
    ("bundles", "api"), ("open", "api"),
    ("site", "map"), ("site", "brief"), ("site", "scoreboard"), ("site", "data"), ("api", "map"),
]
GATES = ["frozen-model test: configuration hash", "delayed-feedback leak gate", "look counter and seal",
         "number and copy lints", "research/ never imported by the shipped path"]
RESEARCH = ["research/: v1.2 arms and audits that did not ship (research/README.md)"]


def mermaid() -> str:
    """The diagram as a Mermaid flowchart."""
    out = ["```mermaid", "flowchart LR"]
    for i, (title, nodes) in enumerate(COLUMNS):
        out.append(f'  subgraph c{i}["{title}"]')
        for nid, lines in nodes:
            out.append(f'    {nid}["{"<br/>".join(lines)}"]')
        out.append("  end")
    out += [f"  {a} --> {b}" for a, b in EDGES]
    out.append(f'  gates["Gates: {"; ".join(GATES)}"]')
    out.append(f'  research["{RESEARCH[0]}"]')
    out.append("  gates -.- model")
    out.append("  research -.-x export")
    out.append("```")
    return "\n".join(out)


def svg() -> str:
    """The same diagram as an SVG, laid out in columns."""
    line_h, pad, gap = 17, 10, 70
    # Box width from the longest label line (about 7.4 px a character at 13 px).
    box_w = max(int(max(len(t) for _c, ns in COLUMNS for _n, ls in ns for t in ls) * 7.4) + 2 * pad, 190)
    col_w = box_w
    top = 70
    pos: dict[str, tuple[float, float, float, float]] = {}
    parts: list[str] = []
    heights = []
    for i, (_title, nodes) in enumerate(COLUMNS):
        y = top
        for nid, lines in nodes:
            h = pad * 2 + line_h * len(lines)
            x = 30 + i * (col_w + gap)
            pos[nid] = (x, y, box_w, h)
            y += h + 22
        heights.append(y)
    width = 30 + len(COLUMNS) * (col_w + gap) - gap + 30
    body_h = max(heights)
    height = body_h + 150
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="Helvetica, Arial, sans-serif">')
    parts.append(f'<rect width="{width}" height="{height}" fill="#f4f2ec"/>')
    parts.append('<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#66686e"/></marker></defs>')
    for i, (title, _nodes) in enumerate(COLUMNS):
        x = 30 + i * (col_w + gap)
        parts.append(f'<text x="{x}" y="44" font-size="15" font-weight="bold" fill="#17181b">{escape(title)}</text>')
    for a, b in EDGES:
        ax, ay, aw, ah = pos[a]
        bx, by, _bw, bh = pos[b]
        x1, y1, x2, y2 = ax + aw, ay + ah / 2, bx, by + bh / 2
        if bx <= ax:  # same column or backwards: route around
            x1, x2 = ax + aw, bx + aw
            parts.append(f'<path d="M{x1} {y1} C{x1 + 40} {y1}, {x2 + 40} {y2}, {x2} {y2}" fill="none" stroke="#66686e" stroke-width="1.2" marker-end="url(#a)"/>')
        else:
            mx = (x1 + x2) / 2
            parts.append(f'<path d="M{x1} {y1} C{mx} {y1}, {mx} {y2}, {x2} {y2}" fill="none" stroke="#66686e" stroke-width="1.2" marker-end="url(#a)"/>')
    for _title, nodes in COLUMNS:
        for nid, lines in nodes:
            x, y, w, h = pos[nid]
            frozen = nid in ("model", "seal")
            fill, stroke = ("#ece5d2", "#9a7420") if frozen else ("#faf9f5", "#3d3f45")
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
            for k, line in enumerate(lines):
                weight = "bold" if k == 0 else "normal"
                parts.append(f'<text x="{x + pad}" y="{y + pad + 13 + k * line_h}" font-size="13" font-weight="{weight}" fill="#17181b">{escape(line)}</text>')
    gy = body_h + 20
    parts.append(f'<rect x="30" y="{gy}" width="{width - 60}" height="46" rx="3" fill="#e8ddd6" stroke="#b33a1a" stroke-width="1.2"/>')
    parts.append(f'<text x="44" y="{gy + 28}" font-size="13" fill="#17181b"><tspan font-weight="bold">Gates</tspan>: {escape("; ".join(GATES))}</text>')
    ry = gy + 62
    parts.append(f'<rect x="30" y="{ry}" width="{width - 60}" height="40" rx="3" fill="none" stroke="#66686e" stroke-dasharray="6 4" stroke-width="1.2"/>')
    parts.append(f'<text x="44" y="{ry + 25}" font-size="13" fill="#3d3f45">{escape(RESEARCH[0])}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main(check: bool) -> None:
    block = f"{BEGIN}\n\n{mermaid()}\n\nThe same diagram as an image: [docs/architecture.svg](docs/architecture.svg) (generated by `scripts/architecture.py`).\n\n{END}"
    readme = README.read_text()
    a, b = readme.index(BEGIN), readme.index(END) + len(END)
    new_readme = readme[:a] + block + readme[b:]
    new_svg = svg()
    if check:
        stale = [p for p, new in ((README, new_readme), (SVG, new_svg)) if p.read_text() != new]
        if stale:
            raise SystemExit(f"out of date: {', '.join(map(str, stale))}; run python scripts/architecture.py")
        print("architecture diagram current")
        return
    README.write_text(new_readme)
    SVG.write_text(new_svg)
    print(f"wrote {SVG} and the README's Mermaid block")


if __name__ == "__main__":
    main("--check" in sys.argv)
