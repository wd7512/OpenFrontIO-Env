"""OpenFront MCP scaffold — tool-mediated agent benchmark for OpenFront.io.

Mirrors the civ6-mcp shape (server + narration + evals) against the vendored
upstream core. See docs/openfront-framework.md. Tools are plain functions in
openfront_mcp.server.TOOLS and are registered on a real FastMCP stdio server
named "openfront-mcp".
"""

from __future__ import annotations

__version__ = "0.1.0"
