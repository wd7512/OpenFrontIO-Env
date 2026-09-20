"""Server-side game session: one real engine worker per server lifespan.

``GameSession`` owns the boundary between the MCP tool layer and the real
engine worker (``openfrontbench.engine.EngineWorker``). One worker is created
per server lifespan and reaped when the lifespan closes; all public entry
points are serialized through a lock because ``EngineWorker`` is strictly
sequential.

Tools only ever see the controlled projections built here — never engine
hashes, asset paths or internal ids.
"""

from __future__ import annotations

import logging
import math
import os
import threading
from typing import Any, Callable

from openfrontbench.engine import DIFFICULTIES, MAP_NAMES, MAPS, EngineWorker

log = logging.getLogger(__name__)

SMOKE_SCENARIO = "plains-human-smoke"
SMOKE_LABEL = "single-human-smoke"
MATCH_SCENARIO = "plains-1v1-nation"
MATCH_LABEL = "human-vs-nation"
SOLO_SCENARIO = "britannia-solo-nations"
SOLO_LABEL = "solo-vs-nations"
TRIBAL_LABEL = "solo-vs-tribes"
DECISION_TICKS = 50
MAX_TOOL_NATIONS = 100
MAX_TOOL_TRIBES = 500
# Production bound for build/upgrade amount (MAX_UPGRADE_AMOUNT in Game.ts).
MAX_TOOL_UPGRADE_AMOUNT = 50
# Human build menu, kebab-case for the tool surface (worker maps to UnitType).
BUILDABLE_UNITS = (
    "city",
    "defense-post",
    "sam-launcher",
    "missile-silo",
    "port",
    "factory",
    "atom-bomb",
    "hydrogen-bomb",
    "mirv",
    "warship",
)
# Per-map engine boot: plains keeps the fast fixture behavior; britannia
# plays production Compact (map4x, seeded random land spawn); world plays
# full-res like online Normal.
MAP_BOOT = {
    "plains": {"map_size": "full", "spawn": (50, 50)},
    "britannia": {"map_size": "compact", "spawn": None},
    "world": {"map_size": "full", "spawn": None},
    "europe": {"map_size": "full", "spawn": None},
}


class SessionError(RuntimeError):
    """Invalid lifecycle usage: calls before start, stale decisions, etc."""


