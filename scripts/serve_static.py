"""Serve the production static build (app/out) locally, as GitHub Pages would.

    python scripts/serve_static.py [--port 4100] [--root app/out] [--base /cofire]

The site is served under its base path, with HTTP range requests (the
basemap is a PMTiles archive read by byte ranges, and Pages answers those
with 206) and gzip for text (Pages compresses, so captures and Lighthouse
see the same transfer sizes). Standard library only; binds to 127.0.0.1.
"""

from __future__ import annotations

import argparse
import gzip
import mimetypes
import os
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

TEXT = {".html", ".js", ".mjs", ".css", ".json", ".svg", ".txt", ".xml", ".webmanifest", ".map"}
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("application/octet-stream", ".pmtiles")


def resolve(root: Path, base: str, url_path: str) -> Path | None:
    """The file a request path names, or None if it is outside the base or the root."""
    path = unquote(urlsplit(url_path).path)
    if not (path == base or path.startswith(base + "/")):
        return None
    rel = path[len(base):].lstrip("/")
    target = (root / rel).resolve()
    if root not in target.parents and target != root:
        return None
    if target.is_dir():
        target = target / "index.html"
    elif not target.exists() and target.with_suffix(".html").exists():
        target = target.with_suffix(".html")  # Next's static export writes /about as about.html
    return target if target.is_file() else None


class Handler(BaseHTTPRequestHandler):
    root: Path
    base: str

    def log_message(self, fmt: str, *args: object) -> None:  # quiet unless asked
        if os.environ.get("SERVE_VERBOSE"):
            sys.stderr.write(fmt % args + "\n")

    def end_headers(self) -> None:
        # The film renders in its own local origin and reads the basemap from
        # here, by byte ranges: allow that (local only, 127.0.0.1).
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Content-Length, Accept-Ranges, ETag")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, If-Match, If-None-Match")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_HEAD(self) -> None:
        self._serve(head=True)

    def do_GET(self) -> None:
        self._serve(head=False)

    def _serve(self, head: bool) -> None:
        f = resolve(self.root, self.base, self.path)
        if f is None:
            nf = self.root / "404.html"
            body = nf.read_bytes() if nf.exists() else b"not found"
            self.send_response(HTTPStatus.NOT_FOUND)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head:
                self.wfile.write(body)
            return
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        size = f.stat().st_size
        rng = self.headers.get("Range")
        if rng:
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
            if not m or (m.group(1) == "" and m.group(2) == ""):
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            if m.group(1) == "":
                start, end = max(0, size - int(m.group(2))), size - 1
            else:
                start = int(m.group(1))
                end = min(size - 1, int(m.group(2))) if m.group(2) else size - 1
            if start >= size or start > end:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            with f.open("rb") as fh:
                fh.seek(start)
                body = fh.read(end - start + 1)
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            if not head:
                self.wfile.write(body)
            return
        body = f.read_bytes()
        gz = f.suffix in TEXT and "gzip" in (self.headers.get("Accept-Encoding") or "")
        if gz:
            body = gzip.compress(body, compresslevel=6, mtime=0)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "max-age=600")
        if gz:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.end_headers()
        if not head:
            self.wfile.write(body)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=4100)
    ap.add_argument("--root", default="app/out")
    ap.add_argument("--base", default="/cofire")
    a = ap.parse_args(argv)
    Handler.root = Path(a.root).resolve()
    Handler.base = a.base.rstrip("/")
    if not (Handler.root / "index.html").exists():
        raise SystemExit(f"{Handler.root} has no index.html: run scripts/build_static.sh first")
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"serving {Handler.root} at http://127.0.0.1:{a.port}{Handler.base}/", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
