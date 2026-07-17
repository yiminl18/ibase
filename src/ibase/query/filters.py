"""Pure-Python structured filters and local text matching. No LLM."""

from __future__ import annotations

from typing import List, Optional

from ..models import Item


def filter_structured(
    items: List[Item],
    read: Optional[bool] = None,
    topic: Optional[str] = None,
) -> List[Item]:
    """Filter by read status and/or an exact topic tag."""
    out = items
    if read is not None:
        out = [it for it in out if it.read == read]
    if topic:
        t = topic.strip().lower()
        out = [it for it in out if any(tag.lower() == t for tag in it.topics)]
    return out


def local_text_match(items: List[Item], query: str) -> List[Item]:
    """Case-insensitive substring match over name/summary/note/topics."""
    q = (query or "").strip().lower()
    if not q:
        return items
    matched = []
    for it in items:
        haystack = " ".join(
            [it.name, it.summary, it.note, " ".join(it.topics)]
        ).lower()
        if q in haystack:
            matched.append(it)
    return matched


def looks_natural_language(query: str) -> bool:
    """Heuristic: treat multi-word queries as natural language (semantic)."""
    q = (query or "").strip()
    return len(q.split()) >= 3
