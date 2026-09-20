"""Retrying HTTP with checksums, resumable downloads, and named source errors."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Final

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

LOGGER = logging.getLogger("cofire.http")
USER_AGENT: Final[str] = "COFIRE/0.1 (Congressional App Challenge; educational; no-auth core pipeline)"
CHUNK = 1024 * 256


class SourceFetchError(RuntimeError):
    def __init__(self, source: str, url: str, message: str) -> None:
        super().__init__(f"{source}: {message} (url={url})")
        self.source = source
        self.url = url
        self.message = message


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type((requests.RequestException, SourceFetchError)),
)
def get_bytes(
    url: str,
    *,
    source: str,
    timeout: int = 120,
    headers: dict[str, str] | None = None,
) -> bytes:
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    try:
        response = requests.get(url, headers=hdrs, timeout=timeout)
    except requests.RequestException as exc:
        raise SourceFetchError(source, url, f"request failed: {exc}") from exc
    if response.status_code >= 400:
        raise SourceFetchError(source, url, f"HTTP {response.status_code}")
    return response.content


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type((requests.RequestException, SourceFetchError)),
)
def download_file(
    url: str,
    dest: Path,
    *,
    source: str,
    timeout: int = 300,
    headers: dict[str, str] | None = None,
) -> Path:
    """Idempotent download. Resumes if dest.partial exists and the server allows Range."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    partial = dest.with_suffix(dest.suffix + ".partial")
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    existing = partial.stat().st_size if partial.exists() else 0
    if existing:
        hdrs["Range"] = f"bytes={existing}-"

    try:
        response = requests.get(url, headers=hdrs, timeout=timeout, stream=True)
    except requests.RequestException as exc:
        raise SourceFetchError(source, url, f"download failed: {exc}") from exc

    if response.status_code == 416:
        # Partial is already complete; just rename.
        partial.replace(dest)
        return dest
    if response.status_code >= 400:
        raise SourceFetchError(source, url, f"HTTP {response.status_code}")

    mode = "ab" if response.status_code == 206 and existing else "wb"
    if mode == "wb" and partial.exists():
        partial.unlink()
    with partial.open(mode) as handle:
        for chunk in response.iter_content(CHUNK):
            if chunk:
                handle.write(chunk)
    partial.replace(dest)
    LOGGER.info("downloaded %s -> %s (%s bytes)", url, dest, dest.stat().st_size)
    return dest


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
