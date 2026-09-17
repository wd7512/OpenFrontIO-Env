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
from openfront_mcp.session import (
    MAX_TOOL_NATIONS,
    MAX_TOOL_TRIBES,
    GameSession,
    SessionError,
)

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
async def start_1v1_game(
    ctx: Context,
    nations: StrictInt = 1,
    difficulty: str = "easy",
    map: str = "britannia",
) -> str:
    """Start a solo match: one human vs nation opponents (1-4 nations, easy/medium/hard/impossible) on britannia (production Compact board) or plains (fast fixture)."""
    if isinstance(nations, bool) or not 1 <= nations <= MAX_TOOL_NATIONS:
        raise SessionError(
            f"nations must be an integer in [1, {MAX_TOOL_NATIONS}] for a match"
        )
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).start, nations, difficulty, map)
    )


@mcp.tool()
async def start_solo_game(
    ctx: Context,
    tribes: StrictInt = 400,
    nations: StrictInt = 52,
    difficulty: str = "easy",
    map: str = "europe",
) -> str:
    """Start the default solo format: one human, 400 neutral tribes, 52 nations on full Europe FFA (easy/medium/hard/impossible)."""
    if isinstance(tribes, bool) or not 0 <= tribes <= MAX_TOOL_TRIBES:
        raise SessionError(
            f"tribes must be an integer in [0, {MAX_TOOL_TRIBES}] for a solo game"
        )
    if isinstance(nations, bool) or not 0 <= nations <= MAX_TOOL_NATIONS:
        raise SessionError(
            f"nations must be an integer in [0, {MAX_TOOL_NATIONS}] for a solo game"
        )
    return json.dumps(
        await asyncio.to_thread(
            _session_of(ctx).start, nations, difficulty, map, tribes
        )
    )


@mcp.tool()
async def get_overview(ctx: Context) -> str:
    """Current controlled human state; a pure query that never advances the simulation."""
    return json.dumps(await asyncio.to_thread(_session_of(ctx).overview))


@mcp.tool()
async def end_decision(decision: StrictInt, ctx: Context) -> str:
    """Advance exactly 50 sim ticks for one decision. Pass the exact next expected decision integer; non-integers and stale values are rejected."""
    return json.dumps(await asyncio.to_thread(_session_of(ctx).end_decision, decision))


@mcp.tool()
async def order_attack(
    ctx: Context, target: str = "expand", troops: StrictInt = 1000
) -> str:
    """Order the human to expand or attack: target "expand" (adjacent neutral land), "nation-N" or "tribe-N", with a positive integer troop count. Production rules (immunity, shared border) decide whether the order lands; the result reports live attacks."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_attack, target, troops)
    )


@mcp.tool()
async def order_cancel_attack(ctx: Context, attack_id: str = "") -> str:
    """Retreat a live outgoing attack by its id (from get_overview attacks). Unknown ids are rejected."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_cancel_attack, attack_id)
    )


@mcp.tool()
async def order_boat_attack(
    ctx: Context, x: StrictInt = 0, y: StrictInt = 0, troops: StrictInt = 1000
) -> str:
    """Launch a boat attack at tile (x, y) with a positive integer troop count. Bounds are checked; the engine validates the tile (needs shore and water, same as a human order)."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_boat_attack, x, y, troops)
    )


@mcp.tool()
async def order_cancel_boat(ctx: Context, unit_id: str = "") -> str:
    """Recall a transport ship by its id (from get_overview boats). Unknown ids are rejected."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_cancel_boat, unit_id)
    )


@mcp.tool()
async def order_build(
    ctx: Context, unit: str = "city", x: StrictInt = 0, y: StrictInt = 0
) -> str:
    """Order a build-menu unit (city, defense-post, sam-launcher, missile-silo, port, factory, atom-bomb, hydrogen-bomb, mirv, warship) at tile (x, y). The engine validates gold, costs and tiles — acceptance, not landing, is the contract."""
    return json.dumps(await asyncio.to_thread(_session_of(ctx).order_build, unit, x, y))


@mcp.tool()
async def order_upgrade_unit(ctx: Context, unit_id: str = "") -> str:
    """Upgrade a human unit by its id (from get_overview units). Unknown ids are rejected; only some structures are upgradable in production."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_upgrade_unit, unit_id)
    )


@mcp.tool()
async def order_delete_unit(ctx: Context, unit_id: str = "") -> str:
    """Delete a human unit by its id (from get_overview units). Unknown ids are rejected; removal follows a production grace period."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_delete_unit, unit_id)
    )


@mcp.tool()
async def order_alliance_request(ctx: Context, target: str = "") -> str:
    """Request an alliance with a nation or tribe (nation-N / tribe-N). The recipient's AI answers on its own schedule, same as for a human."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_alliance_request, target)
    )


@mcp.tool()
async def order_alliance_reject(ctx: Context, requestor: str = "") -> str:
    """Reject a pending incoming alliance request from a nation or tribe. Only listed incoming requestors are answerable."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_alliance_reject, requestor)
    )


@mcp.tool()
async def order_alliance_extend(ctx: Context, target: str = "") -> str:
    """Extend the alliance with a nation or tribe (nation-N / tribe-N)."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_alliance_extend, target)
    )


@mcp.tool()
async def order_break_alliance(ctx: Context, target: str = "") -> str:
    """Break the alliance with a nation or tribe (nation-N / tribe-N)."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_break_alliance, target)
    )


@mcp.tool()
async def order_embargo(ctx: Context, target: str = "", action: str = "start") -> str:
    """Start or stop an embargo on a nation or tribe (nation-N / tribe-N, action start|stop)."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_embargo, target, action)
    )


@mcp.tool()
async def order_donate_gold(
    ctx: Context, target: str = "", amount: StrictInt = 1000
) -> str:
    """Donate gold to a nation or tribe. Only friendly (allied) recipients can receive — strangers are refused, same as for a human."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_donate_gold, target, amount)
    )


@mcp.tool()
async def order_donate_troops(
    ctx: Context, target: str = "", amount: StrictInt = 1000
) -> str:
    """Donate troops to a nation or tribe. Only friendly (allied) recipients can receive."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_donate_troops, target, amount)
    )


@mcp.tool()
async def order_move_warship(
    ctx: Context, unit_id: str = "", x: StrictInt = 0, y: StrictInt = 0
) -> str:
    """Retarget a warship to patrol tile (x, y). The id must be a live human warship; the engine validates the water component, same as a human patrol order."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_move_warship, unit_id, x, y)
    )


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
                "start_1v1_game",
                "start_solo_game",
                "get_overview",
                "end_decision",
                "order_attack",
                "order_cancel_attack",
                "order_boat_attack",
                "order_cancel_boat",
                "order_build",
                "order_upgrade_unit",
                "order_delete_unit",
                "order_alliance_request",
                "order_alliance_reject",
                "order_alliance_extend",
                "order_break_alliance",
                "order_embargo",
                "order_donate_gold",
                "order_donate_troops",
                "order_move_warship",
                "close_game",
            ]
        ),
    )
    mcp.run(transport="stdio")
