"""Real 1v1 over MCP stdio: human vs one nation, full lifecycle through tools.

Drives the packaged FastMCP server over a real stdio transport with the real
pinned-engine worker behind the server lifespan. No mocks.
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


async def _call(session: ClientSession, name: str, args: dict) -> tuple[bool, str]:
    result = await asyncio.wait_for(session.call_tool(name, args), 30)
    text = "\n".join(c.text for c in result.content if isinstance(c, TextContent))
    return bool(result.isError), text


@asynccontextmanager
async def _client():
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), 15)
            yield session


def test_1v1_lifecycle_through_tools() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, text = await _call(session, "start_1v1_game", {"map": "plains"})
            assert is_err is False, text
            started = json.loads(text)
            assert started["scenario"] == "plains-1v1-nation"
            assert started["decision"] == 0
            assert started["winner"] is None
            assert started["human"]["tiles"] > 0
            assert len(started["nations"]) == 1
            assert started["nations"][0]["tiles"] > 0

            is_err, first = await _call(session, "get_overview", {})
            assert is_err is False
            is_err, second = await _call(session, "get_overview", {})
            assert is_err is False
            assert json.loads(first) == json.loads(second)

            ticks = [started["tick"]]
            for n in (1, 2, 3):
                is_err, text = await _call(session, "end_decision", {"decision": n})
                assert is_err is False, text
                ticks.append(json.loads(text)["tick"])
            assert ticks[1] - ticks[0] == 50
            assert ticks[2] - ticks[1] == 50

            is_err, text = await _call(session, "get_overview", {})
            assert is_err is False
            overview = json.loads(text)
            assert overview["tick"] == ticks[3]
            assert set(overview) <= {
                "status",
                "scenario",
                "label",
                "tick",
                "decision",
                "next_decision",
                "in_spawn_phase",
                "winner",
                "tribes",
                "tribes_list",
                "boats",
                "boat_targets",
                "units",
                "alliances",
                "alliance_requests",
                "embargoes",
                "human",
                "nations",
                "attacks",
                "incoming_attacks",
            }
            assert set(overview["nations"][0]) == {
                "id",
                "name",
                "troops",
                "gold",
                "tiles",
                "alive",
                "immune",
                "borders_human",
                "incoming_troops",
            }

            is_err, text = await _call(session, "close_game", {})
            assert is_err is False
            assert json.loads(text)["status"] == "closed"

    asyncio.run(scenario())


def test_1v1_rejects_bad_params_and_survives() -> None:
    async def scenario() -> None:
        async with _client() as session:
            for bad in (
                {"nations": 0},
                {"nations": 101},
                {"difficulty": "brutal"},
                {"map": "atlantis"},
            ):
                is_err, _ = await _call(session, "start_1v1_game", bad)
                assert is_err is True, bad
            is_err, text = await _call(session, "start_1v1_game", {"nations": 1})
            assert is_err is False, text
            assert len(json.loads(text)["nations"]) == 1

    asyncio.run(scenario())


def test_britannia_solo_default_through_tools() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, text = await _call(session, "start_1v1_game", {})
            assert is_err is False, text
            started = json.loads(text)
            assert started["scenario"] == "britannia-solo-nations"
            assert started["human"]["tiles"] > 0
            assert len(started["nations"]) == 1
            nation = started["nations"][0]
            assert set(nation) == {
                "id",
                "name",
                "troops",
                "gold",
                "tiles",
                "alive",
                "immune",
                "borders_human",
                "incoming_troops",
            }
            home_tiles = started["human"]["tiles"]

            is_err, text = await _call(
                session, "order_attack", {"target": "expand", "troops": 5000}
            )
            assert is_err is False, text
            is_err, text = await _call(session, "end_decision", {"decision": 1})
            assert is_err is False, text
            is_err, text = await _call(session, "get_overview", {})
            assert is_err is False, text
            assert json.loads(text)["human"]["tiles"] > home_tiles

            is_err, _ = await _call(session, "close_game", {})
            assert is_err is False

    asyncio.run(scenario())


def test_order_attack_expand_then_observe_through_tools() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, text = await _call(session, "start_1v1_game", {})
            assert is_err is False, text
            started = json.loads(text)
            assert started["attacks"] == []
            home_tiles = started["human"]["tiles"]

            for bad in (
                {"target": "nation-9", "troops": 1000},
                {"target": "expand", "troops": 0},
                {"target": "expand", "troops": -5},
                {"target": "expand", "troops": "many"},
                {"target": "human-1", "troops": 1000},
            ):
                is_err, _ = await _call(session, "order_attack", bad)
                assert is_err is True, bad

            is_err, text = await _call(
                session, "order_attack", {"target": "expand", "troops": 5000}
            )
            assert is_err is False, text
            ordered = json.loads(text)
            assert ordered["status"] == "attack-ordered"

            is_err, text = await _call(session, "end_decision", {"decision": 1})
            assert is_err is False, text
            is_err, text = await _call(session, "get_overview", {})
            assert is_err is False, text
            overview = json.loads(text)
            assert set(overview["attacks"][0]) == {
                "id",
                "target",
                "troops",
                "retreating",
            }
            assert overview["human"]["tiles"] > home_tiles

            is_err, text = await _call(session, "close_game", {})
            assert is_err is False

    asyncio.run(scenario())
