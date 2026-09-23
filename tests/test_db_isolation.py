"""The test suite must never write to the app's own database."""

from __future__ import annotations


def test_api_engine_is_not_the_app_database() -> None:
    from cofire.api import engine

    url = str(engine.url)
    assert "cofire-test-" in url, f"tests are writing to {url}"
    assert not url.endswith("data/cofire.db")
