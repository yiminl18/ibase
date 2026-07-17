"""The unified digest pipeline: one entry point for any input.

``digest(source, ...)`` fetches the input (URL or local path), extracts text
(HTML/PDF/text) or OCRs it (image/scanned PDF), auto-summarizes via the LLM,
merges topics, and persists an :class:`Item`.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import List, Optional

from ..llm.engine import LLMEngine
from ..models import Item
from ..store import Store
from . import extract, ocr
from .fetcher import Fetched, fetch, save_upload


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def _extract_content(fetched: Fetched):
    """Return (text, title) for a fetched file, using OCR where needed."""
    fmt = fetched.fmt
    path = fetched.raw_path
    if fmt == "html":
        ex = extract.extract_html(path)
        return ex.text, ex.title
    if fmt == "text":
        ex = extract.extract_text(path)
        return ex.text, None
    if fmt == "pdf":
        ex = extract.extract_pdf(path)
        text = ex.text
        if len(text.strip()) < 40:  # likely scanned -> OCR fallback
            ocr_text = ocr.ocr_pdf(path)
            if ocr_text:
                text = ocr_text
        return text, ex.title
    if fmt == "image":
        return ocr.ocr_image(path), None
    # "other": best effort as utf-8 text.
    try:
        return path.read_text(encoding="utf-8", errors="ignore"), None
    except Exception:
        return "", None


def _merge_topics(user_topics: List[str], llm_topics: List[str]) -> List[str]:
    merged: List[str] = []
    for t in list(user_topics) + list(llm_topics):
        t = (t or "").strip()
        if t and t not in merged:
            merged.append(t)
        if len(merged) == 3:
            break
    return merged


def digest(
    source: str,
    store: Store,
    llm: Optional[LLMEngine] = None,
    note: str = "",
    topics: Optional[List[str]] = None,
) -> Item:
    """Ingest ``source`` (URL or local path) and return the stored item."""
    item_id = _new_id()
    folder = store.item_folder(item_id)
    fetched = fetch(source, folder)
    return _finalize(item_id, folder, fetched, source, store, llm, note, topics)


def digest_upload(
    data: bytes,
    filename: str,
    store: Store,
    llm: Optional[LLMEngine] = None,
    note: str = "",
    topics: Optional[List[str]] = None,
) -> Item:
    """Ingest raw uploaded bytes (a file dropped into the browser)."""
    item_id = _new_id()
    folder = store.item_folder(item_id)
    fetched = save_upload(data, filename, folder)
    source = filename or "upload"
    return _finalize(item_id, folder, fetched, source, store, llm, note, topics)


def _finalize(
    item_id: str,
    folder,
    fetched: Fetched,
    source: str,
    store: Store,
    llm: Optional[LLMEngine],
    note: str,
    topics: Optional[List[str]],
) -> Item:
    """Shared tail of the pipeline: extract -> summarize -> persist."""
    llm = llm or LLMEngine()
    topics = topics or []

    text = ""
    title = None
    if fetched.status == "ok":
        text, title = _extract_content(fetched)

    # Persist extracted text for search/reference.
    content_text_path = None
    if text and text.strip():
        content_file = folder / "content.txt"
        content_file.write_text(text, encoding="utf-8")
        content_text_path = _rel(content_file)

    # Auto-summarize (always, when we have text and the LLM is available).
    summary = ""
    llm_topics: List[str] = []
    if content_text_path:
        result = llm.summarize(text)
        summary = str(result.get("summary", ""))
        llm_topics = list(result.get("topics", []))

    # Decide fetch_status.
    if fetched.status == "failed":
        status = "failed"
    elif not content_text_path:
        status = "partial"  # stored the file but couldn't extract text
    else:
        status = "ok"

    name = (title or fetched.name_hint or source).strip()[:200] or source

    item = Item(
        id=item_id,
        name=name,
        source_link=source,
        local_path=_rel(fetched.raw_path) if fetched.status == "ok" else None,
        content_text_path=content_text_path,
        format=fetched.fmt,
        read=False,
        topics=_merge_topics(topics, llm_topics),
        summary=summary,
        note=note,
        size_bytes=fetched.size_bytes,
        fetch_status=status,
    )
    return store.add(item)


def _rel(path: Path) -> str:
    """Store paths relative to the project root when possible."""
    from .. import config

    try:
        return str(path.resolve().relative_to(config.PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())
