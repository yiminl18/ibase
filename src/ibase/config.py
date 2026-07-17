"""Central configuration: paths and environment-driven settings.

Everything is resolved relative to the project root so the app can be launched
from any working directory. Override the data location with ``IBASE_DATA_DIR``.
"""

from __future__ import annotations

import os
from pathlib import Path

# Project root = two levels up from this file (src/ibase/config.py -> project/).
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default


# Where all user data lives. Gitignored; created on demand.
DATA_DIR = _env_path("IBASE_DATA_DIR", PROJECT_ROOT / "data")
FILES_DIR = DATA_DIR / "files"
METADATA_PATH = DATA_DIR / "metadata.json"

# Static web assets served by FastAPI.
WEB_DIR = PROJECT_ROOT / "web"

# LLM backend selection: "cli" (Claude Code subscription), "api", or "off".
LLM_BACKEND = os.environ.get("IBASE_LLM_BACKEND", "cli").lower()
# Path to the claude binary for the CLI backend.
CLAUDE_BIN = os.environ.get("IBASE_CLAUDE_BIN", "claude")
# Model for the lightweight summarize / semantic-filter calls (fast + cheap).
LLM_MODEL = os.environ.get("IBASE_LLM_MODEL", "haiku")
# Seconds to wait on a single LLM call before falling back to local logic.
LLM_TIMEOUT = float(os.environ.get("IBASE_LLM_TIMEOUT", "60"))

# Networking for ingestion.
HTTP_TIMEOUT = float(os.environ.get("IBASE_HTTP_TIMEOUT", "30"))
USER_AGENT = os.environ.get(
    "IBASE_USER_AGENT",
    "ibase/0.1 (+https://github.com/yiminl18)",
)


def ensure_dirs() -> None:
    """Create the data directories if they do not exist."""
    FILES_DIR.mkdir(parents=True, exist_ok=True)
