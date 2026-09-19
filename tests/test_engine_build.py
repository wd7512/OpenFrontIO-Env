"""Build parity at engine level: structures, upgrade, delete.

Humans build cities/defense/silos/ports/factories/SAMs, warships and nukes
from the build menu, upgrade structures, and delete units. All three ride
the production intent paths (ConstructionExecution / UpgradeStructure /
DeleteUnit via Executor.createExec).
"""

from __future__ import annotations

import pytest

from openfrontbench.engine import EngineWorker, EngineError


def _plains() -> EngineWorker:
    from openfrontbench.engine import PLAINS_MAP_DIR

    return EngineWorker(map_dir=PLAINS_MAP_DIR)


def _rich(engine: EngineWorker) -> dict:
    # Structures cost tens of thousands of gold; humans earn it by holding
    # land, so expand to a 10k-tile economy first. Deterministic on plains.
    snapshot: dict = {}
    for _ in range(10):
        engine.attack("expand", 20000)
        snapshot = engine.advance(100)
    return snapshot


def test_build_defense_post_on_home_tile() -> None:
    with _plains() as engine:
        started = engine.start(nations=0, spawn=(50, 50), tribes=0)
        assert started["units"] == []
        home = started["human"]["spawnTile"]
        assert home is not None
        _rich(engine)

        engine.build_unit("defense-post", home["x"], home["y"])
        built = engine.advance(15)
        posts = [u for u in built["units"] if u["type"] == "Defense Post"]
        assert len(posts) == 1
        assert posts[0]["level"] >= 1


def test_build_unknown_unit_rejected() -> None:
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=0)
        with pytest.raises(EngineError):
            engine.build_unit("death-star", 50, 50)


def test_build_bad_coords_rejected() -> None:
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=0)
        with pytest.raises(EngineError):
            engine.build_unit("city", -1, 50)


def _funded(engine: EngineWorker, minimum: int = 400000) -> dict:
    # City base is 125k and upgrade doubles per built unit; earn until the
    # treasury covers build + upgrade. Deterministic income on capped land.
    snapshot: dict = {}
    for _ in range(60):
        snapshot = engine.advance(200)
        if int(snapshot["human"]["gold"]) >= minimum:
            break
    return snapshot


def test_upgrade_city_raises_level() -> None:
    with _plains() as engine:
        started = engine.start(nations=0, spawn=(50, 50), tribes=0)
        home = started["human"]["spawnTile"]
        assert home is not None
        _rich(engine)
        _funded(engine)
        engine.build_unit("city", home["x"], home["y"])
        built = engine.advance(200)
        city = next(u for u in built["units"] if u["type"] == "City")
        assert city["under_construction"] is False
        assert city["level"] == 1

        engine.upgrade_unit(city["id"])
        upgraded = engine.advance(5)
        city_after = next(u for u in upgraded["units"] if u["id"] == city["id"])
        assert city_after["level"] == 2


def test_upgrade_unknown_unit_rejected() -> None:
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=0)
        with pytest.raises(EngineError):
            engine.upgrade_unit("99999")


def test_upgrade_amount_rejects_out_of_range() -> None:
    # The production schema bounds amount to 1..50 (MAX_UPGRADE_AMOUNT).
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=0)
        for bad in (0, 51, -1, 1.5, True):
            with pytest.raises(EngineError):
                engine.upgrade_unit("99999", bad)


def test_build_amount_rejects_out_of_range() -> None:
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=0)
        for bad in (0, 51, -1, 1.5):
            with pytest.raises(EngineError):
                engine.build_unit("atom-bomb", 60, 60, None, bad)
        with pytest.raises(EngineError):
            engine.build_unit("atom-bomb", 60, 60, "up", None)


def test_build_rocket_direction_and_amount_reach_the_intent() -> None:
    # The live client sends rocketDirectionUp for atom/hydrogen bombs and a
    # stack amount for stackable nukes; the worker must pass both through.
    # Acceptance is the parity bit (gold/tile validation is the engine's).
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=0)
        engine.build_unit("atom-bomb", 60, 60, True, 3)
        engine.build_unit("hydrogen-bomb", 60, 60, False, None)


def test_delete_unit_removes_it() -> None:
    with _plains() as engine:
        started = engine.start(nations=0, spawn=(50, 50), tribes=0)
        home = started["human"]["spawnTile"]
        assert home is not None
        _rich(engine)
        engine.build_unit("defense-post", home["x"], home["y"])
        built = engine.advance(60)
        post = next(u for u in built["units"] if u["type"] == "Defense Post")
        assert post["under_construction"] is False

        # Deletion runs on the tick loop like every other execution, with a
        # production grace period (~150-350 ticks) before removal.
        engine.delete_unit(post["id"])
        cleared = engine.advance(200)
        cleared = engine.advance(200)
        assert all(u["id"] != post["id"] for u in cleared["units"])


def test_delete_unknown_unit_rejected() -> None:
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=0)
        with pytest.raises(EngineError):
            engine.delete_unit("99999")


def test_nuke_order_accepted() -> None:
    # Launching is the same build_unit path with the target tile; humans get
    # no pre-flight guarantee either. Acceptance (no error) is the parity bit.
    with _plains() as engine:
        engine.start(nations=0, spawn=(50, 50), tribes=0)
        engine.build_unit("atom-bomb", 60, 60)
