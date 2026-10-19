"""Check a deployment of the site and its API: the things a host can get wrong.

    python scripts/check_deploy.py https://cofire.vercel.app/
    python scripts/check_deploy.py http://127.0.0.1:4100/ --local   # a local static build: pages and files, no API

The browser checks (every route, both languages, axe) are app/e2e/static/;
this covers what they do not see directly:
- pages answer (the web service);
- the forecast bundles are served as JSON;
- the basemap answers byte-range requests (PMTiles reads it in ranges; a host
  that sends the whole 51 MB file instead breaks the map);
- a missing page is a 404, not the home page;
- the api service answers under /api, stores picks in Postgres (not the
  temporary fallback), and reads the forecast cells (the leaderboard).
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import urljoin


def fetch(url: str, headers: dict[str, str] | None = None, limit: int = 1 << 20) -> tuple[int, dict[str, str], bytes]:
    """Status, lower-cased headers and up to `limit` bytes of the body; HTTP errors are returned, not raised."""
    req = urllib.request.Request(url, headers={"User-Agent": "cofire-deploy-check", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read(limit)
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read(limit)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="the site's root, e.g. https://cofire.vercel.app/")
    ap.add_argument("--local", action="store_true", help="a local server: skip the host's headers")
    a = ap.parse_args()
    root: str = a.url if a.url.endswith("/") else a.url + "/"

    def u(path: str) -> str:
        return urljoin(root, path)

    results: list[tuple[str, bool, str]] = []

    def check(name: str, f: Callable[[], tuple[bool, str]]) -> None:
        try:
            ok, detail = f()
        except Exception as e:  # noqa: BLE001 - every failure is reported, not raised
            ok, detail = False, f"{type(e).__name__}: {e}"
        results.append((name, ok, detail))

    def page(path: str) -> tuple[bool, str]:
        s, _, body = fetch(u(path))
        return s == 200 and b"<html" in body[:2000].lower(), f"HTTP {s}"

    for path in ("", "brief/", "scoreboard/", "data/", "hindcast/", "about/"):
        check(f"page /{path}", functools.partial(page, path))

    def bundles() -> tuple[bool, str]:
        s, h, body = fetch(u("data/domains/index.json"))
        idx = json.loads(body)
        return s == 200 and bool(idx.get("issues")), f"HTTP {s}, {len(idx.get('issues', []))} issues, {h.get('content-type')}"

    check("forecast bundles", bundles)

    def ranges() -> tuple[bool, str]:
        s, h, body = fetch(u("tiles/colorado.pmtiles"), {"Range": "bytes=0-126"}, limit=4096)
        ok = s == 206 and body[:7] == b"PMTiles" and len(body) == 127
        return ok, f"HTTP {s}, {len(body)} bytes, content-range {h.get('content-range')}, encoding {h.get('content-encoding', 'none')}"

    check("basemap byte ranges", ranges)

    def missing() -> tuple[bool, str]:
        s, _, _ = fetch(u("no-such-page-here/"))
        return s == 404, f"HTTP {s}"

    check("missing page is 404", missing)

    if not a.local:
        def api_health() -> tuple[bool, str]:
            s, _, body = fetch(u("api/health"))
            got = json.loads(body) if s == 200 else {}
            return s == 200 and got.get("storage") == "postgres", f"HTTP {s}, storage {got.get('storage')} (want postgres)"

        check("api: health and storage", api_health)

        def api_cells() -> tuple[bool, str]:
            s, _, body = fetch(u("api/leaderboard"))
            return s == 200 and isinstance(json.loads(body), list), f"HTTP {s}"

        check("api: leaderboard (database and cells)", api_cells)

    width = max(len(n) for n, _, _ in results)
    for name, ok, detail in results:
        print(f"{'ok  ' if ok else 'FAIL'} {name:<{width}}  {detail}")
    failed = sum(not ok for _, ok, _ in results)
    print(f"\n{len(results) - failed} of {len(results)} checks passed at {root}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
