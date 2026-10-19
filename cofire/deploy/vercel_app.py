"""Vercel entry point: the API under /api, as the api service in vercel.json.

Vercel passes each request on with its full path (`/api/leaderboard`), so the
API is mounted under `/api`; `cofire.api.main:app` still serves it from the root
for local runs.

This module lives outside `cofire.api` because importing anything in that
package runs its `__init__`, which opens the database. On Vercel (the VERCEL
variable is set), `vercel_env.prepare` first sets what the API expects:
- **Writable folders.** The deployment's files are read-only. The settings
  create their data and log folders on first use (`cofire/model/config.py`,
  frozen), so those point under /tmp, with the data manifest copied there for
  `/meta` and `/manifest`.
- **The database.** `DATABASE_URL`, set by a Postgres integration, stores picks
  and reports. Without one they go to SQLite under /tmp, kept only while an
  instance lives; `/api/health` then reports storage "temporary".
- **The forecast cells.** Read from the web service's published bundles
  through the `WEB_URL` binding, unless COFIRE_BUNDLES_URL names another
  address.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from cofire.deploy.vercel_env import prepare

if os.environ.get("VERCEL"):
    prepare()

from cofire.api import app as api  # noqa: E402 - after prepare(), which the API's settings read

app = FastAPI(title="COFIRE", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", api)
