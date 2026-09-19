"""Diplomacy parity through real MCP tools.

Drives the packaged server over stdio with the real pinned-engine worker.
Pins: alliance/embargo/donate tool listing, relation projections on start,
request + embargo round-trips, donation acceptance (the engine refuses
without alliance, same as for humans), and rejection of bad targets.
Full outcome mechanics are pinned at engine level (test_engine_diplo.py).
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
    result = await asyncio.wait_for(session.call_tool(name, args), 180)
    text = "\n".join(c.text for c in result.content if isinstance(c, TextContent))
    return bool(result.isError), text


def test_diplo_tools_listed() -> None:
    async def scenario() -> None:
        async with _client() as session:
            tools = await asyncio.wait_for(session.list_tools(), 15)
            names = {t.name for t in tools.tools}
            for tool in (
                "order_alliance_request",
                "order_alliance_reject",
                "order_alliance_extend",
                "order_break_alliance",
                "order_embargo",
                "order_donate_gold",
                "order_donate_troops",
            ):
                assert tool in names, tool

    asyncio.run(scenario())


def test_diplo_round_trip_through_tools() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, text = await _call(
                session, "start_1v1_game", {"nations": 1, "map": "plains"}
            )
            assert is_err is False, text
            started = json.loads(text)
            assert started["alliances"] == []
            assert started["alliance_requests"] == {"incoming": [], "outgoing": []}
            assert started["embargoes"] == []

            is_err, text = await _call(
                session, "order_alliance_request", {"target": "nation-1"}
            )
            assert is_err is False, text
            # The request execution materialises on ticks, like all orders.
            is_err, text = await _call(session, "end_decision", {"decision": 1})
            assert is_err is False, text
            is_err, text = await _call(session, "get_overview", {})
            assert is_err is False, text
            # The request execution materialises on ticks, like all orders.
            # Adjudication timing is nation-AI driven (spawn-dependent): by
            # the time 50 ticks pass it may be pending, accepted, or
            # rejected. Materialisation itself is pinned at engine level;
            # here the tool surface must stay coherent.
            state = json.loads(text)
            valid = {"nation-1"}
            assert {a["id"] for a in state["alliances"]}.issubset(valid)
            assert set(state["alliance_requests"]["outgoing"]).issubset(valid)
            assert set(state["alliance_requests"]["incoming"]).issubset(valid)

            is_err, text = await _call(
                session, "order_embargo", {"target": "nation-1", "action": "start"}
            )
            assert is_err is False, text
            is_err, text = await _call(session, "end_decision", {"decision": 2})
            assert is_err is False, text
            is_err, text = await _call(session, "get_overview", {})
            assert is_err is False, text
            assert [e["id"] for e in json.loads(text)["embargoes"]] == ["nation-1"]

            is_err, text = await _call(
                session, "order_embargo", {"target": "nation-1", "action": "stop"}
            )
            assert is_err is False, text
            is_err, text = await _call(session, "end_decision", {"decision": 3})
            assert is_err is False, text
            is_err, text = await _call(session, "get_overview", {})
            assert is_err is False, text
            assert json.loads(text)["embargoes"] == []

            # Donations are accepted; the engine refuses without alliance.
            is_err, text = await _call(
                session, "order_donate_troops", {"target": "nation-1", "amount": 1000}
            )
            assert is_err is False, text
            is_err, text = await _call(
                session, "order_donate_gold", {"target": "nation-1", "amount": 1000}
            )
            assert is_err is False, text

            # Bad targets, actions, amounts and requestors reject.
            for name, bad in (
                ("order_alliance_request", {"target": "nation-9"}),
                ("order_alliance_reject", {"requestor": "nation-1"}),
                ("order_alliance_extend", {"target": "nation-9"}),
                ("order_break_alliance", {"target": "everyone"}),
                ("order_embargo", {"target": "nation-1", "action": "forever"}),
                ("order_donate_gold", {"target": "nation-1", "amount": 0}),
                ("order_donate_troops", {"target": "nation-1", "amount": -5}),
            ):
                is_err, _ = await _call(session, name, bad)
                assert is_err is True, (name, bad)

            is_err, _ = await _call(session, "close_game", {})
            assert is_err is False

    asyncio.run(scenario())
