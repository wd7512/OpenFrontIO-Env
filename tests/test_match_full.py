"""Full-length 1v1 through real MCP tools: play until production declares a winner.

Scripted (not LLM): passive human, pure advance, stop at the first non-null
winner or after 20 decisions. Pins that a complete match ending is
observable through the tool projections.

Production facts pinned here (verified live against the pinned engine):
- passive human (52 tiles): the nation takes the map and WinCheck declares
  it winner around tick 753;
- expanding human: fronts meet ~tick 553 and the game stalemates (3,315 vs
  6,685) with no winner — the nation never attacks first on easy;
- attacking human: nation attacks land once borders meet, but the nation
  counter-attacks and wins around tick 2,253.
"""

from __future__ import annotations

import asyncio
import json
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
        args=["-m", "openfront_mcp"],
        env=env,
    )


@asynccontextmanager
async def _client():
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), 15)
            yield session


async def _call(session: ClientSession, name: str, args: dict) -> tuple[bool, str]:
    result = await asyncio.wait_for(session.call_tool(name, args), 60)
    text = "\n".join(c.text for c in result.content if isinstance(c, TextContent))
    return bool(result.isError), text


def test_full_match_reaches_a_declared_winner() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, text = await _call(session, "start_1v1_game", {"map": "plains"})
            assert is_err is False, text
            started = json.loads(text)
            nation_name = started["nations"][0]["name"]

            winner = None
            for n in range(1, 21):
                is_err, text = await _call(session, "end_decision", {"decision": n})
                assert is_err is False, text
                is_err, text = await _call(session, "get_overview", {})
                assert is_err is False, text
                overview = json.loads(text)
                if overview["winner"] is not None:
                    winner = overview
                    break

            assert winner is not None, "no winner after 20 decisions (1000 ticks)"
            assert winner["winner"] == nation_name
            assert winner["human"]["tiles"] == 52

            is_err, _ = await _call(session, "close_game", {})
            assert is_err is False

    asyncio.run(scenario())
