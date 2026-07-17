"""Search that blends local substring matching with LLM semantic filtering.

Resolution:
  * mode="local"    -> always substring match (never calls the LLM).
  * mode="semantic" -> always ask the LLM (fall back to local on failure).
  * mode="auto"     -> LLM for natural-language queries (>=3 words) when the LLM
                       is available, else substring match.
"""

from __future__ import annotations

from typing import List, Optional

from ..llm.engine import LLMEngine
from ..models import Item
from .filters import local_text_match, looks_natural_language


def search(
    items: List[Item],
    query: str,
    mode: str = "auto",
    llm: Optional[LLMEngine] = None,
) -> List[Item]:
    query = (query or "").strip()
    if not query:
        return items

    use_llm = False
    if mode == "semantic":
        use_llm = True
    elif mode == "auto":
        use_llm = looks_natural_language(query)

    if use_llm:
        engine = llm or LLMEngine()
        if engine.available():
            payload = [it.model_dump() for it in items]
            ids = engine.semantic_filter(query, payload)
            if ids is not None:
                idset = set(ids)
                return [it for it in items if it.id in idset]
        # LLM unavailable or failed -> graceful fallback.
    return local_text_match(items, query)
