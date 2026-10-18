"""Tribe-farming phase tests: external nations can order tribe attacks,
and nation_observe exposes the tribe roster plus the tribe-tribe adjacency
graph for peel-order targeting. Fast fixture (Britannia compact, 5 tribes).
"""

from __future__ import annotations

from typing import Any

import pytest

from openfrontbench.duel_env import TRIBE_KEYS, DuelEnv
from openfrontbench.engine import (
    BRITANNIA_MAP_DIR,
    EngineError,
    EngineWorker,
)


def _start_farm(game_id: str) -> EngineWorker:
    engine = EngineWorker(map_dir=BRITANNIA_MAP_DIR)
    engine.__enter__()
    try:
        engine.start(
            nations=1,
            difficulty="hard",
            map_size="compact",
            spawn=None,
            tribes=5,
            game_id=game_id,
            nation_behaviors=["external"],
        )
    except BaseException:
        engine.close()
        raise
    return engine


def _bordering_tribe(engine: EngineWorker) -> str | None:
    """First roster label bordering nation 0 (advances until contact)."""
    for _ in range(30):
        obs = engine.nation_observe(0)
        for tribe in obs["tribes"]:
            if tribe["bordersMe"] and tribe["alive"]:
                return str(tribe["id"])
        engine.advance(52)
    return None


def test_tribe_order_accepted_and_taped() -> None:
    """nation_order takes tribe-N labels; the tape records targetID/Name."""
    engine = _start_farm("farm-tape")
    try:
        obs = engine.nation_observe(0)
        assert [t["id"] for t in obs["tribes"]] == [f"tribe-{n}" for n in range(1, 6)]
        wanted = obs["tribes"][0]["name"]
        engine.nation_order(0, "tribe-1", 5000.0)
        record = engine.save_record()
    finally:
        engine.close()
    orders = record.get("externalOrders", [])
    assert len(orders) == 1
    assert orders[0]["nation"] == 0
    assert orders[0]["targetName"] == wanted
    assert isinstance(orders[0]["targetID"], str) and orders[0]["targetID"]


def test_tribe_order_validation_fail_closed() -> None:
    """Unknown tribes, expand, bad troops, and production nations reject —
    before anything is queued or taped."""
    engine = _start_farm("farm-valid")
    try:
        with pytest.raises(EngineError):
            engine.nation_order(0, "tribe-999", 100.0)  # no such tribe
        with pytest.raises(EngineError):
            engine.nation_order(0, "tribe-0", 100.0)  # 1-based labels
        with pytest.raises(EngineError):
            engine.nation_order(0, "expand", 100.0)  # autopilot owns expansion
        with pytest.raises(EngineError):
            engine.nation_order(0, "nation-9", 100.0)  # no such nation
        with pytest.raises(EngineError):
            engine.nation_order(0, "tribe-1", -5.0)  # negative troops
        with pytest.raises(EngineError):
            engine.nation_order(5, "tribe-1", 100.0)  # out of range
        record = engine.save_record()
    finally:
        engine.close()
    assert record.get("externalOrders", []) == []


def test_observe_tribes_and_graph_contract() -> None:
    """Roster keys stable, graph keys match the roster, edges symmetric."""
    engine = _start_farm("farm-graph")
    try:
        engine.advance(52 * 4)
        obs = engine.nation_observe(0)
    finally:
        engine.close()
    assert TRIBE_KEYS == frozenset(obs["tribes"][0].keys())
    labels = [t["id"] for t in obs["tribes"]]
    assert set(obs["tribeGraph"].keys()) == set(labels)
    for source, targets in obs["tribeGraph"].items():
        assert targets == sorted(targets)
        for target in targets:
            assert target in obs["tribeGraph"]
            assert source in obs["tribeGraph"][target]  # symmetric
    for tribe in obs["tribes"]:
        assert isinstance(tribe["enclosed"], bool)
        if tribe["enclosed"]:
            # Enclosure implies contact (flag is only computed on contact).
            assert tribe["bordersMe"] and tribe["alive"]


def test_observe_tribes_deterministic() -> None:
    """Same seed replays the same roster and graph."""
    first: dict[str, Any]
    second: dict[str, Any]
    engine = _start_farm("farm-det")
    try:
        engine.advance(52 * 4)
        first = engine.nation_observe(0)
    finally:
        engine.close()
    engine = _start_farm("farm-det")
    try:
        engine.advance(52 * 4)
        second = engine.nation_observe(0)
    finally:
        engine.close()
    assert first["tribes"] == second["tribes"]
    assert first["tribeGraph"] == second["tribeGraph"]


def test_tribe_orders_change_the_world() -> None:
    """Attacking a bordering tribe takes its land (or kills it)."""
    engine = _start_farm("farm-fight")
    try:
        target = _bordering_tribe(engine)
        assert target is not None
        before = {
            t["id"]: (t["tiles"], t["alive"])
            for t in engine.nation_observe(0)["tribes"]
        }
        for _ in range(6):
            me = engine.nation_observe(0)["me"]
            engine.nation_order(0, target, float(me["troops"]) * 0.30)
            engine.advance(52)
        after = {
            t["id"]: (t["tiles"], t["alive"])
            for t in engine.nation_observe(0)["tribes"]
        }
    finally:
        engine.close()
    assert after[target][0] < before[target][0] or not after[target][1]


def test_duel_env_obs_carries_empty_tribe_fields() -> None:
    """DuelEnv (tribes=0) exposes the same keys with empty tribe data."""
    with DuelEnv("farm-duel-keys") as env:
        obs = env.reset()
    assert obs["tribes"] == []
    assert obs["tribeGraph"] == {}
