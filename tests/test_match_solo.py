"""Identical solo format through real MCP tools: World + 400 tribes.

Drives the packaged server over stdio with the real pinned-engine worker.
Pins the online solo defaults: full World board, 400 neutral tribes,
0 nations, and the scenario label.
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
    result = await asyncio.wait_for(session.call_tool(name, args), 120)
    text = "\n".join(c.text for c in result.content if isinstance(c, TextContent))
    return bool(result.isError), text


def test_solo_default_matches_online_format() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, text = await _call(
                session,
                "start_solo_game",
                {"map": "world", "tribes": 400, "nations": 0},
            )
            assert is_err is False, text
            started = json.loads(text)
            assert started["scenario"] == "world-solo-tribes"
            assert started["tribes"] == 400
            assert started["nations"] == []
            assert started["human"]["tiles"] > 0
            home_tiles = started["human"]["tiles"]

            is_err, text = await _call(
                session, "order_attack", {"target": "expand", "percent": 20}
            )
            assert is_err is False, text
            is_err, text = await _call(session, "end_decision", {"decision": 1})
            assert is_err is False, text
            is_err, text = await _call(session, "get_overview", {})
            assert is_err is False, text
            overview = json.loads(text)
            assert overview["tribes"] == 400
            assert overview["human"]["tiles"] > home_tiles

            is_err, _ = await _call(session, "close_game", {})
            assert is_err is False

    asyncio.run(scenario())


def test_solo_rejects_bad_tribes_and_survives() -> None:
    async def scenario() -> None:
        async with _client() as session:
            for bad in (
                {"tribes": -1},
                {"tribes": 501},
                {"tribes": "many"},
                {"nations": 101},
            ):
                is_err, _ = await _call(session, "start_solo_game", bad)
                assert is_err is True, bad
            is_err, text = await _call(session, "start_solo_game", {"tribes": 10})
            assert is_err is False, text
            assert json.loads(text)["tribes"] == 10

    asyncio.run(scenario())


def test_europe_ffa_is_the_default_solo() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, text = await _call(session, "start_solo_game", {})
            assert is_err is False, text
            started = json.loads(text)
            assert started["scenario"] == "europe-solo-tribes"
            assert started["tribes"] == 400
            assert len(started["nations"]) == 52
            assert started["human"]["tiles"] > 0
            home_tiles = started["human"]["tiles"]

            is_err, text = await _call(
                session, "order_attack", {"target": "expand", "percent": 20}
            )
            assert is_err is False, text
            is_err, text = await _call(session, "end_decision", {"decision": 1})
            assert is_err is False, text
            is_err, text = await _call(session, "get_overview", {})
            assert is_err is False, text
            overview = json.loads(text)
            assert overview["human"]["tiles"] > home_tiles

            is_err, _ = await _call(session, "close_game", {})
            assert is_err is False

    asyncio.run(scenario())
