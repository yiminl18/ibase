"""Pydantic schemas for stored items and API payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

Format = str  # "pdf" | "html" | "image" | "text" | "other"
FetchStatus = str  # "ok" | "partial" | "failed"


def utcnow_iso() -> str:
    """Current UTC time as an ISO-8601 string with a trailing Z."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


class Item(BaseModel):
    """A single collected piece of content and its metadata."""

    id: str
    name: str
    source_link: str
    local_path: Optional[str] = None
    content_text_path: Optional[str] = None
    format: Format = "other"
    read: bool = False
    topics: List[str] = Field(default_factory=list, max_length=3)
    summary: str = ""
    note: str = ""
    inserted_at: str = Field(default_factory=utcnow_iso)
    read_at: Optional[str] = None
    size_bytes: int = 0
    fetch_status: FetchStatus = "ok"


class ItemCreate(BaseModel):
    """Request body for ingesting a new item."""

    link: str = Field(..., description="A URL or a local file path.")
    note: str = ""
    topics: List[str] = Field(default_factory=list, max_length=3)


class ItemUpdate(BaseModel):
    """Partial update of mutable fields (all optional)."""

    read: Optional[bool] = None
    note: Optional[str] = None
    topics: Optional[List[str]] = None
    summary: Optional[str] = None
    name: Optional[str] = None


class Database(BaseModel):
    """Top-level shape of metadata.json."""

    version: int = 1
    items: List[Item] = Field(default_factory=list)
