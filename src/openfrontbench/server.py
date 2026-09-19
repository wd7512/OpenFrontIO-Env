"""Smoke + lifecycle tools over a real FastMCP stdio server.

Plain metadata functions stay importable; a FastMCP server on top registers
them under the same names. The lifecycle tools (start_smoke_game /
start_solo_game / get_overview / end_decision / orders / close_game) talk to
the real pinned engine through a per-lifespan ``GameSession``: one engine
worker per server lifespan, with all requests serialized there. Tools never
accept paths.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp.server.fastmcp import Context, FastMCP
from pydantic import StrictInt

from openfrontbench import pins as _pins
from openfrontbench.session import (
    MAX_TOOL_NATIONS,
    MAX_TOOL_TRIBES,
    GameSession,
    SessionError,
)


def _coerce_int(value: object, label: str) -> int | None:
    """Accept an int or an integer string; reject bools/floats/garbage.

    Small models sometimes type ``"69"`` where the schema wants an integer.
    StrictInt alone burns a tool call on that; numeric strings are safe to
    coerce (bools and fractional floats stay rejected).
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            raise SessionError(f"{label} must be an integer, got {value!r}") from None
    if isinstance(value, bool) or not isinstance(value, int):
        raise SessionError(f"{label} must be an integer, got {value!r}")
    return value


log = logging.getLogger(__name__)

PIN = f"{_pins.VENDOR_TAG} ({_pins.VENDOR_PIN})"
CORE_SCOPE = "src/core only; client/server untouched"


def get_pin() -> str:
    return f"upstream-openfrontio {PIN}; scope: {CORE_SCOPE}"


TOOLS = {
    "get_pin": get_pin,
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
    nations: StrictInt | str = 1,
    difficulty: str = "easy",
    map: str = "britannia",
) -> str:
    """Start a solo match: one human vs nation opponents (1-4 nations, easy/medium/hard/impossible) on britannia (production Compact board) or plains (fast fixture). map is a map name, never a size like "full"."""
    count = _coerce_int(nations, "nations")
    if count is None or not 1 <= count <= MAX_TOOL_NATIONS:
        raise SessionError(
            f"nations must be an integer in [1, {MAX_TOOL_NATIONS}] for a match"
        )
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).start, count, difficulty, map)
    )


@mcp.tool()
async def start_solo_game(
    ctx: Context,
    tribes: StrictInt | str = 400,
    nations: StrictInt | str = 52,
    difficulty: str = "easy",
    map: str = "europe",
) -> str:
    """Start the default solo format: one human, 400 neutral tribes, 52 nations on Europe FFA (easy/medium/hard/impossible). map is a map name (europe, world, britannia, plains), never a size like "full" — map size is fixed per map."""
    tribe_count = _coerce_int(tribes, "tribes")
    if tribe_count is None or not 0 <= tribe_count <= MAX_TOOL_TRIBES:
        raise SessionError(
            f"tribes must be an integer in [0, {MAX_TOOL_TRIBES}] for a solo game"
        )
    nation_count = _coerce_int(nations, "nations")
    if nation_count is None or not 0 <= nation_count <= MAX_TOOL_NATIONS:
        raise SessionError(
            f"nations must be an integer in [0, {MAX_TOOL_NATIONS}] for a solo game"
        )
    return json.dumps(
        await asyncio.to_thread(
            _session_of(ctx).start, nation_count, difficulty, map, tribe_count
        )
    )


@mcp.tool()
async def get_overview(ctx: Context) -> str:
    """Current controlled human state; a pure query that never advances the simulation."""
    return json.dumps(await asyncio.to_thread(_session_of(ctx).overview))


@mcp.tool()
async def end_decision(ctx: Context, decision: StrictInt | str | None = None) -> str:
    """Advance exactly 50 sim ticks for one decision and return a compact human snapshot (troops, gold, tiles, spawn phase, winner). Pass the next expected decision integer when you know it (stale values are rejected); omit it to just advance."""
    expected = _coerce_int(decision, "decision")
    return json.dumps(await asyncio.to_thread(_session_of(ctx).end_decision, expected))


