"""Pure-Python ranking (sorting). No LLM involved."""

from __future__ import annotations

from typing import List

from ..models import Item

SORTABLE_FIELDS = {
    "inserted_at",
    "read_at",
    "name",
    "read",
    "topics",
    "size_bytes",
    "format",
    "fetch_status",
}
DEFAULT_SORT = "inserted_at"


def _key(item: Item, field: str):
    value = getattr(item, field, None)
    if value is None:
        # Sort missing values last (in ascending order) by using a type-aware
        # sentinel. We normalize everything to (missing_flag, comparable).
        return (1, "")
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, (int, float)):
        return (0, value)
    if isinstance(value, list):
        return (0, ",".join(str(v) for v in value).lower())
    return (0, str(value).lower())


def rank(items: List[Item], sort: str = DEFAULT_SORT,
         order: str = "desc") -> List[Item]:
    """Return a new list of ``items`` sorted by ``sort`` field."""
    if sort not in SORTABLE_FIELDS:
        sort = DEFAULT_SORT
    reverse = str(order).lower() != "asc"
    return sorted(items, key=lambda it: _key(it, sort), reverse=reverse)
