"""Server-side game session: one real engine worker per server lifespan.

``GameSession`` owns the boundary between the MCP tool layer and the real
engine worker (``openfront_mcp.engine.EngineWorker``). One worker is created
per server lifespan and reaped when the lifespan closes; all public entry
points are serialized through a lock because ``EngineWorker`` is strictly
sequential.

Tools only ever see the controlled projections built here — never engine
hashes, asset paths or internal ids.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Callable

from openfront_mcp.engine import DIFFICULTIES, MAP_NAMES, MAPS, EngineWorker

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
    ) -> dict[str, Any]:
        """Spawn the engine worker and boot the scenario.

        ``nations=0`` is the single-human smoke game; ``nations>=1`` adds
        that many production nation opponents (capped for tool play).
        ``map`` is ``"plains"`` (fast fixture), ``"britannia"`` (production
        Compact board) or ``"world"`` (full-res, like online Normal).
        ``tribes`` spawns that many neutral tribes (online solo default 400).
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
            engine = self._engine_factory(map_dir=MAPS[map])
            engine.__enter__()
            try:
                snapshot = engine.start(
                    nations=nations,
                    difficulty=difficulty,
                    map_size=boot["map_size"],
                    spawn=boot["spawn"],
                    tribes=tribes,
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

    def end_decision(self, expected: int) -> dict[str, Any]:
        """Advance exactly ``DECISION_TICKS`` sim ticks for one decision.

        ``expected`` must equal the next decision integer; anything else is a
        stale or out-of-order request and is rejected.
        """
        with self._lock:
            self._require_running()
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
            self._capture_grid()
            self._capture_record()
            return {"decision": self._decision, "tick": self._tick}

    def _capture_grid(self) -> None:
        """Append one ownership-grid frame for timelapse rendering.

        Only when ``OPENFRONT_GRID_DIR`` names an existing directory (set by
        the live runner): one JSON line per decision, never surfaced to the
        agent. Failures are swallowed — capture must never break a game.
        """
        grid_dir = os.environ.get("OPENFRONT_GRID_DIR", "")
        if not grid_dir:
            return
        try:
            assert self._engine is not None
            frame = self._engine.grid()
            frame["decision"] = self._decision
            path = os.path.join(grid_dir, "grids.jsonl")
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(frame) + "\n")
        except Exception:
            pass

    def _capture_record(self) -> None:
        """Persist the replay tape alongside grid frames.

        Only when ``OPENFRONT_RECORD_DIR`` is set (live runner sets it to
        the run dir): the worker rewrites record.json itself; failures are
        swallowed — capture must never break a game.
        """
        if not os.environ.get("OPENFRONT_RECORD_DIR", ""):
            return
        try:
            assert self._engine is not None
            self._engine.save_record()
        except Exception:
            pass

    def order_attack(self, target: object, troops: object) -> dict[str, Any]:
        """Order the human to expand or attack, then project the result.

        ``target`` is ``"expand"`` (adjacent neutral land), ``"nation-N"`` or
        ``"tribe-N"``; ``troops`` is a positive integer. Bad values are
        rejected before touching the engine; production rules (spawn
        immunity, shared border) decide whether the order lands — the
        projection reports what actually happened.
        """
        with self._lock:
            self._require_running()
            if not isinstance(target, str) or target not in self._valid_targets():
                raise SessionError(
                    'target must be "expand" or one of '
                    f"{self._valid_targets()}, got {target!r}"
                )
            if isinstance(troops, bool) or not isinstance(troops, int) or troops <= 0:
                raise SessionError(f"troops must be a positive integer, got {troops!r}")
            assert self._engine is not None
            try:
                snapshot = self._engine.attack(target=target, troops=troops)
            except Exception as exc:
                raise SessionError(f"attack rejected by engine: {exc}") from exc
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            return self._project("attack-ordered")

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

    def order_boat_attack(self, x: object, y: object, troops: object) -> dict[str, Any]:
        """Launch a boat attack at tile (``x``, ``y``) with ``troops``.

        Rides the production boat intent (TransportShipExecution); integer
        bounds are checked here, the engine validates the tile itself.
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
            if isinstance(troops, bool) or not isinstance(troops, int) or troops <= 0:
                raise SessionError(f"troops must be a positive integer, got {troops!r}")
            assert self._engine is not None
            try:
                snapshot = self._engine.boat_attack(x=x, y=y, troops=troops)
            except Exception as exc:
                raise SessionError(f"boat order rejected by engine: {exc}") from exc
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            return self._project("boat-ordered")

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

    def order_build(self, unit: object, x: object, y: object) -> dict[str, Any]:
        """Order a build-menu unit at tile (``x``, ``y``), then project.

        ``unit`` is a kebab-case build-menu name (city, defense-post,
        sam-launcher, missile-silo, port, factory, atom-bomb, hydrogen-bomb,
        mirv, warship). Rides the production build_unit intent; the engine
        validates gold, costs and tiles — humans get no pre-flight guarantee
        either, so acceptance (not landing) is the contract here.
        """
        with self._lock:
            self._require_running()
            assert self._snapshot is not None
            if not isinstance(unit, str) or unit not in BUILDABLE_UNITS:
                raise SessionError(
                    f"unit must be one of {list(BUILDABLE_UNITS)}, got {unit!r}"
                )
            width = int(self._snapshot["width"])
            height = int(self._snapshot["height"])
            tile_x = self._check_tile("x", x, width)
            tile_y = self._check_tile("y", y, height)
            assert self._engine is not None
            try:
                snapshot = self._engine.build_unit(unit=unit, x=tile_x, y=tile_y)
            except Exception as exc:
                raise SessionError(f"build rejected by engine: {exc}") from exc
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            return self._project("build-ordered")

    def _live_unit_ids(self) -> list[str]:
        assert self._snapshot is not None
        return [u["id"] for u in self._snapshot.get("units", [])]

    def order_upgrade_unit(self, unit_id: object) -> dict[str, Any]:
        """Upgrade a human unit by its id, then project.

        Rides the production upgrade_structure intent; unknown ids are
        rejected before touching the engine. Only some structures are
        upgradable in production (port, missile-silo, sam-launcher, city,
        factory) — the engine decides, same as a human upgrade button.
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
                snapshot = self._engine.upgrade_unit(unit_id=unit_id)
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

    def _check_donation(self, amount: object) -> int:
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise SessionError(f"amount must be a positive integer, got {amount!r}")
        return amount

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
        self, unit_id: object, x: object, y: object
    ) -> dict[str, Any]:
        """Retarget a warship to patrol tile (``x``, ``y``), then project.

        Rides the production move_warship intent; the id must be a live
        human warship (from get_overview units) and the tile in bounds. The
        engine validates the water component — retargets only land on water
        in the warship's component, same as a human patrol order.
        """
        with self._lock:
            self._require_running()
            assert self._snapshot is not None
            warships = [
                u["id"]
                for u in self._snapshot.get("units", [])
                if u["type"] == "Warship"
            ]
            if not isinstance(unit_id, str) or unit_id not in warships:
                raise SessionError(
                    f"unit_id must be one of {warships}, got {unit_id!r}"
                )
            width = int(self._snapshot["width"])
            height = int(self._snapshot["height"])
            tile_x = self._check_tile("x", x, width)
            tile_y = self._check_tile("y", y, height)
            return self._diplo_order_inner(
                "warship-moved", "move_warship", unit_id, tile_x, tile_y
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
        tribes_list = [
            {
                "id": tribe["id"],
                "name": tribe["name"],
                "troops": tribe["troops"],
                "tiles": tribe["tiles"],
                "alive": tribe.get("alive", True),
                "borders_human": tribe.get("borders_human", False),
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
            "units": units,
            "alliances": alliances,
            "alliance_requests": alliance_requests,
            "embargoes": embargoes,
            "attacks": attacks,
        }
