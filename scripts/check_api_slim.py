"""Run the Vercel API entry point on the API's own dependencies, as the api service does.

    uv sync --frozen            # the project's dependencies only, no extras: what Vercel installs
    uv run --no-sync python scripts/check_api_slim.py

Serves the committed demo bundles over HTTP, prepares the environment as on
Vercel (writable folders under a temporary directory, SQLite there, the
bundles read from a URL), starts the API under /api with uvicorn, and calls
the endpoints the site uses. Fails if any pipeline package (geopandas, torch,
...) was imported, since the api service's bundle does not have them.
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ROOT / "demo" / "artifacts" / "ship" / "domains"
# Top-level modules of the `pipeline` extra (pyproject.toml). pyarrow is left
# out: pandas imports it when present, and the slim environment has none.
PIPELINE = {
    "geopandas", "shapely", "pyproj", "rasterio", "rioxarray", "xarray", "scipy", "sklearn", "lightgbm",
    "torch", "netCDF4", "h5netcdf", "h5py", "rio_tiler", "shap", "statsmodels", "arch", "climate_indices",
    "aiohttp", "tenacity", "slowapi",
}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


def get(url: str) -> tuple[int, object]:
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def post(url: str, body: dict[str, object]) -> tuple[int, object]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main() -> int:
    os.chdir(ROOT)
    files_port, api_port = free_port(), free_port()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(BUNDLES))
    files = http.server.ThreadingHTTPServer(("127.0.0.1", files_port), handler)
    threading.Thread(target=files.serve_forever, daemon=True).start()

    tmp = Path(tempfile.mkdtemp(prefix="cofire-api-"))
    from cofire.deploy.vercel_env import prepare

    os.environ["WEB_URL"] = f"http://127.0.0.1:{files_port}/unused"
    os.environ["COFIRE_BUNDLES_URL"] = f"http://127.0.0.1:{files_port}/"
    os.environ.pop("DATABASE_URL", None)
    prepare(os.environ, tmp)

    import uvicorn
    from cofire.api import DB_URL
    from cofire.deploy.vercel_app import app

    # Never write a test pick to a real database (data/cofire.db above all).
    if not DB_URL.startswith(f"sqlite:///{tmp}/"):
        print(f"refusing to run: the API opened {DB_URL}, not a database under {tmp}")
        return 1

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=api_port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    base = f"http://127.0.0.1:{api_port}/api"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/health", timeout=1)
            break
        except OSError:
            time.sleep(0.1)

    failures: list[str] = []

    def check(name: str, ok: bool, detail: object) -> None:
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {str(detail)[:160]}")
        if not ok:
            failures.append(name)

    s, health = get(base + "/health")
    check("health", s == 200 and isinstance(health, dict) and health.get("status") == "ok", health)
    index = json.loads((BUNDLES / "index.json").read_text())
    issue, dom = index["issues"][-1], index["order"][0]
    bundle = json.loads((BUNDLES / dom / f"{issue}.json").read_text())
    cell = bundle["cells"][0]["id"]
    s, made = post(base + "/predictions", {"device_id": "slim-check-device", "cell_id": cell, "horizon": 2,
                                           "drought_category": 1, "fire_band": "low", "issue": issue})
    check("POST /predictions", s == 200, made)
    s, mine = get(base + "/predictions/me?device_id=slim-check-device")
    check("GET /predictions/me", s == 200 and isinstance(mine, list) and len(mine) == 1, mine)
    s, board = get(base + "/leaderboard")
    check("GET /leaderboard", s == 200, board)
    s, obs = get(base + "/observations")
    check("GET /observations", s == 200, obs)
    s, ember = get(base + "/ember/checklist?zone=wui")
    check("GET /ember/checklist", s == 200, ember)
    s, missing = get(base + "/no-such-route")
    check("unknown route is 404", s == 404, missing)

    heavy = sorted(PIPELINE & {m.split(".")[0] for m in sys.modules})
    check("no pipeline package imported", not heavy, heavy or "none")
    server.should_exit = True
    files.shutdown()
    print(f"\n{'all checks passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
