"""Every outside link the app shows residents is registered, and each one works.

The offline tests run in CI on every push. The live check opens every page and
reads its title; it runs weekly in .github/workflows/links.yml, or locally with
COFIRE_CHECK_LINKS=1. It reads web pages, not data, so it is not a download
under the ledger: nothing is cached or parsed beyond the <title>.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
import yaml

APP = Path("app")
LINKS_TS = (APP / "lib/links.ts").read_text()
REGISTRY = {
    m[0]: {"url": m[1], "title": m[2]}
    for m in re.findall(r'\n  "?(\w+)"?: \{\n    id: "\w+",\n    url: "([^"]+)",\n    publisher: "[^"]+",\n    title: "([^"]+)",', LINKS_TS)
}
EMBER_LINKS = dict(re.findall(r'\n  "?(\w+)"?: "(\w+)",', LINKS_TS.split("EMBER_LINKS")[1]))
CREDITS = [c["url"] for c in json.loads((APP / "lib/facts.json").read_text())["credits"]]
# Linked from the landing page's photo credit.
EXTRA = {"https://creativecommons.org/licenses/by/2.0/"}


def test_the_registry_parses_and_every_link_is_https() -> None:
    assert len(REGISTRY) >= 10
    assert all(v["url"].startswith("https://") for v in REGISTRY.values())


def test_every_ember_action_link_points_into_the_registry() -> None:
    ids = set()
    for f in ("cofire/ship/ember_city.yaml", "cofire/model/ember_checklist.yaml"):
        for group in yaml.safe_load(Path(f).read_text()).values():
            if isinstance(group, dict):
                ids |= {i["id"] for i in group.get("items", [])}
    assert EMBER_LINKS, "EMBER_LINKS did not parse"
    for item, link in EMBER_LINKS.items():
        assert item in ids, f"{item} is not an Ember item"
        assert link in REGISTRY, f"{item} points at unknown link {link}"


def test_no_page_renders_an_unregistered_outside_link() -> None:
    known = {v["url"] for v in REGISTRY.values()} | set(CREDITS) | EXTRA
    for src in [*APP.glob("app/**/*.tsx"), *APP.glob("components/**/*.tsx")]:
        for url in re.findall(r'href="(https?://[^"]+)"', src.read_text()):
            assert url in known, f"{src}: {url} is not in lib/links.ts or the credits"


def _title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


@pytest.mark.skipif(not os.environ.get("COFIRE_CHECK_LINKS"), reason="live link check: set COFIRE_CHECK_LINKS=1")
@pytest.mark.parametrize("url", sorted({v["url"] for v in REGISTRY.values()} | set(CREDITS) | EXTRA))
def test_the_link_opens_the_page_it_names(url: str) -> None:
    import requests

    r = requests.get(url, timeout=30, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; COFIRE link check)"})
    assert r.status_code == 200, f"{url} returned {r.status_code}"
    expected = next((v["title"] for v in REGISTRY.values() if v["url"] == url), None)
    if expected:
        title = _title(r.text[:200_000])
        assert expected.lower() in title.lower(), f"{url}: title {title!r} lacks {expected!r}"
