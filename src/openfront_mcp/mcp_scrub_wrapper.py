"""Scrub provider credentials from the MCP child, then serve the game MCP."""

from __future__ import annotations

import os

_SCRUB_KEYS = (
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENCODE_GO_API_KEY",
)

for _key in _SCRUB_KEYS:
    os.environ.pop(_key, None)

from openfront_mcp.server import main  # noqa: E402

if __name__ == "__main__":
    main()
