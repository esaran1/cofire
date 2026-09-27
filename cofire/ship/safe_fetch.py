"""Every network fetch for v1.1 goes through here.

The rules, each enforced in code and tested in tests/test_safe_fetch.py:

1. HTTPS only, to hosts on an explicit allowlist. Redirects are followed by
   hand, one hop at a time, and a hop to any host off the list aborts.
2. HEAD first. Content-Length and Content-Type are read before any body is
   transferred; a fetch that would push the session past its cap, or the
   ledger past its global ceiling, is refused, as is a Content-Type that
   contradicts the expected format. Where the server gives no length, the
   caller states a maximum and the body is streamed with a hard stop.
3. Magic bytes are checked after download. A body beginning `<!DOCTYPE` or
   `<html` is an error page served with status 200; it is rejected, logged, and
   never cached. This project has been bitten by that twice.
4. Size sanity: a file more than 5x or less than 0.2x the median of its peers
   in the same series is rejected.
5. Archives are never executed, and entries with `..` or a leading `/` are
   refused; extraction goes to a scoped directory and files are moved out
   explicitly.
6. Every transfer is logged to data/ledger.json with URL, bytes, sha256 and
   timestamp, tagged with the session so the session cap is enforced from the
   ledger itself.

The ledger's own save routine keeps only the fields it knows, so the session
sub-budget is carried in the transfer notes rather than a new top-level key.
"""

from __future__ import annotations

import hashlib
import logging
import statistics
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

LOGGER = logging.getLogger("cofire.ship.safe_fetch")

SESSION = "v1.1"
SESSION_CAP_BYTES = 2_000_000_000

ALLOWED_HOSTS = frozenset({
    # Climatology Lab / Northwest Knowledge Network (gridMET)
    "thredds.northwestknowledge.net",
    "www.northwestknowledge.net",
    # US Drought Monitor
    "droughtmonitor.unl.edu",
    # USGS boundary and hydrography services
    "hydro.nationalmap.gov",
    "index.nationalmap.gov",
    # Census boundaries
    "www2.census.gov",
    "tigerweb.geo.census.gov",
    # NOAA and NRCS hosts already in use
    "downloads.psl.noaa.gov",
    "wcc.sc.egov.usda.gov",
})

# Accepted Content-Type prefixes per expected format. A mismatch refuses.
CONTENT_TYPES = {
    "netcdf": ("application/x-netcdf", "application/netcdf", "application/octet-stream", "application/x-hdf5"),
    "geotiff": ("image/tiff", "application/octet-stream"),
    "zip": ("application/zip", "application/x-zip-compressed", "application/octet-stream"),
    "json": ("application/json", "application/geo+json", "text/plain"),
    # OPeNDAP metadata responses (.dds, .das), which open with a fixed keyword.
    "dap": ("text/plain",),
}


class FetchRefused(RuntimeError):
    """A fetch that broke one of the rules. Nothing was cached."""


@dataclass
class FetchResult:
    url: str
    path: Path
    n_bytes: int
    sha256: str


def check_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme != "https":
        raise FetchRefused(f"not HTTPS: {url}")
    if u.hostname not in ALLOWED_HOSTS:
        raise FetchRefused(f"host not on the allowlist: {u.hostname}")


def check_magic(head: bytes, fmt: str) -> None:
    """Reject error pages and anything that is not the expected format."""
    stripped = head.lstrip()[:15].lower()
    if stripped.startswith(b"<!doctype") or stripped.startswith(b"<html"):
        raise FetchRefused("body is an HTML page, not data (an error page served with status 200)")
    ok = {
        "netcdf": head[:3] == b"CDF" or head[:8] == b"\x89HDF\r\n\x1a\n",
        "geotiff": head[:4] in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"),
        "zip": head[:4] == b"PK\x03\x04",
        "json": head.lstrip()[:1] in (b"{", b"["),
        "dap": head.lstrip().startswith((b"Dataset", b"Attributes")),
    }.get(fmt)
    if ok is None:
        raise FetchRefused(f"unknown expected format {fmt!r}")
    if not ok:
        raise FetchRefused(f"first bytes {head[:8]!r} are not {fmt}")


def check_peer_size(n_bytes: int, peers: list[int]) -> None:
    if not peers:
        return
    med = statistics.median(peers)
    if med <= 0:
        return
    ratio = n_bytes / med
    if ratio > 5.0 or ratio < 0.2:
        raise FetchRefused(f"size {n_bytes} B is {ratio:.2f}x its peers' median {med:.0f} B")


