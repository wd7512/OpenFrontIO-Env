"""Build parity through real MCP tools: order_build/upgrade/delete + units.

Drives the packaged server over stdio with the real pinned-engine worker.
Pins: units projection on start/validate, build allowlist + bounds checks,
upgrade/delete id validation, and tool listing. Full build/upgrade/delete
mechanics are pinned at engine level (test_engine_build.py); here the
surface is what matters.
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


def test_build_tools_listed() -> None:
    async def scenario() -> None:
        async with _client() as session:
            tools = await asyncio.wait_for(session.list_tools(), 15)
            names = {t.name for t in tools.tools}
            assert "order_build" in names
            assert "order_upgrade_unit" in names
            assert "order_delete_unit" in names

    asyncio.run(scenario())


def test_build_surface_validation_and_acceptance() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, text = await _call(
                session, "start_solo_game", {"map": "world", "tribes": 0, "nations": 0}
            )
            assert is_err is False, text
            started = json.loads(text)
            assert started["units"] == []

            # Allowlist + bounds reject before touching the engine.
            for bad in (
                {"unit": "death-star", "x": 10, "y": 10},
                {"unit": "city", "x": -1, "y": 10},
                {"unit": "city", "x": "far", "y": 10},
            ):
                is_err, _ = await _call(session, "order_build", bad)
                assert is_err is True, bad

            # Acceptance is the parity bit: the production engine decides
            # landing (gold, owned land), same as a human click.
            is_err, text = await _call(
                session, "order_build", {"unit": "city", "x": 100, "y": 100}
            )
            assert is_err is False, text
            assert json.loads(text)["status"] == "build-ordered"

            is_err, _ = await _call(session, "order_upgrade_unit", {"unit_id": "99999"})
            assert is_err is True
            is_err, _ = await _call(session, "order_delete_unit", {"unit_id": "99999"})
            assert is_err is True

            is_err, text = await _call(session, "get_overview", {})
            assert is_err is False, text
            overview = json.loads(text)
            assert "units" in overview
            assert isinstance(overview["units"], list)

            is_err, _ = await _call(session, "close_game", {})
            assert is_err is False

    asyncio.run(scenario())