class GameSession:
    """A single started game held server-side for the whole server lifespan."""

    def __init__(
        self, engine_factory: Callable[..., EngineWorker] = EngineWorker
    ) -> None:
        self._engine_factory = engine_factory
        self._lock = threading.RLock()
        self._engine: EngineWorker | None = None
        self._snapshot: dict[str, Any] | None = None
        self._decision = 0
        self._tick = 0
        self._closed = False
        self._scenario = SMOKE_SCENARIO
        self._label = SMOKE_LABEL

    def start(
        self,
        nations: int = 0,
        difficulty: str = "easy",
        map: str = "plains",
        tribes: int = 0,
        spawn: tuple[int, int] | list[int] | None = None,
        game_id: str | None = None,
        policy_path: str | None = None,
    ) -> dict[str, Any]:
        """Spawn the engine worker and boot the scenario.

        ``nations=0`` is the single-human smoke game; ``nations>=1`` adds
        that many production nation opponents (capped for tool play).
        ``map`` is a map NAME — ``"plains"`` (fast fixture), ``"britannia"``
        (production Compact board), ``"world"`` (full-res, like online
        Normal) or ``"europe"`` (solo default). Map sizes (``"full"`` /
        ``"compact"``) are chosen per map, never passed here. ``tribes``
        spawns that many neutral tribes (online solo default 400).
        ``spawn`` overrides the per-map boot tile with an explicit
        ``(x, y)`` pair (used by the code-evo evaluator's fixed-spawn
        registry); ``None`` keeps the boot default (fixed fixture tile on
        plains, seeded random land on real maps). The engine validates the
        tile — water or out-of-bounds spawns fail closed. ``game_id``
        overrides the legacy ``ENGINE01`` constant for every seeded RNG
        (pass one per spawn for distinct-but-reproducible worlds);
        ``None`` keeps the legacy constant. ``policy_path`` is the path
        to a bundled in-engine TS policy loaded by the worker at boot
        (``None`` for no policy); it is passed through to the engine.
        """
        with self._lock:
            self._require_open()
            if self._snapshot is not None:
                raise SessionError(
                    "game already started: start tools may be called once "
                    "per server lifecycle"
                )
            if (
                isinstance(nations, bool)
                or not isinstance(nations, int)
                or not 0 <= nations <= MAX_TOOL_NATIONS
            ):
                raise SessionError(
                    f"nations must be an integer in [0, {MAX_TOOL_NATIONS}]"
                )
            if not isinstance(difficulty, str) or difficulty not in DIFFICULTIES:
                raise SessionError(
                    f"difficulty must be one of {', '.join(DIFFICULTIES)}"
                )
            if not isinstance(map, str) or map not in MAPS:
                raise SessionError(
                    f"map must be one of {', '.join(MAP_NAMES)}, got {map!r}"
                )
            if (
                isinstance(tribes, bool)
                or not isinstance(tribes, int)
                or not 0 <= tribes <= MAX_TOOL_TRIBES
            ):
                raise SessionError(
                    f"tribes must be an integer in [0, {MAX_TOOL_TRIBES}]"
                )
            boot = MAP_BOOT[map]
            default_spawn = boot["spawn"]
            spawn_xy: tuple[int, int] | None = (
                (default_spawn[0], default_spawn[1])
                if isinstance(default_spawn, tuple)
                else None
            )
            if spawn is not None:
                spawn_xy = self._check_spawn(spawn)
            engine = self._engine_factory(map_dir=MAPS[map])
            engine.__enter__()
            try:
                snapshot = engine.start(
                    nations=nations,
                    difficulty=difficulty,
                    map_size=boot["map_size"],
                    spawn=spawn_xy,
                    tribes=tribes,
                    game_id=game_id,
                    policy_path=policy_path,
                )
            except BaseException:
                engine.close()
                raise
            self._engine = engine
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            self._decision = 0
            if tribes > 0:
                self._scenario = f"{map}-solo-tribes"
                self._label = TRIBAL_LABEL
            elif nations > 0:
                if map == "britannia":
                    self._scenario = SOLO_SCENARIO
                    self._label = SOLO_LABEL
                elif map == "plains":
                    self._scenario = MATCH_SCENARIO
                    self._label = MATCH_LABEL
                else:
                    self._scenario = f"{map}-ffa-nations"
                    self._label = MATCH_LABEL
            return self._project("started")

    def overview(self) -> dict[str, Any]:
        """Pure query: returns the current human state without ticking."""
        with self._lock:
            self._require_running()
            return self._project("running")

    def end_decision(self, expected: int | None = None) -> dict[str, Any]:
        """Advance exactly ``DECISION_TICKS`` sim ticks for one decision.

        ``expected`` is optional: when given it must equal the next decision
        integer (a stale value is rejected so out-of-order calls are caught);
        when omitted the session advances the next decision, which keeps an
        agent that lost its counter from looping on rejections. The reply
        carries a compact human snapshot so the tape samples tiles/troops
        every decision, not only on projection calls.
        """
        with self._lock:
            self._require_running()
            if expected is not None:
                if isinstance(expected, bool) or not isinstance(expected, int):
                    raise SessionError("decision must be an integer")
                next_expected = self._decision + 1
                if expected != next_expected:
                    raise SessionError(
                        f"stale decision: expected {next_expected}, got {expected} "
                        "(advance exactly one decision at a time)"
                    )
            assert self._engine is not None
            snapshot = self._engine.advance(DECISION_TICKS)
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            self._decision += 1
            self._capture_record()
            human = snapshot["human"]
            return {
                "decision": self._decision,
                "tick": self._tick,
                "in_spawn_phase": bool(snapshot["inSpawnPhase"]),
                "winner": snapshot.get("winner"),
                "human": {
                    "troops": human["troops"],
                    "gold": human["gold"],
                    "tiles": human["tiles"],
                },
            }

    def _capture_record(self) -> None:
        """Persist the replay tape alongside grid frames.

        Only when ``OPENFRONT_RECORD_DIR`` is set (live runner sets it to
        the run dir): the worker rewrites record.json itself via the
        metadata-only flush (the full tape never crosses the pipe);
        failures are swallowed — capture must never break a game.
        """
        if not os.environ.get("OPENFRONT_RECORD_DIR", ""):
            return
        try:
            assert self._engine is not None
            self._engine.flush_record()
        except Exception as exc:
            log.debug("record capture skipped: %s", exc)

    def _check_percent(self, percent: object) -> int:
        """Validate a slider percentage (1..100, the live client's control)."""
        if (
            isinstance(percent, bool)
            or not isinstance(percent, int)
            or not 1 <= percent <= 100
        ):
            raise SessionError(
                f"percent must be an integer in [1, 100], got {percent!r}"
            )
        return percent

    def _attack_troops(self, percent: int) -> float:
        """Convert a slider percent into troops exactly like the live client.

        ``ClientGameRunner`` sends ``attackRatio * player.troops()`` raw; the
        engine clamps to owner troops at execution (AttackExecution).
        """
        assert self._snapshot is not None
        return self._snapshot["human"]["troops"] * percent / 100.0

    def order_attack(self, target: object, percent: object = 20) -> dict[str, Any]:
        """Order the human to expand or attack, then project the result.

        ``target`` is ``"expand"`` (adjacent neutral land), ``"nation-N"`` or
        ``"tribe-N"``; ``percent`` is the attack slider (1..100 of current
        troops, default 20) — the harness computes the troop number the live
        client would send. Production rules (spawn immunity, shared border)
        decide whether the order lands; the next snapshot shows what
        happened (the order executes on the following tick).
        """
        with self._lock:
            self._require_running()
            if not isinstance(target, str) or target not in self._valid_targets():
                raise SessionError(
                    'target must be "expand" or one of '
                    f"{self._valid_targets()}, got {target!r}"
                )
            share = self._check_percent(percent)
            troops = self._attack_troops(share)
            assert self._engine is not None
            try:
                snapshot = self._engine.attack(target=target, troops=troops)
            except Exception as exc:
                raise SessionError(f"attack rejected by engine: {exc}") from exc
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            payload = self._project("attack-ordered")
            payload["order"] = {"percent": share, "troops": troops}
            return payload

    def run_policy_decision(self) -> dict[str, Any]:
        """Run one in-engine TS policy decision, then project the result.

        The worker executes the bundled policy against the live game and
        returns the post-order snapshot; bookkeeping mirrors
        :meth:`order_attack` without an order payload.
        """
        with self._lock:
            self._require_running()
            assert self._engine is not None
            snapshot = self._engine.decide()
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            return self._project("policy-decided")

    def order_cancel_attack(self, attack_id: object) -> dict[str, Any]:
        """Retreat a live outgoing attack by its id, then project.

        Rides the production cancel_attack intent (RetreatExecution); unknown
        ids are rejected before touching the engine.
        """
        with self._lock:
            self._require_running()
            assert self._snapshot is not None
            live_ids = [a["id"] for a in self._snapshot.get("attacks", [])]
            if not isinstance(attack_id, str) or attack_id not in live_ids:
                raise SessionError(
                    f"attack_id must be one of {live_ids}, got {attack_id!r}"
                )
            assert self._engine is not None
            try:
                snapshot = self._engine.cancel_attack(attack_id=attack_id)
            except Exception as exc:
                raise SessionError(f"cancel rejected by engine: {exc}") from exc
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            return self._project("cancel-ordered")

    def order_boat_attack(
        self, x: object, y: object, percent: object = 20
    ) -> dict[str, Any]:
        """Launch a boat attack at tile (``x``, ``y``) with a percent of troops.

        ``x``/``y`` come from ``get_overview`` ``boat_targets`` (the agent
        cannot see terrain); ``percent`` is the same attack slider the live
        client uses (1..100 of current troops, default 20). Rides the
        production boat intent (TransportShipExecution); bounds are checked
        here, the engine validates the tile itself.
        """
        with self._lock:
            self._require_running()
            assert self._snapshot is not None
            width = int(self._snapshot["width"])
            height = int(self._snapshot["height"])
            for label, value, maximum in (("x", x, width), ("y", y, height)):
                if (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or not 0 <= value < maximum
                ):
                    raise SessionError(
                        f"{label} must be an integer in [0, {maximum}), got {value!r}"
                    )
            share = self._check_percent(percent)
            troops = self._attack_troops(share)
            assert self._engine is not None
            try:
                snapshot = self._engine.boat_attack(x=x, y=y, troops=troops)
            except Exception as exc:
                raise SessionError(f"boat order rejected by engine: {exc}") from exc
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            payload = self._project("boat-ordered")
            payload["order"] = {"percent": share, "troops": troops}
            return payload

    def order_cancel_boat(self, unit_id: object) -> dict[str, Any]:
        """Recall a transport ship by its id, then project.

        Rides the production cancel_boat intent (BoatRetreatExecution);
        unknown ids are rejected before touching the engine.
        """
        with self._lock:
            self._require_running()
            assert self._snapshot is not None
            boat_ids = [b["id"] for b in self._snapshot.get("boats", [])]
            if not isinstance(unit_id, str) or unit_id not in boat_ids:
                raise SessionError(
                    f"unit_id must be one of {boat_ids}, got {unit_id!r}"
                )
            assert self._engine is not None
            try:
                snapshot = self._engine.cancel_boat(unit_id=unit_id)
            except Exception as exc:
                raise SessionError(f"boat cancel rejected by engine: {exc}") from exc
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            return self._project("boat-cancel-ordered")

    def _check_amount(self, amount: object) -> int:
        """Validate a production build/upgrade stack amount (1..50)."""
        if (
            isinstance(amount, bool)
            or not isinstance(amount, int)
            or not 1 <= amount <= MAX_TOOL_UPGRADE_AMOUNT
        ):
            raise SessionError(
                f"amount must be an integer in [1, {MAX_TOOL_UPGRADE_AMOUNT}], "
                f"got {amount!r}"
            )
        return amount

    def _check_spawn(self, spawn: object) -> tuple[int, int]:
        """Validate an explicit spawn override as an (x, y) integer pair."""
        if not isinstance(spawn, (tuple, list)) or len(spawn) != 2:
            raise SessionError(
                f"spawn must be an (x, y) integer pair or None, got {spawn!r}"
            )
        x_raw, y_raw = spawn[0], spawn[1]
        if isinstance(x_raw, bool) or not isinstance(x_raw, int):
            raise SessionError(
                f"spawn must be an (x, y) integer pair or None, got {spawn!r}"
            )
        if isinstance(y_raw, bool) or not isinstance(y_raw, int):
            raise SessionError(
                f"spawn must be an (x, y) integer pair or None, got {spawn!r}"
            )
        return (x_raw, y_raw)

    def _check_tile(self, label: str, value: object, maximum: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise SessionError(
                f"{label} must be an integer in [0, {maximum}), got {value!r}"
            )
        if not 0 <= value < maximum:
            raise SessionError(
                f"{label} must be an integer in [0, {maximum}), got {value!r}"
            )
        return value

    def order_build(
        self,
        unit: object,
        x: object,
        y: object,
        rocket_direction_up: object = None,
        amount: object = None,
    ) -> dict[str, Any]:
        """Order a build-menu unit at tile (``x``, ``y``), then project.

        ``unit`` is a kebab-case build-menu name (city, defense-post,
        sam-launcher, missile-silo, port, factory, atom-bomb, hydrogen-bomb,
        mirv, warship). ``rocket_direction_up`` is the live client's rocket
        direction toggle (atom-bomb/hydrogen-bomb); ``amount`` is the
        production stack amount for stackable nukes (1..50). Rides the
        production build_unit intent; the engine validates gold, costs and
        tiles — humans get no pre-flight guarantee either, so acceptance
        (not landing) is the contract here.
        """
        with self._lock:
            self._require_running()
            assert self._snapshot is not None
            if not isinstance(unit, str) or unit not in BUILDABLE_UNITS:
                raise SessionError(
                    f"unit must be one of {list(BUILDABLE_UNITS)}, got {unit!r}"
                )
            if rocket_direction_up is not None and not isinstance(
                rocket_direction_up, bool
            ):
                raise SessionError(
                    "rocket_direction_up must be a boolean, got "
                    f"{rocket_direction_up!r}"
                )
            stack = None if amount is None else self._check_amount(amount)
            width = int(self._snapshot["width"])
            height = int(self._snapshot["height"])
            tile_x = self._check_tile("x", x, width)
            tile_y = self._check_tile("y", y, height)
            assert self._engine is not None
            try:
                snapshot = self._engine.build_unit(
                    unit=unit,
                    x=tile_x,
                    y=tile_y,
                    rocket_direction_up=rocket_direction_up,
                    amount=stack,
                )
            except Exception as exc:
                raise SessionError(f"build rejected by engine: {exc}") from exc
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            return self._project("build-ordered")

    def _live_unit_ids(self) -> list[str]:
        assert self._snapshot is not None
        return [u["id"] for u in self._snapshot.get("units", [])]

    def order_upgrade_unit(
        self, unit_id: object, amount: object = None
    ) -> dict[str, Any]:
        """Upgrade a human unit by its id, then project.

        Rides the production upgrade_structure intent; unknown ids are
        rejected before touching the engine. ``amount`` is the production
        stack amount (1..50) the client sends for multi-level upgrades. Only
        some structures are upgradable in production (port, missile-silo,
        sam-launcher, city, factory) — the engine decides, same as a human
        upgrade button.
        """
        with self._lock:
            self._require_running()
            live_ids = self._live_unit_ids()
            if not isinstance(unit_id, str) or unit_id not in live_ids:
                raise SessionError(
                    f"unit_id must be one of {live_ids}, got {unit_id!r}"
                )
            stack = None if amount is None else self._check_amount(amount)
            assert self._engine is not None
            try:
                snapshot = self._engine.upgrade_unit(unit_id=unit_id, amount=stack)
            except Exception as exc:
                raise SessionError(f"upgrade rejected by engine: {exc}") from exc
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            return self._project("upgrade-ordered")

    def order_delete_unit(self, unit_id: object) -> dict[str, Any]:
        """Delete a human unit by its id, then project.

        Rides the production delete_unit intent; unknown ids are rejected
        before touching the engine. Removal follows a production grace
        period, so the unit stays listed briefly after the order.
        """
        with self._lock:
            self._require_running()
            live_ids = self._live_unit_ids()
            if not isinstance(unit_id, str) or unit_id not in live_ids:
                raise SessionError(
                    f"unit_id must be one of {live_ids}, got {unit_id!r}"
                )
            assert self._engine is not None
            try:
                snapshot = self._engine.delete_unit(unit_id=unit_id)
            except Exception as exc:
                raise SessionError(f"delete rejected by engine: {exc}") from exc
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            return self._project("delete-ordered")

    def _check_diplo_target(self, target: object) -> str:
        # Adapter labels only; the worker resolves to internal player ids and
        # validates bounds against live game state.
        assert self._snapshot is not None
        nations = [
            f"nation-{index + 1}"
            for index, _ in enumerate(self._snapshot.get("nations", []))
        ]
        tribes = [t["id"] for t in self._snapshot.get("tribe_list", [])]
        labels = nations + tribes
        if not isinstance(target, str) or target not in labels:
            raise SessionError(f"target must be one of {labels}, got {target!r}")
        return target

    def _check_donation(self, amount: object) -> float:
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not math.isfinite(amount)
            or not amount > 0
        ):
            raise SessionError(f"amount must be a positive number, got {amount!r}")
        return float(amount)

    def order_alliance_request(self, target: object) -> dict[str, Any]:
        """Request an alliance with a nation or tribe, then project.

        Rides the production allianceRequest intent; the recipient's AI
        answers on its own schedule (or never), same as for a human.
        """
        with self._lock:
            self._require_running()
            label = self._check_diplo_target(target)
            return self._diplo_order_inner(
                "alliance-requested", "alliance_request", label
            )

    def order_alliance_reject(self, requestor: object) -> dict[str, Any]:
        """Reject an incoming alliance request, then project.

        Only pending incoming requestors are answerable; anything else is
        rejected before touching the engine.
        """
        with self._lock:
            self._require_running()
            assert self._snapshot is not None
            incoming = self._snapshot.get("alliance_requests", {}).get("incoming", [])
            if not isinstance(requestor, str) or requestor not in incoming:
                raise SessionError(
                    f"requestor must be one of {incoming}, got {requestor!r}"
                )
            return self._diplo_order_inner(
                "alliance-rejected", "alliance_reject", requestor
            )

    def order_alliance_extend(self, target: object) -> dict[str, Any]:
        """Extend the alliance with a nation or tribe, then project."""
        with self._lock:
            self._require_running()
            label = self._check_diplo_target(target)
            return self._diplo_order_inner(
                "alliance-extended", "alliance_extend", label
            )

    def order_break_alliance(self, target: object) -> dict[str, Any]:
        """Break the alliance with a nation or tribe, then project."""
        with self._lock:
            self._require_running()
            label = self._check_diplo_target(target)
            return self._diplo_order_inner("alliance-broken", "break_alliance", label)

    def order_embargo(self, target: object, action: object) -> dict[str, Any]:
        """Start or stop an embargo on a nation or tribe, then project."""
        with self._lock:
            self._require_running()
            label = self._check_diplo_target(target)
            if action not in ("start", "stop"):
                raise SessionError(f'action must be "start" or "stop", got {action!r}')
            return self._diplo_order_inner("embargo-ordered", "embargo", label, action)

    def order_donate_gold(self, target: object, amount: object) -> dict[str, Any]:
        """Donate gold to a nation or tribe, then project.

        The engine only lets friendly (allied) players donate — strangers
        are refused silently, same as a human gift.
        """
        with self._lock:
            self._require_running()
            label = self._check_diplo_target(target)
            coins = self._check_donation(amount)
            return self._diplo_order_inner("gold-donated", "donate_gold", label, coins)

    def order_donate_troops(self, target: object, amount: object) -> dict[str, Any]:
        """Donate troops to a nation or tribe, then project (friendly-only)."""
        with self._lock:
            self._require_running()
            label = self._check_diplo_target(target)
            count = self._check_donation(amount)
            return self._diplo_order_inner(
                "troops-donated", "donate_troops", label, count
            )

    def _diplo_order_inner(
        self, status: str, method: str, *args: object
    ) -> dict[str, Any]:
        assert self._engine is not None
        call = getattr(self._engine, method)
        try:
            snapshot = call(*args)
        except Exception as exc:
            raise SessionError(f"order rejected by engine: {exc}") from exc
        self._snapshot = snapshot
        self._tick = int(snapshot["tick"])
        return self._project(status)

    def order_move_warship(
        self, unit_ids: object, x: object, y: object
    ) -> dict[str, Any]:
        """Retarget a fleet of warships to patrol tile (``x``, ``y``).

        Rides the production move_warship intent, which carries a non-empty
        ``unitIds`` array — the live client moves every selected warship in
        one order. Ids must be live human warships (from get_overview units)
        and the tile in bounds. The engine validates the water component —
        retargets only land on water in the warship's component, same as a
        human patrol order.
        """
        with self._lock:
            self._require_running()
            assert self._snapshot is not None
            warships = [
                u["id"]
                for u in self._snapshot.get("units", [])
                if u["type"] == "Warship"
            ]
            if (
                not isinstance(unit_ids, (list, tuple))
                or not unit_ids
                or any(not isinstance(unit_id, str) for unit_id in unit_ids)
            ):
                raise SessionError(
                    f"unit_ids must be a non-empty list of warship ids, "
                    f"got {unit_ids!r}"
                )
            unknown = [unit_id for unit_id in unit_ids if unit_id not in warships]
            if unknown:
                raise SessionError(
                    f"unit_ids must be live warships {warships}, got {unknown!r}"
                )
            width = int(self._snapshot["width"])
            height = int(self._snapshot["height"])
            tile_x = self._check_tile("x", x, width)
            tile_y = self._check_tile("y", y, height)
            return self._diplo_order_inner(
                "warship-moved", "move_warship", list(unit_ids), tile_x, tile_y
            )

    def _valid_targets(self) -> list[str]:
        assert self._snapshot is not None
        nations = [
            f"nation-{index + 1}"
            for index, _ in enumerate(self._snapshot.get("nations", []))
        ]
        tribes = [tribe["id"] for tribe in self._snapshot.get("tribe_list", [])]
        return ["expand"] + nations + tribes

    def close(self) -> dict[str, Any]:
        """Close the running game and reap its engine worker."""
        with self._lock:
            self._require_running()
            result = {
                "status": "closed",
                "decision": self._decision,
                "tick": self._tick,
            }
            self._shutdown_engine()
            self._closed = True
            return result

    def shutdown(self) -> None:
        """Reap any engine worker still alive (idempotent; lifespan teardown)."""
        with self._lock:
            self._shutdown_engine()

    def _require_open(self) -> None:
        if self._closed:
            raise SessionError("session is closed; start a new server lifecycle")

    def _require_running(self) -> None:
        self._require_open()
        if self._snapshot is None:
            raise SessionError("game not started: call start_smoke_game first")

    def _shutdown_engine(self) -> None:
        engine, self._engine = self._engine, None
        if engine is not None:
            engine.close()

    def _project(self, status: str) -> dict[str, Any]:
        assert self._snapshot is not None
        human = self._snapshot["human"]
        nations = [
            {
                "id": f"nation-{index + 1}",
                "name": nation["name"],
                "troops": nation["troops"],
                "gold": nation["gold"],
                "tiles": nation["tiles"],
                "alive": nation.get("alive", True),
                "immune": nation.get("immune", False),
                "borders_human": nation.get("borders_human", False),
                "incoming_troops": nation.get("incoming_troops", 0),
            }
            for index, nation in enumerate(self._snapshot.get("nations", []))
        ]
        attacks = [
            {
                "id": attack["id"],
                "target": attack["target"],
                "troops": attack["troops"],
                "retreating": attack.get("retreating", False),
            }
            for attack in self._snapshot.get("attacks", [])
        ]
        incoming_attacks = [
            {
                "attacker": attack.get("attacker"),
                "troops": attack.get("troops"),
                "retreating": attack.get("retreating", False),
            }
            for attack in self._snapshot.get("incoming_attacks", [])
            if isinstance(attack, dict)
        ]
        tribes_list = [
            {
                "id": tribe["id"],
                "name": tribe["name"],
                "troops": tribe["troops"],
                "tiles": tribe["tiles"],
                "alive": tribe.get("alive", True),
                "borders_human": tribe.get("borders_human", False),
                "incoming_troops": tribe.get("incoming_troops", 0),
            }
            # Only bordering tribes are listed: distant ones are unactionable
            # (attacks without shared border retreat silent), and 400 full
            # entries blow out the agent's tool-result window (~45KB), which
            # blinds it entirely. Totals stay in "tribes"; addressing uses
            # the full worker list, so any tribe-N remains orderable.
            for tribe in self._snapshot.get("tribe_list", [])
            if tribe.get("borders_human", False)
        ]
        boats = [
            {"id": boat["id"], "troops": boat["troops"]}
            for boat in self._snapshot.get("boats", [])
        ]
        boat_targets = [
            {
                "x": target.get("x"),
                "y": target.get("y"),
                "owner": target.get("owner"),
                "troops": target.get("troops"),
                "tiles": target.get("tiles"),
            }
            for target in self._snapshot.get("boat_targets", [])
            if isinstance(target, dict)
        ]
        units = [
            {
                "id": unit["id"],
                "type": unit["type"],
                "level": unit["level"],
                "x": unit["x"],
                "y": unit["y"],
                "troops": unit["troops"],
                "under_construction": unit.get("under_construction", False),
            }
            for unit in self._snapshot.get("units", [])
        ]
        alliances = [
            {"id": ally["id"], "name": ally["name"]}
            for ally in self._snapshot.get("alliances", [])
        ]
        requests = self._snapshot.get(
            "alliance_requests", {"incoming": [], "outgoing": []}
        )
        alliance_requests = {
            "incoming": list(requests.get("incoming", [])),
            "outgoing": list(requests.get("outgoing", [])),
        }
        embargoes = [
            {"id": ban["id"], "name": ban["name"]}
            for ban in self._snapshot.get("embargoes", [])
        ]
        return {
            "status": status,
            "scenario": self._scenario,
            "label": self._label,
            "tick": self._tick,
            "decision": self._decision,
            "next_decision": self._decision + 1,
            "in_spawn_phase": self._snapshot["inSpawnPhase"],
            "winner": self._snapshot.get("winner"),
            "tribes": self._snapshot.get("tribes", 0),
            "human": {
                "id": "human-1",
                "name": human["name"],
                "troops": human["troops"],
                "gold": human["gold"],
                "tiles": human["tiles"],
                "spawn": human["spawnTile"],
            },
            "nations": nations,
            "tribes_list": tribes_list,
            "boats": boats,
            "boat_targets": boat_targets,
            "units": units,
            "alliances": alliances,
            "alliance_requests": alliance_requests,
            "embargoes": embargoes,
            "attacks": attacks,
            "incoming_attacks": incoming_attacks,
        }
