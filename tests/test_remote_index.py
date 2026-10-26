"""The api service's bundle read on Vercel: one read per instance, retried.

On 2026-10-26 the live Beat the Model page got 500s: it asks for the
leaderboard and the reader's picks together, and on a cold instance each
request started its own read of all 210 bundles from the web service. The
burst timed out. These tests pin the fix: concurrent requests share one read,
and a bundle read that times out once is tried again.
"""

from __future__ import annotations

import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import cofire.api as api
import pytest
from cofire.ship import cells


def test_concurrent_requests_on_a_cold_instance_share_one_read(monkeypatch: pytest.MonkeyPatch) -> None:
    reads = 0
    guard = threading.Lock()

    def slow_read(base: str) -> dict[str, Any]:
        nonlocal reads
        with guard:
            reads += 1
        time.sleep(0.3)  # long enough that every request arrives during the read
        return {"issues": ["2026-10-20"], "cells": [{"cell_id": "x"}]}

    monkeypatch.setattr(api, "legacy_cells", slow_read)
    monkeypatch.setattr(api, "_INDEX_CACHE", {})
    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(lambda _: api._remote_index("https://example.invalid/data/domains/"), range(12)))
    assert reads == 1
    assert all(r is results[0] for r in results)


def test_an_expired_copy_is_still_served_when_the_re_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_read(base: str) -> dict[str, Any]:
        raise TimeoutError("handshake timed out")

    old = {"issues": ["2026-10-13"], "cells": []}
    monkeypatch.setattr(api, "legacy_cells", failing_read)
    monkeypatch.setattr(api, "_INDEX_CACHE", {"remote": {"at": time.monotonic() - api.REMOTE_INDEX_TTL_S - 1, "index": old}})
    assert api._remote_index("https://example.invalid/data/domains/") is old


def test_a_bundle_read_that_times_out_once_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    class Body:
        def __enter__(self) -> Body:
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"ok": true}'

    def flaky(req: Any, timeout: float) -> Body:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("handshake timed out")
        return Body()

    monkeypatch.setattr(cells.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(cells, "FETCH_BACKOFF_S", 0)
    assert cells._url_reader("https://example.invalid/")("index.json") == {"ok": True}
    assert calls == 2


def test_a_missing_bundle_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def missing(req: Any, timeout: float) -> None:
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(cells.urllib.request, "urlopen", missing)
    with pytest.raises(urllib.error.HTTPError):
        cells._url_reader("https://example.invalid/")("index.json")
    assert calls == 1
