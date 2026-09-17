"""Warship maneuver parity at engine level: move/patrol orders.

Humans retarget warships to new patrol tiles. The order rides the
production move_warship intent (MoveWarshipExecution) via
Executor.createExec. Warship positions are already in the units projection.
"""

from __future__ import annotations

import pytest

from openfront_mcp.engine import EngineWorker, EngineError


def _britannia() -> EngineWorker:
    from openfront_mcp.engine import BRITANNIA_MAP_DIR

    return EngineWorker(map_dir=BRITANNIA_MAP_DIR)


def _warship(engine: EngineWorker) -> dict:
    # Full production chain, same as a human: expand to shore, earn 600k,
    # finish a port, then float a warship. Seeded and deterministic.
    engine.start(nations=0, difficulty="easy", map_size="compact", spawn=None, tribes=0)
    for _ in range(20):
        engine.attack("expand", 100000)
        engine.advance(100)
    for _ in range(30):
        funded = engine.advance(200)
        if int(funded["human"]["gold"]) >= 600000:
            break
    engine.build_unit("port", 540, 860)
    engine.advance(60)
    engine.build_unit("warship", 500, 880)
    sailed = engine.advance(10)
    ship = next(u for u in sailed["units"] if u["type"] == "Warship")
    return ship


def test_move_warship_sails_to_patrol() -> None:
    with _britannia() as engine:
        ship = _warship(engine)
        # Retargets only land once the warship is on water in the same
        # component (production rule): let it sail out first. The no-order
        # drift path ends far from the target, so convergence proves landing.
        engine.advance(400)
        engine.move_warship(ship["id"], 700, 1000)
        moved = engine.advance(300)
        now = next(u for u in moved["units"] if u["id"] == ship["id"])
        dist = abs(now["x"] - 700) + abs(now["y"] - 1000)
        assert dist < 100


def test_move_warship_bad_unit_rejected() -> None:
    with _britannia() as engine:
        _warship(engine)
        with pytest.raises(EngineError):
            engine.move_warship("99999", 700, 1000)


def test_move_warship_non_warship_rejected() -> None:
    with _britannia() as engine:
        _warship(engine)
        # The port exists but is not a warship: humans cannot patrol it.
        port = next(u for u in engine.advance(1)["units"] if u["type"] == "Port")
        with pytest.raises(EngineError):
            engine.move_warship(port["id"], 700, 1000)


def test_move_warship_bad_coords_rejected() -> None:
    with _britannia() as engine:
        ship = _warship(engine)
        with pytest.raises(EngineError):
            engine.move_warship(ship["id"], -1, 1000)