@mcp.tool()
async def order_attack(ctx: Context, target: str, percent: StrictInt | str = 20) -> str:
    """Order the human to expand or attack with a percent of current troops — the same attack slider a human uses (1-100, default 20). Target "expand" (adjacent neutral land), "nation-N" or "tribe-N". Size the percent from get_overview (target troops/tiles, your troops): production combat math is what decides the exchange. Production rules (immunity, shared border) decide whether the order lands; the next snapshot shows the result."""
    share = _coerce_int(percent, "percent")
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_attack, target, share)
    )


@mcp.tool()
async def order_cancel_attack(ctx: Context, attack_id: str = "") -> str:
    """Retreat a live outgoing attack by its id (from get_overview attacks). Unknown ids are rejected."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_cancel_attack, attack_id)
    )


@mcp.tool()
async def order_boat_attack(
    ctx: Context,
    x: StrictInt | str,
    y: StrictInt | str,
    percent: StrictInt | str = 20,
) -> str:
    """Launch a boat attack at a landing tile (x, y) from get_overview boat_targets, with a percent of current troops — the same attack slider a human uses (1-100, default 20). Bounds are checked; the engine validates the tile (needs shore and water, same as a human order)."""
    tile_x = _coerce_int(x, "x")
    tile_y = _coerce_int(y, "y")
    share = _coerce_int(percent, "percent")
    return json.dumps(
        await asyncio.to_thread(
            _session_of(ctx).order_boat_attack, tile_x, tile_y, share
        )
    )


@mcp.tool()
async def order_cancel_boat(ctx: Context, unit_id: str = "") -> str:
    """Recall a transport ship by its id (from get_overview boats). Unknown ids are rejected."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_cancel_boat, unit_id)
    )


@mcp.tool()
async def order_build(
    ctx: Context,
    unit: str = "city",
    x: StrictInt | str = 0,
    y: StrictInt | str = 0,
    rocket_direction_up: bool | None = None,
    amount: StrictInt | str | None = None,
) -> str:
    """Order a build-menu unit (city, defense-post, sam-launcher, missile-silo, port, factory, atom-bomb, hydrogen-bomb, mirv, warship) at tile (x, y). rocket_direction_up is the client's rocket toggle (atom-bomb/hydrogen-bomb); amount is the stack amount (1-50) for stackable nukes. The engine validates gold, costs and tiles — acceptance, not landing, is the contract."""
    tile_x = _coerce_int(x, "x")
    tile_y = _coerce_int(y, "y")
    stack = _coerce_int(amount, "amount")
    return json.dumps(
        await asyncio.to_thread(
            _session_of(ctx).order_build,
            unit,
            tile_x,
            tile_y,
            rocket_direction_up,
            stack,
        )
    )


@mcp.tool()
async def order_upgrade_unit(
    ctx: Context, unit_id: str = "", amount: StrictInt | str | None = None
) -> str:
    """Upgrade a human unit by its id (from get_overview units); amount (1-50) upgrades several levels at once, as the client's multi-level button does. Unknown ids are rejected; only some structures are upgradable in production."""
    stack = _coerce_int(amount, "amount")
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_upgrade_unit, unit_id, stack)
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
    ctx: Context, target: str = "", amount: float = 1000
) -> str:
    """Donate gold to a nation or tribe (fractional amounts allowed, as the client's send-resource modal computes them). Only friendly (allied) recipients can receive — strangers are refused, same as for a human."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_donate_gold, target, amount)
    )


@mcp.tool()
async def order_donate_troops(
    ctx: Context, target: str = "", amount: float = 1000
) -> str:
    """Donate troops to a nation or tribe (fractional amounts allowed, as the client's send-resource modal computes them). Only friendly (allied) recipients can receive."""
    return json.dumps(
        await asyncio.to_thread(_session_of(ctx).order_donate_troops, target, amount)
    )


@mcp.tool()
async def order_move_warship(
    ctx: Context,
    unit_ids: list[str] | None = None,
    x: StrictInt | str = 0,
    y: StrictInt | str = 0,
) -> str:
    """Retarget a fleet of warships to patrol tile (x, y); unit_ids is a non-empty list of live human warship ids (the client moves every selected ship in one order). The engine validates the water component, same as a human patrol order."""
    tile_x = _coerce_int(x, "x")
    tile_y = _coerce_int(y, "y")
    return json.dumps(
        await asyncio.to_thread(
            _session_of(ctx).order_move_warship, unit_ids, tile_x, tile_y
        )
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
