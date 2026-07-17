"""Full query pipeline: structured filter -> search -> rank."""

from __future__ import annotations

from typing import List, Optional

from ..llm.engine import LLMEngine
from ..models import Item
from . import filters, ranker, semantic


def run_query(
    items: List[Item],
    *,
    read: Optional[bool] = None,
    topic: Optional[str] = None,
    q: str = "",
    q_mode: str = "auto",
    sort: str = ranker.DEFAULT_SORT,
    order: str = "desc",
    llm: Optional[LLMEngine] = None,
) -> List[Item]:
    result = filters.filter_structured(items, read=read, topic=topic)
    if q and q.strip():
        result = semantic.search(result, q, mode=q_mode, llm=llm)
    return ranker.rank(result, sort=sort, order=order)
