"""Identical solo format: World full-res, 1 human, 400 tribes, 0 nations.

Mirrors SinglePlayerModal DEFAULT_OPTIONS + GameRunner.init exactly:
World/Normal(full-res)/Singleplayer/FFA/Easy, bots=400 driving
spawnTribes(400), nations disabled, WinCheck on. The only deliberate
deviation: seeded random land spawn (the modal's pick-a-tile is a UI
affordance the agent has no equivalent for; randomSpawn is a real modal
option).
"""

from pathlib import Path

from openfront_mcp.engine import EngineWorker

WORLD = (
    Path(__file__).resolve().parent.parent
    / "vendor"
    / "OpenFrontIO"
    / "resources"
    / "maps"
    / "world"
)


def _world(**kwargs):
    return EngineWorker(map_dir=WORLD, **kwargs)


def test_solo_boots_world_full_with_400_tribes():
    with _world() as engine:
        started = engine.start(tribes=400, spawn=None)
        assert (started["width"], started["height"]) == (2000, 1000)
        assert started["human"]["tiles"] > 0
        assert started["nations"] == []
        advanced = engine.advance(50)
        assert advanced["tick"] == started["tick"] + 50
        assert advanced["tribes"] == 400


def test_solo_exposes_boat_targets_with_coordinates():
    # The agent has no terrain view, so the engine must hand it landing
    # spots: coordinates plus the owner label and, for players, strength.
    with _world() as engine:
        started = engine.start(tribes=400, spawn=None)
        targets = started["boat_targets"]
        assert isinstance(targets, list)
        for target in targets:
            assert isinstance(target["x"], int)
            assert isinstance(target["y"], int)
            assert isinstance(target["owner"], str)
            assert target["troops"] is None or isinstance(target["troops"], int)
            assert target["tiles"] is None or isinstance(target["tiles"], int)
        advanced = engine.advance(50)
        assert isinstance(advanced["boat_targets"], list)


def test_solo_is_deterministic():
    first = second = None
    with _world() as engine:
        first = engine.start(tribes=400, spawn=None)
    with _world() as engine:
        second = engine.start(tribes=400, spawn=None)
    assert first["human"]["spawnTile"] == second["human"]["spawnTile"]
    assert first["human"]["tiles"] == second["human"]["tiles"]


def test_solo_rejects_bad_tribes():
    with _world() as engine:
        for bad in (-1, 501, "many", True):
            try:
                engine.start(tribes=bad, spawn=None)  # type: ignore[arg-type]
            except Exception:
                pass
            else:
                raise AssertionError(f"solo accepted bad tribes {bad!r}")
