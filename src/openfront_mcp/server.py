"""Smoke + lifecycle tools over a real FastMCP stdio server.

Plain metadata functions stay importable and the TOOLS registry survives for
scaffold/evals compatibility; a FastMCP server on top registers them under the
same names. The four lifecycle tools (start_smoke_game / get_overview /
end_decision / close_game) talk to the real pinned engine through a
per-lifespan ``GameSession``: one engine worker per server lifespan, with all
requests serialized there. Tools never accept paths.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp.server.fastmcp import Context, FastMCP
from pydantic import StrictInt

from openfront_mcp import scenarios as _scenarios
from openfront_mcp.session import GameSession, SessionError

log = logging.getLogger(__name__)

PIN = "v0.33.14 (577819ba0e1e13ecdbc8dede2ba33de542c88a67)"
CORE_SCOPE = "src/core only; client/server untouched"


def get_pin() -> str:
    return f"upstream-openfrontio {PIN}; scope: {CORE_SCOPE}"


def list_scenarios() -> str:
    names = [s.name for s in _scenarios.SCENARIOS]
    return "scenarios: " + ", ".join(names)


TOOLS = {
    "get_pin": get_pin,
    "list_scenarios": list_scenarios,
}


@asynccontextmanager
async def _lifespan(app: FastMCP[Any]) -> AsyncIterator[GameSession]:
    games = GameSession()
    try:
        yield games
    finally:
        await asyncio.to_thread(games.shutdown)


mcp = FastMCP("openfront-mcp", lifespan=_lifespan)
for _name, _fn in TOOLS.items():
    mcp.add_tool(_fn, name=_name)


def _session_of(ctx: Context) -> GameSession:
    request = ctx.request_context
    if request is None:
        raise SessionError("tool invoked outside a request context")
    return request.lifespan_context


@mcp.tool()
async def start_smoke_game(ctx: Context) -> str:
    """Start the pinned single-human smoke scenario (plains map, no opponents, no victory claims)."""
    return json.dumps(await asyncio.to_thread(_session_of(ctx).start))


@mcp.tool()
async def get_overview(ctx: Context) -> str:
    """Current controlled human state; a pure query that never advances the simulation."""
    return json.dumps(await asyncio.to_thread(_session_of(ctx).overview))


@mcp.tool()
async def end_decision(decision: StrictInt, ctx: Context) -> str:
    """Advance exactly 50 sim ticks for one decision. Pass the exact next expected decision integer; non-integers and stale values are rejected."""
    return json.dumps(await asyncio.to_thread(_session_of(ctx).end_decision, decision))


@mcp.tool()
async def close_game(ctx: Context) -> str:
    """Close the current game and reap its engine worker."""
    return json.dumps(await asyncio.to_thread(_session_of(ctx).close))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info(
        "openfront-mcp serving tools: %s",
        sorted(
            list(TOOLS)
            + [
                "start_smoke_game",
                "get_overview",
                "end_decision",
                "close_game",
            ]
        ),
    )
    mcp.run(transport="stdio")
