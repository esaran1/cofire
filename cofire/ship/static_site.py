"""Data files for the static deployment of the app.

The static site has no API. It reads the same per-domain bundles the API
serves, copied under `app/public/data/`, and the Ember checklists as JSON. The
Predict and Observe screens need the live service to store picks and reports,
and say so in the static build.

    python -m cofire.ship.static_site [out_dir]
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from cofire.ship import bundles
from cofire.ship.ember_zones import score

OUT = Path("app/public/data")


def build(out: Path = OUT, src: Path = bundles.OUT) -> dict[str, int]:
    if not (src / "index.json").exists():
        raise SystemExit(f"no bundles at {src}; run `python -m cofire.ship.bundles`")
    if out.exists():
        shutil.rmtree(out)
    (out / "domains").mkdir(parents=True)
    shutil.copy2(src / "index.json", out / "domains" / "index.json")
    idx = json.loads((src / "index.json").read_text())
    n = 0
    for dom in idx["order"]:
        (out / "domains" / dom).mkdir()
        for issue in idx["issues"]:
            shutil.copy2(src / dom / f"{issue}.json", out / "domains" / dom / f"{issue}.json")
            n += 1
    (out / "ember").mkdir()
    for zone in ("city", "wui"):
        (out / "ember" / f"{zone}.json").write_text(json.dumps(score({}, zone)))
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    return {"bundles": n, "bytes": size}


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT))
