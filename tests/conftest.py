"""Test-wide setup.

The API test posts observations and predictions, and it used to post them into
`data/cofire.db`, the same database the running app reads. Every `make test`
added another "Grass crisp, front yard" report and another `dev1` pick, and 49
runs later the Observe and Predict screens showed a leaderboard of test devices
to anyone who opened them.

Pointing the suite at a throwaway database here, before any test module imports
`cofire.api`, keeps test writes out of the app's data. The engine is built at
import time from `DATABASE_URL`, so this has to happen at conftest load, not in
a fixture.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TEST_DB = Path(tempfile.mkdtemp(prefix="cofire-test-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
