"""Combat parity at engine level: tribe targets, cancel attack, boats.

Humans can attack any tribe directly, retreat attacks, and launch/cancel
boat attacks. The adapter must expose all four through the production
intent paths (AttackExecution / RetreatExecution / TransportShipExecution
/ BoatRetreatExecution via Executor.createExec).
"""

from __future__ import annotations

import pytest

from openfront_mcp.engine import EngineWorker, EngineError


def _plains() -> EngineWorker:
    from openfront_mcp.engine import PLAINS_MAP_DIR

    return EngineWorker(map_dir=PLAINS_MAP_DIR)


def test_attack_tribe_is_accepted_and_hurts() -> None:
    with _plains() as engine:
        started = engine.start(nations=0, spawn=(50, 50), tribes=5)
        assert started["tribes"] == 5
        first = started["tribe_list"][0]
        assert first["id"] == "tribe-1"

        # Production rule (same as nations): attacks with no shared border
        # retreat silent, so expand to contact first. Deterministic.
        for _ in range(10):
            engine.attack("expand", 20000)
            engine.advance(50)
        contact = engine.advance(1)
        tiles_before = contact["tribe_list"][0]["tiles"]
        assert contact["tribe_list"][0]["borders_human"] is True

        engine.attack("tribe-1", 20000)
        # Production double-buffer: the AttackExecution materialises after
        # ticks run, same as a human order.
        ordered = engine.advance(5)
        targets = [a["target"] for a in ordered["attacks"]]
        assert first["name"] in targets

        after = engine.advance(200)
        tribes = {t["id"]: t for t in after["tribe_list"]}
        assert (
            tribes["tribe-1"]["tiles"] < tiles_before
            or tribes["tribe-1"]["alive"] is False
        )


def test_attack_unknown_tribe_rejected() -> None:
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=5)
        with pytest.raises(EngineError):
            engine.attack("tribe-999", 5000)


def test_cancel_attack_retreats() -> None:
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=0)
        engine.attack("expand", 5000)
        live = engine.advance(2)
        assert len(live["attacks"]) == 1
        attack_id = live["attacks"][0]["id"]

        engine.cancel_attack(attack_id)
        cancelled = engine.advance(2)
        states = {a["id"]: a for a in cancelled["attacks"]}
        assert states[attack_id]["retreating"] is True


def test_cancel_unknown_attack_rejected() -> None:
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=0)
        with pytest.raises(EngineError):
            engine.cancel_attack("no-such-attack")


def _britannia() -> EngineWorker:
    from openfront_mcp.engine import BRITANNIA_MAP_DIR

    return EngineWorker(map_dir=BRITANNIA_MAP_DIR)


def _grow_to_shore(engine: EngineWorker) -> None:
    # Seeded spawn is inland; repeated expand orders grow the territory to
    # the shore so a boat has somewhere to launch from. Deterministic.
    for _ in range(20):
        engine.attack("expand", 100000)
        engine.advance(100)


def test_boat_attack_launches_transport() -> None:
    with _britannia() as engine:
        engine.start(
            nations=0, difficulty="easy", map_size="compact", spawn=None, tribes=0
        )
        _grow_to_shore(engine)
        engine.boat_attack(400, 1041, 5000)
        sailed = engine.advance(5)
        assert len(sailed["boats"]) == 1
        assert sailed["boats"][0]["troops"] == 5000


def test_boat_attack_bad_coords_rejected() -> None:
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=0)
        with pytest.raises(EngineError):
            engine.boat_attack(-1, -1, 5000)


def test_cancel_boat_is_accepted() -> None:
    with _britannia() as engine:
        engine.start(
            nations=0, difficulty="easy", map_size="compact", spawn=None, tribes=0
        )
        _grow_to_shore(engine)
        engine.boat_attack(400, 1041, 5000)
        sailed = engine.advance(5)
        unit_id = sailed["boats"][0]["id"]

        # The recall order rides the production cancel_boat intent; the boat
        # sails home over game time, so right after the order it is still
        # tracked (humans see the same).
        recalled = engine.cancel_boat(unit_id)
        assert [b["id"] for b in recalled["boats"]] == [unit_id]


def test_cancel_unknown_boat_rejected() -> None:
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=0)
        with pytest.raises(EngineError):
            engine.cancel_boat("99999")
