"""LLMEngine — a thin, swappable wrapper over an LLM backend.

Backends (``IBASE_LLM_BACKEND``):
  * ``cli``  — shell out to the local ``claude`` binary (uses a Claude
               subscription; no API key needed). This is the default.
  * ``api``  — placeholder for a future direct-API implementation.
  * ``off``  — disable the LLM entirely; every method degrades gracefully.

The engine never raises on LLM failure: summarize returns empty results and
semantic_filter returns ``None`` so callers can fall back to local logic.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Dict, List, Optional

from .. import config

_MAX_TEXT_CHARS = 12000  # cap prompt size; summaries need only the opening.


class LLMEngine:
    def __init__(self, backend: Optional[str] = None) -> None:
        self.backend = (backend or config.LLM_BACKEND).lower()

    # ---- availability --------------------------------------------------------
    def available(self) -> bool:
        if self.backend == "off":
            return False
        if self.backend == "cli":
            return shutil.which(config.CLAUDE_BIN) is not None
        if self.backend == "api":
            return False  # not implemented yet
        return False

    # ---- public operations ---------------------------------------------------
    def summarize(self, text: str) -> Dict[str, object]:
        """Return ``{"summary": str, "topics": [str, ...]}`` (topics <= 3).

        Returns empty values if the LLM is unavailable or fails.
        """
        empty = {"summary": "", "topics": []}
        text = (text or "").strip()
        if not text or not self.available():
            return empty
        prompt = (
            "Summarize the following document in 1-2 sentences and suggest up "
            "to 3 short topic tags (lowercase, hyphenated, no spaces).\n"
            "Respond with ONLY a JSON object of the form "
            '{"summary": "...", "topics": ["tag1", "tag2"]}.\n\n'
            "DOCUMENT:\n" + text[:_MAX_TEXT_CHARS]
        )
        data = self._call_json(prompt)
        if not isinstance(data, dict):
            return empty
        topics = data.get("topics") or []
        if not isinstance(topics, list):
            topics = []
        return {
            "summary": str(data.get("summary", "")).strip(),
            "topics": [str(t).strip() for t in topics if str(t).strip()][:3],
        }

    def semantic_filter(self, query: str, items: List[dict]) -> Optional[List[str]]:
        """Return the ids of items matching a natural-language ``query``.

        Returns ``None`` (not an empty list) when the LLM is unavailable or
        fails, signalling the caller to fall back to local matching.
        """
        if not items or not self.available():
            return None
        catalog = [
            {
                "id": it["id"],
                "name": it.get("name", ""),
                "summary": it.get("summary", ""),
                "topics": it.get("topics", []),
            }
            for it in items
        ]
        prompt = (
            "You are filtering a list of saved documents against a user query.\n"
            "Return ONLY a JSON object {\"ids\": [...]} listing the ids of the "
            "documents that match the query's intent. If none match, return an "
            "empty list.\n\n"
            "QUERY: " + query + "\n\nDOCUMENTS:\n" + json.dumps(catalog)
        )
        data = self._call_json(prompt)
        if not isinstance(data, dict):
            return None
        ids = data.get("ids")
        if not isinstance(ids, list):
            return None
        valid = {it["id"] for it in items}
        return [str(i) for i in ids if str(i) in valid]

    # ---- backend plumbing ----------------------------------------------------
    def _call_json(self, prompt: str) -> Optional[object]:
        """Run the prompt and parse the model's reply as JSON."""
        raw = self._raw_call(prompt)
        if raw is None:
            return None
        return _extract_json(raw)

    def _raw_call(self, prompt: str) -> Optional[str]:
        if self.backend != "cli":
            return None
        cmd = [
            config.CLAUDE_BIN,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--model",
            config.LLM_MODEL,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.LLM_TIMEOUT,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
        if proc.returncode != 0:
            return None
        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return None
        if envelope.get("is_error"):
            return None
        result = envelope.get("result")
        return result if isinstance(result, str) else None


def _extract_json(text: str) -> Optional[object]:
    """Best-effort extraction of the first JSON object/array in ``text``."""
    text = text.strip()
    # Strip a ```json ... ``` fence if present.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the first {...} or [...] span.
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None
