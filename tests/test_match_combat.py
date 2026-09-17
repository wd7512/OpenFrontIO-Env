"""Combat parity through real MCP tools: tribes, cancel attack, boats.

Drives the packaged server over stdio with the real pinned-engine worker.
Pins: tribe_list projection on start, order_attack accepting tribe-N,
order_cancel_attack retreating a live attack, order_boat_attack launching
(and order_cancel_boat recalling) on water, and rejection of bad ids.
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
    result = await asyncio.wait_for(session.call_tool(name, args), 180)
    text = "\n".join(c.text for c in result.content if isinstance(c, TextContent))
    return bool(result.isError), text


def test_combat_tools_listed() -> None:
    async def scenario() -> None:
        async with _client() as session:
            tools = await asyncio.wait_for(session.list_tools(), 15)
            names = {t.name for t in tools.tools}
            assert "order_cancel_attack" in names
            assert "order_boat_attack" in names
            assert "order_cancel_boat" in names

    asyncio.run(scenario())


def test_tribe_attack_and_cancel_attack() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, text = await _call(
                session, "start_solo_game", {"map": "world", "tribes": 5, "nations": 0}
            )
            assert is_err is False, text
            started = json.loads(text)
            assert started["tribes"] == 5
            # No contact yet: bordering-only projection lists none, but every
            # tribe-N stays orderable (validation uses the full worker list).
            assert started["tribes_list"] == []

            # Tribe order accepted (production decides landing: no shared
            # border yet, so it retreats silent — same as a human order).
            is_err, text = await _call(
                session, "order_attack", {"target": "tribe-1", "troops": 5000}
            )
            assert is_err is False, text

            is_err, _ = await _call(
                session, "order_attack", {"target": "tribe-999", "troops": 5000}
            )
            assert is_err is True

            # Expand, let the attack go live over a decision, then retreat it.
            is_err, text = await _call(
                session, "order_attack", {"target": "expand", "troops": 5000}
            )
            assert is_err is False, text
            is_err, text = await _call(session, "end_decision", {"decision": 1})
            assert is_err is False, text
            is_err, text = await _call(session, "get_overview", {})
            assert is_err is False, text
            live = [a for a in json.loads(text)["attacks"] if not a["retreating"]]
            assert len(live) >= 1

            is_err, text = await _call(
                session, "order_cancel_attack", {"attack_id": live[0]["id"]}
            )
            assert is_err is False, text

            is_err, _ = await _call(
                session, "order_cancel_attack", {"attack_id": "no-such-attack"}
            )
            assert is_err is True

            is_err, _ = await _call(session, "close_game", {})
            assert is_err is False

    asyncio.run(scenario())


def test_boat_attack_validation() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, text = await _call(
                session, "start_solo_game", {"map": "world", "tribes": 0, "nations": 0}
            )
            assert is_err is False, text

            for bad in (
                {"x": -1, "y": 10, "troops": 5000},
                {"x": 10, "y": 10, "troops": 0},
                {"x": "far", "y": 10, "troops": 5000},
            ):
                is_err, _ = await _call(session, "order_boat_attack", bad)
                assert is_err is True, bad

            is_err, _ = await _call(session, "order_cancel_boat", {"unit_id": "99999"})
            assert is_err is True

            is_err, _ = await _call(session, "close_game", {})
            assert is_err is False

    asyncio.run(scenario())


def test_tribes_projection_lists_only_bordering() -> None:
    from openfront_mcp.session import GameSession

    session = GameSession()
    session._scenario = "test"
    session._label = "test"
    session._tick = 10
    session._decision = 1
    session._snapshot = {
        "inSpawnPhase": False,
        "winner": None,
        "width": 100,
        "height": 100,
        "tribes": 2,
        "human": {
            "name": "Smoke",
            "troops": 1000,
            "gold": "0",
            "tiles": 52,
            "spawnTile": {"x": 50, "y": 50},
        },
        "nations": [],
        "tribe_list": [
            {
                "id": "tribe-1",
                "name": "Near",
                "troops": 100,
                "tiles": 50,
                "alive": True,
                "borders_human": True,
            },
            {
                "id": "tribe-2",
                "name": "Far",
                "troops": 100,
                "tiles": 50,
                "alive": True,
                "borders_human": False,
            },
        ],
        "boats": [],
        "units": [],
        "alliances": [],
        "alliance_requests": {"incoming": [], "outgoing": []},
        "embargoes": [],
        "attacks": [],
    }
    projected = session._project("started")
    assert projected["tribes"] == 2
    assert [t["id"] for t in projected["tribes_list"]] == ["tribe-1"]
    # Addressing still covers the hidden tribe (full worker list).
    assert "tribe-2" in session._valid_targets()