def session_bytes(ledger: object) -> int:
    transfers = getattr(ledger, "_transfers", [])
    return sum(t.bytes for t in transfers if f"session={SESSION}" in (t.note or ""))


def safe_extract(archive: Path, dest: Path) -> list[Path]:
    """Extract a zip into `dest`, refusing traversal and absolute entries."""
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename
            if name.startswith("/") or name.startswith("\\") or ".." in Path(name).parts:
                raise FetchRefused(f"archive entry escapes its directory: {name!r}")
            target = (dest / name).resolve()
            if dest not in target.parents and target != dest:
                raise FetchRefused(f"archive entry resolves outside {dest}: {name!r}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as fh:
                fh.write(src.read())
            out.append(target)
    return out


def safe_fetch(
    url: str,
    dest: Path,
    fmt: str,
    source: str,
    *,
    max_bytes: int | None = None,
    peers: list[int] | None = None,
    ledger: object | None = None,
    session: object | None = None,
    max_redirects: int = 5,
) -> FetchResult:
    """Fetch `url` to `dest` under every rule above, or raise FetchRefused."""
    import requests

    from cofire.model.data.ledger import get_ledger

    led = ledger if ledger is not None else get_ledger()
    http = session if session is not None else requests.Session()

    # Resolve redirects by hand so every hop is checked.
    current = url
    for _ in range(max_redirects + 1):
        check_url(current)
        head = http.head(current, allow_redirects=False, timeout=60)  # type: ignore[attr-defined]
        if head.status_code in (301, 302, 303, 307, 308):
            current = urljoin(current, head.headers.get("Location", ""))
            continue
        break
    else:
        raise FetchRefused(f"too many redirects from {url}")
    if head.status_code >= 400 and head.status_code != 405:
        raise FetchRefused(f"HEAD {current} returned {head.status_code}")

    ctype = (head.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ctype and ctype.startswith("text/html"):
        raise FetchRefused(f"Content-Type {ctype} is an HTML page, expected {fmt}")
    if ctype and not any(ctype.startswith(p) for p in CONTENT_TYPES[fmt]):
        raise FetchRefused(f"Content-Type {ctype} contradicts expected {fmt}")
    length = head.headers.get("Content-Length")
    projected = int(length) if length is not None and length.isdigit() else max_bytes
    if projected is None:
        raise FetchRefused(f"no Content-Length for {current} and no max_bytes stated")
    if session_bytes(led) + projected > SESSION_CAP_BYTES:
        raise FetchRefused(f"would exceed the {SESSION} session cap of {SESSION_CAP_BYTES} B")
    if not led.can_afford(projected):  # type: ignore[attr-defined]
        raise FetchRefused(
            f"would exceed the ledger's global ceiling: {projected} B requested, "
            f"{led.remaining_bytes} B remaining"  # type: ignore[attr-defined]
        )

    resp = http.get(current, stream=True, allow_redirects=False, timeout=300)  # type: ignore[attr-defined]
    if resp.status_code in (301, 302, 303, 307, 308):
        raise FetchRefused(f"GET redirected after HEAD did not: {current}")
    if resp.status_code != 200:
        raise FetchRefused(f"GET {current} returned {resp.status_code}")
    cap = projected if length is not None else max_bytes
    tmp = dest.with_name(dest.name + ".part")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    n = 0
    first = b""
    try:
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                if not chunk:
                    continue
                if len(first) < 64:
                    first += chunk[: 64 - len(first)]
                n += len(chunk)
                if cap is not None and n > cap * 1.05 + 1024:
                    raise FetchRefused(f"body exceeded its stated size ({n} > {cap} B)")
                digest.update(chunk)
                fh.write(chunk)
        check_magic(first, fmt)
        check_peer_size(n, peers or [])
    except FetchRefused:
        tmp.unlink(missing_ok=True)
        LOGGER.warning("refused and not cached: %s", current)
        # The bytes crossed the wire even though the file is rejected.
        led.record(source, current, n, note=f"session={SESSION}; REJECTED")  # type: ignore[attr-defined]
        raise
    tmp.replace(dest)
    sha = digest.hexdigest()
    led.record(source, current, n, note=f"session={SESSION}; sha256={sha}")  # type: ignore[attr-defined]
    return FetchResult(current, dest, n, sha)
