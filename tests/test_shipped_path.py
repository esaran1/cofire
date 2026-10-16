"""The shipped path: what it is, that it never imports research/, and that it is documented.

The shipped path is every module the deployed product runs, found by
following imports from its entry points: the API, the weekly refresh, the
export, the site build, the open data, the forecast record and the facts the
app reads. Non-shipping arms live in research/ (research/README.md says why).
cofire/model/ is frozen at the preregistered commit and is checked by
tests/test_frozen_model.py instead; it is not edited here.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY_POINTS = [
    "cofire.api.main", "cofire.api", "cofire.ship.refresh", "cofire.ship.runner", "cofire.ship.ci_budget",
    "cofire.ship.datapack", "cofire.ship.bundles", "cofire.ship.static_site", "cofire.ship.export",
    "cofire.ship.facts", "cofire.ship.demo", "cofire.v12.facts", "cofire.v12.forward", "cofire.v12.brief_static",
    "cofire.v12.live", "cofire.v13.explain", "cofire.v13.open_data",
]


def _modules() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for p in (ROOT / "cofire").rglob("*.py"):
        name = ".".join(p.relative_to(ROOT).with_suffix("").parts)
        out[name.removesuffix(".__init__")] = p
    return out


def _imports(path: Path, name: str, mods: dict[str, Path]) -> set[str]:
    tree = ast.parse(path.read_text())
    pkg = name if path.name == "__init__.py" else name.rsplit(".", 1)[0]
    found: set[str] = set()
    for n in ast.walk(tree):
        names: list[str] = []
        if isinstance(n, ast.Import):
            names = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            if n.level:
                parts = pkg.split(".")
                base = ".".join(parts[: len(parts) - n.level + 1] + ([base] if base else []))
            names = [f"{base}.{a.name}" if f"{base}.{a.name}" in mods else base for a in n.names]
        for m in names:
            while m and m not in mods:
                m = m.rsplit(".", 1)[0] if "." in m else ""
            if m:
                found.add(m)
    return found


def shipped() -> set[str]:
    """Every cofire module reachable from the entry points, cofire.model included."""
    mods = _modules()
    seen: set[str] = set()
    stack = list(ENTRY_POINTS)
    while stack:
        m = stack.pop()
        if m in seen or m not in mods:
            continue
        seen.add(m)
        stack.extend(_imports(mods[m], m, mods))
    return seen


def test_no_cofire_module_imports_research() -> None:
    offenders = []
    for p in (ROOT / "cofire").rglob("*.py"):
        for n in ast.walk(ast.parse(p.read_text())):
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) else []
            if any(m == "research" or m.startswith("research.") for m in mods):
                offenders.append(str(p.relative_to(ROOT)))
    assert offenders == []


def test_loading_the_shipped_path_never_loads_research() -> None:
    code = "import importlib, sys\n" + "".join(f"importlib.import_module({m!r})\n" for m in ENTRY_POINTS) + \
        "bad = sorted(m for m in sys.modules if m == 'research' or m.startswith('research.'))\nprint(bad)\nassert not bad, bad\n"
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_entry_point_exists() -> None:
    mods = _modules()
    assert [m for m in ENTRY_POINTS if m not in mods] == []


def test_the_shipped_path_is_documented() -> None:
    """Every shipped module outside the frozen model has a module docstring, and so does every public function and class."""
    mods = _modules()
    missing = []
    for name in sorted(shipped()):
        if name.startswith("cofire.model"):
            continue
        tree = ast.parse(mods[name].read_text())
        if not ast.get_docstring(tree) and mods[name].name != "__init__.py":
            missing.append(f"{name} (module)")
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not n.name.startswith("_") and not ast.get_docstring(n):
                missing.append(f"{name}.{n.name}")
    assert missing == [], f"{len(missing)} undocumented: {missing}"
