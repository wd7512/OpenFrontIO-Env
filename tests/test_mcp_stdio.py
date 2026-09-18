"""Real stdio MCP handshake/discovery against the packaged server.

Spawn the openfront_mcp server as a subprocess over stdio, complete the
MCP initialize handshake, and read back tools/list. This is the integration
boundary the whole benchmark depends on: the agent client only ever talks
to the engine through this transport.
"""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent


def _server_params() -> StdioServerParameters:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if p)
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "openfront_mcp"],
        env=env,
    )


async def _discover_tools(timeout: float = 15.0) -> tuple[str, set[str]]:
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            init = await asyncio.wait_for(session.initialize(), timeout)
            tools = await asyncio.wait_for(session.list_tools(), timeout)
            return init.serverInfo.name, {t.name for t in tools.tools}


def test_stdio_initialize_and_tools_list() -> None:
    server_name, tool_names = asyncio.run(_discover_tools())
    assert server_name == "openfront-mcp"
    assert {"get_pin"} <= tool_names


async def _call_tool(name: str, arguments: dict, timeout: float = 15.0) -> str:
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout)
            result = await asyncio.wait_for(session.call_tool(name, arguments), timeout)
    return "\n".join(c.text for c in result.content if isinstance(c, TextContent))


def test_stdio_call_tool_get_pin() -> None:
    out = asyncio.run(_call_tool("get_pin", {}))
    assert "v0.33.14" in out
    assert "src/core only" in out
