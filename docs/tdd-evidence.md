# TDD evidence: real FastMCP stdio server

Date: 2026-09-16. mcp 1.30.0 (uv).

## Red

Added stdio `call_tool` tests for `get_pin` and `list_scenarios` alongside the
existing handshake/discovery test in `tests/test_mcp_stdio.py`.

```
$ uv run pytest tests/test_mcp_stdio.py -q
FAILED tests/test_mcp_stdio.py::test_stdio_initialize_and_tools_list - McpError('Connection closed')
FAILED tests/test_mcp_stdio.py::test_stdio_call_tool_get_pin - McpError("Conn...
FAILED tests/test_mcp_stdio.py::test_stdio_call_tool_list_scenarios - McpError("Conn...
3 failed in 0.17s
```

Server entry point merely logged and exited; the protocol hung up on
`initialize` (`McpError: Connection closed`).

## Green

Implemented a minimal FastMCP stdio server named `openfront-mcp` in
`src/openfront_mcp/server.py` and `src/openfront_mcp/__main__.py`. Existing
plain functions `get_pin`/`list_scenarios` and the `TOOLS` registry are
preserved; the FastMCP instance registers the same tools under the same names.

```
$ uv run pytest tests/test_mcp_stdio.py -q
...                                                          [100%]
3 passed in 0.64s        # initialize + tools/list + call_tool (get_pin, list_scenarios)
```

## Full checks

```
$ uv run pytest -q
.............                                                              [100%]
13 passed in 0.65s
$ uv run ruff check .
All checks passed!
$ uv run ruff format --check .
19 files already formatted
$ uv run ty check
All checks passed!
```

Note: `ty check` initially flagged `c.text` on the content union in the new
test; narrowed with `isinstance(c, TextContent)` to resolve.

Files changed: `src/openfront_mcp/server.py`, `src/openfront_mcp/__main__.py`,
`src/openfront_mcp/__init__.py` (docstring), `tests/test_mcp_stdio.py`.
No commits or pushes made.