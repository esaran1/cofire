"""safe_fetch enforces every download rule, without touching the network.

A fake HTTP session plays the server and a throwaway ledger records transfers,
so each rule is exercised deterministically and the real ledger is untouched.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from cofire.model.data.ledger import DownloadLedger
from cofire.ship.safe_fetch import (
    SESSION_CAP_BYTES,
    FetchRefused,
    check_magic,
    safe_extract,
    safe_fetch,
)

NC = b"CDF\x01" + b"\x00" * 200
HTML = b"<!DOCTYPE html><html><body>Service unavailable</body></html>"


class Resp:
    def __init__(self, status: int, headers: dict[str, str], body: bytes = b"") -> None:
        self.status_code = status
        self.headers = headers
        self._body = body

    def iter_content(self, chunk_size: int = 65536):  # noqa: ANN201
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]


class FakeSession:
    """Maps URL to (HEAD response, GET response)."""

    def __init__(self, routes: dict[str, tuple[Resp, Resp | None]]) -> None:
        self.routes = routes
        self.gets: list[str] = []

    def head(self, url: str, **_: object) -> Resp:
        return self.routes[url][0]

    def get(self, url: str, **_: object) -> Resp:
        self.gets.append(url)
        resp = self.routes[url][1]
        assert resp is not None
        return resp


def _ledger(tmp_path: Path, budget: int = 10**9) -> DownloadLedger:
    return DownloadLedger(tmp_path / "ledger.json", budget_bytes=budget)


def _ok(url: str, body: bytes, ctype: str = "application/x-netcdf") -> dict[str, tuple[Resp, Resp | None]]:
    h = {"Content-Length": str(len(body)), "Content-Type": ctype}
    return {url: (Resp(200, h), Resp(200, h, body))}


URL = "https://thredds.northwestknowledge.net/thredds/ncss/MET/erc/erc_2020.nc"


def test_a_good_file_is_saved_and_logged_with_its_hash(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    r = safe_fetch(URL, tmp_path / "a.nc", "netcdf", "gridMET", ledger=led, session=FakeSession(_ok(URL, NC)))
    assert r.path.read_bytes() == NC
    t = led._transfers[-1]
    assert t.bytes == len(NC) and "sha256=" + r.sha256 in t.note and "session=v1.1" in t.note


def test_plain_http_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FetchRefused, match="HTTPS"):
        safe_fetch(URL.replace("https", "http"), tmp_path / "a.nc", "netcdf", "x",
                   ledger=_ledger(tmp_path), session=FakeSession({}))


def test_a_host_off_the_allowlist_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FetchRefused, match="allowlist"):
        safe_fetch("https://example.com/erc.nc", tmp_path / "a.nc", "netcdf", "x",
                   ledger=_ledger(tmp_path), session=FakeSession({}))


def test_a_redirect_off_the_allowlist_aborts(tmp_path: Path) -> None:
    s = FakeSession({URL: (Resp(302, {"Location": "https://evil.example.net/x.nc"}), None)})
    with pytest.raises(FetchRefused, match="allowlist"):
        safe_fetch(URL, tmp_path / "a.nc", "netcdf", "x", ledger=_ledger(tmp_path), session=s)
    assert s.gets == [], "nothing may be downloaded after a bad redirect"


def test_an_html_error_page_with_status_200_is_rejected_and_not_cached(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    dest = tmp_path / "a.nc"
    with pytest.raises(FetchRefused, match="HTML"):
        safe_fetch(URL, dest, "netcdf", "x", ledger=led,
                   session=FakeSession(_ok(URL, HTML, ctype="application/octet-stream")))
    assert not dest.exists() and not dest.with_name("a.nc.part").exists()
    assert "REJECTED" in led._transfers[-1].note, "the wasted bytes are still logged"


def test_a_contradicting_content_type_is_refused_before_download(tmp_path: Path) -> None:
    s = FakeSession(_ok(URL, NC, ctype="text/html"))
    with pytest.raises(FetchRefused, match="HTML page"):
        safe_fetch(URL, tmp_path / "a.nc", "netcdf", "x", ledger=_ledger(tmp_path), session=s)
    assert s.gets == []


def test_the_global_ceiling_is_enforced_from_head(tmp_path: Path) -> None:
    led = _ledger(tmp_path, budget=100)
    s = FakeSession(_ok(URL, NC))
    with pytest.raises(FetchRefused, match="global ceiling"):
        safe_fetch(URL, tmp_path / "a.nc", "netcdf", "x", ledger=led, session=s)
    assert s.gets == []


def test_the_session_cap_is_enforced(tmp_path: Path) -> None:
    led = _ledger(tmp_path, budget=10**12)
    led.record("earlier", "https://x", SESSION_CAP_BYTES - 10, note="session=v1.1; sha256=0")
    with pytest.raises(FetchRefused, match="session cap"):
        safe_fetch(URL, tmp_path / "a.nc", "netcdf", "x", ledger=led, session=FakeSession(_ok(URL, NC)))


def test_a_file_far_from_its_peers_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(FetchRefused, match="peers"):
        safe_fetch(URL, tmp_path / "a.nc", "netcdf", "x", peers=[10_000, 11_000, 9_000],
                   ledger=_ledger(tmp_path), session=FakeSession(_ok(URL, NC)))


def test_no_length_needs_a_stated_maximum(tmp_path: Path) -> None:
    s = FakeSession({URL: (Resp(200, {"Content-Type": "application/json"}), None)})
    with pytest.raises(FetchRefused, match="no Content-Length"):
        safe_fetch(URL, tmp_path / "a.json", "json", "x", ledger=_ledger(tmp_path), session=s)


def test_magic_bytes_per_format() -> None:
    check_magic(b"CDF\x01rest", "netcdf")
    check_magic(b"\x89HDF\r\n\x1a\nrest", "netcdf")
    check_magic(b"II*\x00rest", "geotiff")
    check_magic(b"PK\x03\x04rest", "zip")
    check_magic(b'  {"type": "FeatureCollection"}', "json")
    with pytest.raises(FetchRefused):
        check_magic(b"PK\x03\x04rest", "netcdf")


def test_archive_traversal_and_absolute_entries_are_refused(tmp_path: Path) -> None:
    for bad in ("../escape.txt", "/etc/passwd", "a/../../escape.txt"):
        z = tmp_path / "bad.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr(bad, "x")
        with pytest.raises(FetchRefused, match="escapes|outside"):
            safe_extract(z, tmp_path / "out")


def test_a_clean_archive_extracts_into_its_scope(tmp_path: Path) -> None:
    z = tmp_path / "ok.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("dir/file.txt", "hello")
    out = safe_extract(z, tmp_path / "out")
    assert out == [(tmp_path / "out" / "dir" / "file.txt").resolve()]


def test_a_server_that_refuses_head_is_capped_by_the_stated_maximum(tmp_path: Path) -> None:
    """A 405 to HEAD carries the error body's length, not the file's."""
    url = "https://dwr.state.co.us/Rest/GET/api/v2/x/?format=json"
    body = b'{"ResultList": []}' + b" " * 500
    refused = Resp(405, {"Content-Length": "73", "Content-Type": "application/json"})
    s = FakeSession({url: (refused, Resp(200, {"Content-Type": "application/json"}, body))})
    out = safe_fetch(url, tmp_path / "a.json", "json", "x", max_bytes=10_000, ledger=_ledger(tmp_path), session=s)
    assert out.n_bytes == len(body)
    s = FakeSession({url: (refused, None)})
    with pytest.raises(FetchRefused, match="no Content-Length"):
        safe_fetch(url, tmp_path / "b.json", "json", "x", ledger=_ledger(tmp_path), session=s)


def test_a_shared_host_admits_only_the_named_publisher(tmp_path: Path) -> None:
    from cofire.ship.safe_fetch import check_url

    check_url("https://services3.arcgis.com/66aUo8zsujfVXRIT/arcgis/rest/services/ColoradoEnviroScreen_v2_Tract/FeatureServer/0/query")
    for bad in (
        "https://services3.arcgis.com/someoneElse/arcgis/rest/services/x/FeatureServer/0/query",
        "https://services3.arcgis.com/66aUo8zsujfVXRIT/arcgis/rest/services/Other_Layer/FeatureServer/0",
    ):
        with pytest.raises(FetchRefused, match="path not on the allowlist"):
            check_url(bad)


def test_a_compressed_response_is_capped_by_the_stated_maximum(tmp_path: Path) -> None:
    """Content-Length counts gzip bytes; the stream yields decompressed ones."""
    url = "https://dwr.state.co.us/Rest/GET/api/v2/y/?format=json"
    body = b'{"ResultList": []}' + b" " * 5000
    h = {"Content-Length": "300", "Content-Type": "application/json", "Content-Encoding": "gzip"}
    s = FakeSession({url: (Resp(200, h), Resp(200, h, body))})
    out = safe_fetch(url, tmp_path / "a.json", "json", "x", max_bytes=10_000, ledger=_ledger(tmp_path), session=s)
    assert out.n_bytes == len(body)
    s = FakeSession({url: (Resp(200, h), None)})
    with pytest.raises(FetchRefused, match="no Content-Length"):
        safe_fetch(url, tmp_path / "b.json", "json", "x", ledger=_ledger(tmp_path), session=s)
