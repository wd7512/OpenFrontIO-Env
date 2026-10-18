"""1v1 RL sandbox tests: DuelEnv reset/step/observe plus the worker's
external-nation commands. Fast fixture (Britannia compact); Box-scale
fidelity is covered separately by the replay-verify path.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from openfrontbench.duel_env import (
    COMMIT,
    EXPAND,
    ME_KEYS,
    OBS_KEYS,
    OTHER_KEYS,
    RAID,
    DuelEnv,
)
from openfrontbench.engine import (
    BRITANNIA_MAP_DIR,
    EngineError,
    EngineWorker,
)


def _scripted_run(seed: str, actions: list[int]) -> tuple[int, str | None, list]:
    """Run one scripted episode to completion (actions cycle); return
    (final tick, winner, taped orders)."""
    with DuelEnv(seed) as env:
        env.reset()
        done = False
        obs = None
        step = 0
        while not done:
            obs, _, done, _ = env.step(actions[step % len(actions)])
            step += 1
        assert obs is not None
        record = env.save_record()
    return int(obs["tick"]), obs["winner"], record.get("externalOrders", [])


def test_obs_keys_stable() -> None:
    """The observation contract: top-level, me, and others key sets."""
    with DuelEnv("duel-env-keys") as env:
        obs = env.reset()
    assert OBS_KEYS == frozenset(obs.keys())
    assert ME_KEYS == frozenset(obs["me"].keys())
    assert len(obs["others"]) == 1
    assert OTHER_KEYS == frozenset(obs["others"][0].keys())
    assert obs["winner"] is None


def test_invalid_actions_rejected() -> None:
    """Out-of-range, negative, bool, and non-int actions fail closed."""
    with DuelEnv("duel-env-actions") as env:
        env.reset()
        for bad in (3, -1, True, "1", None, 1.0):
            with pytest.raises(ValueError):
                env.step(cast(Any, bad))


def test_step_after_done_raises() -> None:
    """Stepping a finished episode (tick cap) requires reset()."""
    with DuelEnv("duel-env-done", max_ticks=50) as env:
        env.reset()
        _, _, done, info = env.step(EXPAND)
        assert done
        assert info["terminal"] == -5000.0
        with pytest.raises(RuntimeError):
            env.step(EXPAND)


def test_scripted_episode_deterministic() -> None:
    """Same seed + same action script replays the same episode, including
    the taped fight orders."""
    actions = [EXPAND, RAID, EXPAND, COMMIT, EXPAND, RAID]
    first = _scripted_run("duel-env-det", list(actions))
    second = _scripted_run("duel-env-det", list(actions))
    assert first[0] == second[0]
    assert first[1] == second[1]
    assert first[2] == second[2]
    # Cycling [expand, raid, expand, commit, expand, raid] injects on every
    # non-expand step; every taped order carries nation/target/troops.
    assert len(first[2]) > 0
    for order in first[2]:
        assert order["nation"] == 0
        assert {"tick", "targetID", "targetName", "troops"} <= set(order)


def test_fight_orders_change_the_world() -> None:
    """Injected orders are real: a fighting script diverges from
    always-expand on the same seed."""
    calm = _scripted_run("duel-env-fight", [EXPAND])
    fight = _scripted_run("duel-env-fight", [RAID])
    assert calm[2] == []
    assert len(fight[2]) > 0
    # Same seed, different brains-in-action: trajectories must differ.
    assert (calm[0], calm[1]) != (fight[0], fight[1]) or calm[2] != fight[2]


def test_external_autopilot_matches_improved_hard() -> None:
    """No injected orders: external@1 == improved-hard@1 for the first 400
    ticks (same spawn draws, same autopilot rule, same hashes)."""

    def hashes(behaviors: list[str]) -> list:
        with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
            engine.start(
                nations=2,
                difficulty="hard",
                map_size="compact",
                spawn=None,
                tribes=0,
                game_id="duel-env-parity",
                nation_behaviors=behaviors,
            )
            tick = 0
            winner = None
            while winner is None and tick < 400:
                state = engine.advance(52)
                tick = state["tick"]
                winner = state.get("winner")
            record = engine.save_record()
        return [t["hash"] for t in record["turns"] if t.get("hash") is not None]

    assert hashes(["production", "external"]) == hashes(["production", "improved-hard"])


def test_nation_order_validation_fail_closed() -> None:
    """Production nations reject orders, self-targets and bad targets
    reject, negative troops reject — before anything is queued or taped."""
    with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
        engine.start(
            nations=2,
            difficulty="hard",
            map_size="compact",
            spawn=None,
            tribes=0,
            game_id="duel-env-valid",
            nation_behaviors=["external", "production"],
        )
        with pytest.raises(EngineError):
            engine.nation_order(1, "nation-1", 100.0)  # production nation
        with pytest.raises(EngineError):
            engine.nation_order(0, "nation-1", 100.0)  # self-target
        with pytest.raises(EngineError):
            engine.nation_order(0, "nation-9", 100.0)  # no such nation
        with pytest.raises(EngineError):
            engine.nation_order(0, "expand", 100.0)  # autopilot owns expansion
        with pytest.raises(EngineError):
            engine.nation_order(0, "nation-2", -5.0)  # negative troops
        with pytest.raises(EngineError):
            engine.nation_observe(7)  # out of range
        record = engine.save_record()
    assert record.get("externalOrders", []) == []


def test_close_is_idempotent() -> None:
    """Double close and observe-after-close fail safe, never hang."""
    env = DuelEnv("duel-env-close")
    env.reset()
    env.close()
    env.close()
    with pytest.raises(RuntimeError):
        env.observe()
