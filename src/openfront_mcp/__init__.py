"""OpenFront MCP scaffold — tool-mediated agent benchmark for OpenFront.io.

Mirrors the civ6-mcp shape (server + narration + evals) against the vendored
upstream core. See docs/openfront-framework.md. FastMCP wiring lands in step 2,
once the `mcp` dependency decision is made; until then tools are plain
functions in openfront_mcp.server.TOOLS.
"""

from __future__ import annotations

__version__ = "0.1.0"
