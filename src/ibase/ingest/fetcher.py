"""Fetch raw bytes from a URL or local path and save them under an item folder.

Handles the "any input format" requirement: the caller passes a string that is
either an ``http(s)://`` URL or a local filesystem path. We download/copy the
bytes, detect the format, and return a :class:`Fetched` describing the result.
"""

from __future__ import annotations

import mimetypes
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

import httpx

from .. import config

_FORMAT_BY_PREFIX = {
    "application/pdf": "pdf",
    "text/html": "html",
    "application/xhtml": "html",
    "image/": "image",
    "text/": "text",
}


@dataclass
class Fetched:
    raw_path: Path          # where the bytes were saved
    fmt: str                # "pdf" | "html" | "image" | "text" | "other"
    content_type: str       # best-known MIME type
    size_bytes: int
    name_hint: str          # a human-ish name derived from the source
    status: str             # "ok" | "failed"


def is_url(source: str) -> bool:
    scheme = urlparse(source).scheme.lower()
    return scheme in ("http", "https")


def _format_from_content_type(content_type: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    for prefix, fmt in _FORMAT_BY_PREFIX.items():
        if ct.startswith(prefix):
            return fmt
    return "other"


def _sanitize_filename(name: str, default: str = "download") -> str:
    name = unquote(name).strip().replace("/", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    name = name.strip("._") or default
    return name[:120]


def fetch(source: str, dest_dir: Path) -> Fetched:
    """Fetch ``source`` into ``dest_dir``. Never raises; returns status."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    if is_url(source):
        return _fetch_url(source, dest_dir)
    return _fetch_local(source, dest_dir)

    # (unreachable)


def _fetch_url(url: str, dest_dir: Path) -> Fetched:
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=config.HTTP_TIMEOUT,
            headers={"User-Agent": config.USER_AGENT},
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            body = resp.content
    except Exception:
        return Fetched(
            raw_path=dest_dir / "unfetched",
            fmt="other",
            content_type="",
            size_bytes=0,
            name_hint=_name_from_url(url),
            status="failed",
        )

    fmt = _format_from_content_type(content_type)
    filename = _filename_for_url(url, content_type, fmt)
    raw_path = dest_dir / filename
    raw_path.write_bytes(body)
    return Fetched(
        raw_path=raw_path,
        fmt=fmt,
        content_type=content_type.split(";")[0].strip(),
        size_bytes=len(body),
        name_hint=_name_from_url(url),
        status="ok",
    )


def save_upload(data: bytes, filename: str, dest_dir: Path) -> Fetched:
    """Persist raw uploaded bytes (from a browser) and detect their format."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = _sanitize_filename(filename or "upload")
    content_type = mimetypes.guess_type(safe)[0] or ""
    fmt = _format_from_content_type(content_type)
    if fmt == "other":
        fmt = _format_from_extension(Path(safe).suffix)
    raw_path = dest_dir / safe
    raw_path.write_bytes(data)
    return Fetched(
        raw_path=raw_path,
        fmt=fmt,
        content_type=content_type,
        size_bytes=len(data),
        name_hint=Path(safe).stem,
        status="ok",
    )


def _fetch_local(path_str: str, dest_dir: Path) -> Fetched:
    src = Path(path_str).expanduser()
    if not src.is_file():
        return Fetched(
            raw_path=dest_dir / "missing",
            fmt="other",
            content_type="",
            size_bytes=0,
            name_hint=_sanitize_filename(src.name or path_str),
            status="failed",
        )
    content_type = mimetypes.guess_type(str(src))[0] or ""
    fmt = _format_from_content_type(content_type)
    if fmt == "other":
        fmt = _format_from_extension(src.suffix)
    filename = _sanitize_filename(src.name)
    raw_path = dest_dir / filename
    raw_path.write_bytes(src.read_bytes())
    return Fetched(
        raw_path=raw_path,
        fmt=fmt,
        content_type=content_type,
        size_bytes=raw_path.stat().st_size,
        name_hint=src.stem,
        status="ok",
    )


def _format_from_extension(suffix: str) -> str:
    suffix = suffix.lower().lstrip(".")
    if suffix == "pdf":
        return "pdf"
    if suffix in ("html", "htm"):
        return "html"
    if suffix in ("png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp"):
        return "image"
    if suffix in ("txt", "md", "text"):
        return "text"
    return "other"


def _filename_for_url(url: str, content_type: str, fmt: str) -> str:
    path = urlparse(url).path
    base = os.path.basename(path)
    if base and "." in base:
        return _sanitize_filename(base)
    # Derive an extension from the format/content-type.
    ext = {"pdf": ".pdf", "html": ".html", "text": ".txt"}.get(fmt, "")
    if not ext and fmt == "image":
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".img"
    stem = _sanitize_filename(base or "download")
    return stem + ext if ext and not stem.endswith(ext) else stem or "download"


def _name_from_url(url: str) -> str:
    parsed = urlparse(url)
    base = os.path.basename(parsed.path)
    if base:
        return _sanitize_filename(base).rsplit(".", 1)[0] or parsed.netloc
    return parsed.netloc or url
