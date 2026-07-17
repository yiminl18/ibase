"""OCR for images and scanned PDFs via Tesseract.

Requires the system ``tesseract`` binary. If it (or ``pdf2image``'s poppler
dependency) is missing, every function degrades to returning an empty string so
ingestion still succeeds with ``fetch_status = "partial"``.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_image(path: Path) -> str:
    if not tesseract_available():
        return ""
    try:
        import pytesseract
        from PIL import Image

        with Image.open(path) as img:
            return pytesseract.image_to_string(img).strip()
    except Exception:
        return ""


def ocr_pdf(path: Path, max_pages: int = 20) -> str:
    """Rasterize a scanned PDF and OCR each page (bounded by ``max_pages``)."""
    if not tesseract_available():
        return ""
    try:
        import pytesseract
        from pdf2image import convert_from_path

        images = convert_from_path(str(path), first_page=1, last_page=max_pages)
    except Exception:
        return ""
    parts = []
    for img in images:
        try:
            parts.append(pytesseract.image_to_string(img).strip())
        except Exception:
            continue
    return "\n".join(p for p in parts if p).strip()
