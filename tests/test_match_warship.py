"""Warship maneuver through the real MCP tool: listing + validation.

Drives the packaged server over stdio with the real pinned-engine worker.
The full port -> warship -> patrol chain is pinned at engine level
(test_engine_warship.py); here the surface is what matters: the tool is
listed, live warship ids are required, and bounds are checked.
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent


def _server_params() -> StdioServerParameters:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if p)
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "openfrontbench"],
        env=env,
    )


@asynccontextmanager
async def _client():
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), 15)
            yield session


async def _call(session: ClientSession, name: str, args: dict) -> tuple[bool, str]:
    result = await asyncio.wait_for(session.call_tool(name, args), 180)
    text = "\n".join(c.text for c in result.content if isinstance(c, TextContent))
    return bool(result.isError), text


def test_move_warship_tool_listed() -> None:
    async def scenario() -> None:
        async with _client() as session:
            tools = await asyncio.wait_for(session.list_tools(), 15)
            assert "order_move_warship" in {t.name for t in tools.tools}

    asyncio.run(scenario())


def test_move_warship_validation() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, text = await _call(
                session, "start_solo_game", {"map": "world", "tribes": 0, "nations": 0}
            )
            assert is_err is False, text

            # No warships afloat: every id is unknown.
            is_err, _ = await _call(
                session, "order_move_warship", {"unit_id": "1", "x": 10, "y": 10}
            )
            assert is_err is True
            # Bounds reject before touching the engine.
            is_err, _ = await _call(
                session, "order_move_warship", {"unit_id": "1", "x": -1, "y": 10}
            )
            assert is_err is True

            is_err, _ = await _call(session, "close_game", {})
            assert is_err is False

    asyncio.run(scenario())
