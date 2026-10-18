"""1v1 RL sandbox: one externally-driven nation vs a production nation.

Research-sandbox scope (v0): the agent owns a single nation whose body is
the proven Improved-Hard expansion autopilot — the agent only learns the
missing skill, fighting. Discrete actions at a fixed cadence, a small
vector observation, tiles-delta + terminal reward. Every episode tapes a
standard record (plus taped fight orders), so any training rollout stays
auditable through the existing replay-verify path.

Gymnasium-shaped but duck-typed: reset/step/observe/close, no new
dependencies. Deterministic: same seed + same action script replays the
same episode (pinned by tests/test_duel_env.py).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from openfrontbench.engine import BRITANNIA_MAP_DIR, EngineWorker

logger = logging.getLogger(__name__)

# Discrete actions. expand = autopilot only (no injected order); raid and
# commit queue one fight order at the enemy with a share of current troops.
EXPAND = 0
RAID = 1
COMMIT = 2
ACTIONS = (EXPAND, RAID, COMMIT)

RAID_SHARE = 0.15
COMMIT_SHARE = 0.40

STEP_TICKS = 52
MAX_TICKS = 300000

REWARD_SCALE = 1000.0
WIN_BONUS = 5000.0
LOSS_PENALTY = -5000.0

OBS_KEYS = frozenset({"tick", "inSpawnPhase", "winner", "me", "others"})
ME_KEYS = frozenset(
    {
        "name",
        "tiles",
        "troops",
        "maxTroops",
        "alive",
        "incomingTroops",
        "outgoingAttacks",
    }
)
OTHER_KEYS = frozenset(
    {"name", "tiles", "troops", "alive", "bordersMe", "incomingTroops"}
)


class DuelEnv:
    """One agent nation vs one production nation, idle human third party."""

    def __init__(
        self,
        seed: str,
        *,
        agent_index: int = 0,
        step_ticks: int = STEP_TICKS,
        max_ticks: int = MAX_TICKS,
        map_dir: str | Path = BRITANNIA_MAP_DIR,
        map_size: str = "compact",
        spawn: tuple[int, int] | list[int] | None = None,
        record_dir: str | Path | None = None,
    ) -> None:
        if not isinstance(seed, str) or not seed:
            raise ValueError(f"seed must be a non-empty string, got {seed!r}")
        if (
            isinstance(agent_index, bool)
            or not isinstance(agent_index, int)
            or agent_index not in (0, 1)
        ):
            raise ValueError(f"agent_index must be 0 or 1 (1v1), got {agent_index!r}")
        if (
            isinstance(step_ticks, bool)
            or not isinstance(step_ticks, int)
            or step_ticks <= 0
        ):
            raise ValueError(f"step_ticks must be a positive int, got {step_ticks!r}")
        self.seed = seed
        self.agent_index = agent_index
        self.step_ticks = step_ticks
        self.max_ticks = max_ticks
        self.map_dir = map_dir
        self.map_size = map_size
        self.spawn = spawn
        self.record_dir = Path(record_dir) if record_dir is not None else None
        self._engine: EngineWorker | None = None
        self._prev_tiles = 0
        self._done = True
        self._record_env: str | None = None

    def __enter__(self) -> DuelEnv:
        return self

    def __exit__(self, *_exc: object) -> bool:
        self.close()
        return False

    def reset(self) -> dict[str, Any]:
        """Boot a fresh duel world; return the initial observation."""
        self.close()
        behaviors = ["production", "production"]
        behaviors[self.agent_index] = "external"
        if self.record_dir is not None:
            self.record_dir.mkdir(parents=True, exist_ok=True)
            self._record_env = os.environ.get("OPENFRONT_RECORD_DIR")
            os.environ["OPENFRONT_RECORD_DIR"] = str(self.record_dir)
        engine = EngineWorker(map_dir=self.map_dir)
        engine.__enter__()
        try:
            engine.start(
                nations=2,
                difficulty="hard",
                map_size=self.map_size,
                spawn=self.spawn,
                tribes=0,
                game_id=self.seed,
                nation_behaviors=behaviors,
            )
        except BaseException:
            engine.close()
            self._restore_record_env()
            raise
        self._engine = engine
        obs = self.observe()
        self._prev_tiles = int(obs["me"]["tiles"])
        self._done = False
        return obs

    def step(self, action: int) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        """Run one decision: inject the fight order (if any), advance the
        sim, return (obs, reward, done, info)."""
        if self._done or self._engine is None:
            raise RuntimeError("episode is done (or never started); call reset()")
        if (
            isinstance(action, bool)
            or not isinstance(action, int)
            or action not in ACTIONS
        ):
            raise ValueError(f"action must be one of {ACTIONS}, got {action!r}")
        engine = self._engine
        obs = self.observe()
        me = obs["me"]
        if action != EXPAND and bool(me["alive"]):
            target = self._pick_target(obs["others"])
            if target is not None:
                share = RAID_SHARE if action == RAID else COMMIT_SHARE
                troops = float(me["troops"]) * share
                engine.nation_order(self.agent_index, target, troops)
        engine.advance(self.step_ticks)
        obs = self.observe()
        tiles = int(obs["me"]["tiles"])
        tiles_delta = tiles - self._prev_tiles
        reward = tiles_delta / REWARD_SCALE
        self._prev_tiles = tiles
        winner = obs["winner"]
        done = winner is not None or int(obs["tick"]) >= self.max_ticks
        terminal = 0.0
        if done:
            if winner == me["name"]:
                terminal = WIN_BONUS
            else:
                terminal = LOSS_PENALTY
            reward += terminal
            self._done = True
        info = {
            "tick": obs["tick"],
            "winner": winner,
            "tiles": tiles,
            "tiles_delta": tiles_delta,
            "terminal": terminal,
            "action": action,
        }
        return obs, reward, done, info

    def observe(self) -> dict[str, Any]:
        """Read-only observation for the agent nation (no game mutation)."""
        if self._engine is None:
            raise RuntimeError("env is not running; call reset()")
        return self._engine.nation_observe(self.agent_index)

    def save_record(self) -> dict[str, Any]:
        """Return the episode tape (record + taped fight orders)."""
        if self._engine is None:
            raise RuntimeError("env is not running; call reset()")
        return self._engine.save_record()

    def close(self) -> None:
        """Reap the worker; never raises on teardown."""
        engine, self._engine = self._engine, None
        if engine is not None:
            engine.close()
        self._restore_record_env()
        self._done = True

    def _restore_record_env(self) -> None:
        if self.record_dir is None:
            return
        if self._record_env is None:
            os.environ.pop("OPENFRONT_RECORD_DIR", None)
        else:
            os.environ["OPENFRONT_RECORD_DIR"] = self._record_env
        self._record_env = None

    def _pick_target(self, others: list[Any]) -> str | None:
        """v0: the first living other nation (1v1 — exactly one enemy)."""
        for index, other in enumerate(others):
            if bool(other["alive"]):
                enemy_index = index if index < self.agent_index else index + 1
                return f"nation-{enemy_index + 1}"
        return None
