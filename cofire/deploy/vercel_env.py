"""The environment the API expects on Vercel, set before the API is imported.

Kept apart from cofire.deploy.vercel_app, which imports the API, and outside
the cofire.api package, whose `__init__` opens the database: importing this
module opens nothing, so callers (and tests) can prepare first. See
cofire.deploy.vercel_app for what each setting is for.
"""

from __future__ import annotations

import logging
import os
import shutil
from collections.abc import MutableMapping
from pathlib import Path

LOGGER = logging.getLogger("cofire.deploy.vercel")


def prepare(env: MutableMapping[str, str] = os.environ, tmp: Path = Path("/tmp/cofire")) -> None:
    """Set the environment the API reads at import, for a read-only deployment."""
    data = tmp / "data"
    data.mkdir(parents=True, exist_ok=True)
    env.setdefault("COFIRE_DATA_DIR", str(data))
    env.setdefault("COFIRE_LOG_DIR", str(tmp / "logs"))
    manifest = Path("data/MANIFEST.json")
    if manifest.exists() and not (data / "MANIFEST.json").exists():
        shutil.copy2(manifest, data / "MANIFEST.json")
    if not (env.get("DATABASE_URL") or env.get("COFIRE_DATABASE_URL")):
        LOGGER.warning("no DATABASE_URL: picks and reports are stored under /tmp and lost when the instance stops")
        env["DATABASE_URL"] = f"sqlite:///{tmp}/cofire.db"
    if not env.get("COFIRE_BUNDLES_URL") and env.get("WEB_URL"):
        env["COFIRE_BUNDLES_URL"] = env["WEB_URL"].rstrip("/") + "/data/domains/"
