"""Extract plain text and a title from fetched HTML / PDF / text files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Extracted:
    text: str
    title: Optional[str] = None


def extract_html(path: Path) -> Extracted:
    from bs4 import BeautifulSoup

    raw = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    return Extracted(text=text, title=title)


def extract_pdf(path: Path) -> Extracted:
    """Extract embedded text from a PDF. Empty text means it may be scanned."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
    except Exception:
        return Extracted(text="")
    title = None
    try:
        if reader.metadata and reader.metadata.title:
            title = str(reader.metadata.title).strip()
    except Exception:
        title = None
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return Extracted(text="\n".join(parts).strip(), title=title)


def extract_text(path: Path) -> Extracted:
    return Extracted(text=path.read_text(encoding="utf-8", errors="ignore"))
