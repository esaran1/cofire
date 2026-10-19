"""The Vercel deployment: the API under /api, prepared before it opens its database, reading cells from a URL."""

from __future__ import annotations

import functools
import http.server
import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
DEMO_BUNDLES = ROOT / "demo" / "artifacts" / "ship" / "domains"


def test_on_vercel_the_environment_is_prepared_before_the_api_opens_its_database(tmp_path: Path) -> None:
    # A fresh interpreter, as on Vercel: importing the entry point must not let
    # cofire.api open data/cofire.db (read-only there, and the app's own data here).
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "COFIRE_DATABASE_URL", "COFIRE_BUNDLES_URL")}
    env |= {"VERCEL": "1", "WEB_URL": "https://web.internal/"}
    code = (
        "import json, os, sys\n"
        "assert 'cofire.api' not in sys.modules\n"
        "import cofire.deploy.vercel_app\n"
        "from cofire.api import DB_URL, settings\n"
        "print(json.dumps({'db': DB_URL, 'data': str(settings.data_dir), 'bundles': os.environ['COFIRE_BUNDLES_URL']}))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got == {"db": "sqlite:////tmp/cofire/cofire.db", "data": "/tmp/cofire/data", "bundles": "https://web.internal/data/domains/"}


def test_prepare_keeps_a_real_database_and_an_explicit_bundle_address(tmp_path: Path) -> None:
    from cofire.deploy.vercel_env import prepare

    env = {"DATABASE_URL": "postgres://u:p@db.example/cofire", "WEB_URL": "https://web.internal", "COFIRE_BUNDLES_URL": "https://site.example/data/domains/"}
    prepare(env, tmp_path)
    assert env["DATABASE_URL"] == "postgres://u:p@db.example/cofire"
    assert env["COFIRE_BUNDLES_URL"] == "https://site.example/data/domains/"
    assert env["COFIRE_DATA_DIR"] == str(tmp_path / "data") and (tmp_path / "data" / "MANIFEST.json").exists()


@pytest.mark.parametrize(("given", "used"), [
    ("postgres://u:p@h/db?sslmode=require", "postgresql+psycopg://u:p@h/db?sslmode=require"),
    ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ("sqlite:///data/x.db", "sqlite:///data/x.db"),
])
def test_postgres_urls_name_the_driver(monkeypatch: pytest.MonkeyPatch, given: str, used: str) -> None:
    import cofire.api

    monkeypatch.setenv("DATABASE_URL", given)
    assert cofire.api.database_url() == used


@pytest.fixture()
def bundle_server() -> Iterator[str]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DEMO_BUNDLES))
    handler.log_message = lambda *a, **k: None  # type: ignore[method-assign, assignment]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


def test_cells_read_from_a_url_match_the_folder(bundle_server: str) -> None:
    from cofire.ship.cells import legacy_cells

    remote, local = legacy_cells(bundle_server), legacy_cells(DEMO_BUNDLES)
    key = lambda c: (c["domain"], c["issue"], c["cell_id"])  # noqa: E731
    assert remote["issues"] == local["issues"] and len(remote["cells"]) == len(local["cells"]) > 0
    assert sorted(remote["cells"], key=key) == sorted(local["cells"], key=key)


def test_the_api_answers_under_api_with_cells_from_a_url(bundle_server: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import cofire.api
    from cofire.deploy.vercel_app import app

    monkeypatch.setenv("COFIRE_BUNDLES_URL", bundle_server)
    cofire.api._INDEX_CACHE.pop("remote", None)
    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/health").status_code == 404
    idx = json.loads((DEMO_BUNDLES / "index.json").read_text())
    issue = idx["issues"][-1]
    cell = json.loads((DEMO_BUNDLES / idx["order"][0] / f"{issue}.json").read_text())["cells"][0]["id"]
    r = client.post("/api/predictions", json={"device_id": "deploy-test", "cell_id": cell, "horizon": 4,
                                              "drought_category": 2, "fire_band": "low", "issue": issue})
    assert r.status_code == 200, r.text
    assert cofire.api._INDEX_CACHE["remote"]["index"]["issues"] == idx["issues"]
    cofire.api._INDEX_CACHE.pop("remote", None)
