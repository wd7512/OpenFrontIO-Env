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

import threading
from typing import Any, Callable

from openfront_mcp.engine import DIFFICULTIES, EngineWorker

SMOKE_SCENARIO = "plains-human-smoke"
SMOKE_LABEL = "single-human-smoke"
MATCH_SCENARIO = "plains-1v1-nation"
MATCH_LABEL = "human-vs-nation"
DECISION_TICKS = 50
MAX_TOOL_NATIONS = 4


class SessionError(RuntimeError):
    """Invalid lifecycle usage: calls before start, stale decisions, etc."""


class GameSession:
    """A single started game held server-side for the whole server lifespan."""

    def __init__(
        self, engine_factory: Callable[[], EngineWorker] = EngineWorker
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

    def start(self, nations: int = 0, difficulty: str = "easy") -> dict[str, Any]:
        """Spawn the engine worker and boot the scenario.

        ``nations=0`` is the single-human smoke game; ``nations>=1`` adds
        that many production nation opponents (capped for tool play).
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
            engine = self._engine_factory()
            engine.__enter__()
            try:
                snapshot = engine.start(nations=nations, difficulty=difficulty)
            except BaseException:
                engine.close()
                raise
            self._engine = engine
            self._snapshot = snapshot
            self._tick = int(snapshot["tick"])
            self._decision = 0
            if nations > 0:
                self._scenario = MATCH_SCENARIO
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
            return {"decision": self._decision, "tick": self._tick}

    def order_attack(self, target: object, troops: object) -> dict[str, Any]:
        """Order the human to expand or attack, then project the result.

        ``target`` is ``"expand"`` (adjacent neutral land) or ``"nation-N"``;
        ``troops`` is a positive integer. Bad values are rejected before
        touching the engine; production rules (spawn immunity, shared
        border) decide whether the order lands — the projection reports
        what actually happened.
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

    def _valid_targets(self) -> list[str]:
        assert self._snapshot is not None
        return ["expand"] + [
            f"nation-{index + 1}"
            for index, _ in enumerate(self._snapshot.get("nations", []))
        ]

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
            }
            for index, nation in enumerate(self._snapshot.get("nations", []))
        ]
        attacks = [
            {
                "target": attack["target"],
                "troops": attack["troops"],
                "retreating": attack.get("retreating", False),
            }
            for attack in self._snapshot.get("attacks", [])
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
            "human": {
                "id": "human-1",
                "name": human["name"],
                "troops": human["troops"],
                "gold": human["gold"],
                "tiles": human["tiles"],
                "spawn": human["spawnTile"],
            },
            "nations": nations,
            "attacks": attacks,
        }
