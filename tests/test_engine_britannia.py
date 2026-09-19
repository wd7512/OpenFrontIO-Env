"""Real online map: Britannia at production Compact size.

No mocks: the pinned engine loads the shipped Britannia bins at the exact
resolution production Compact games use (map4x + map16x mini, manifest
nation spawns halved by the loader rule), the human spawns on land via
seeded random placement, and fixed manifest nations spawn on their
production cells. Plains remains the fast fixture for unit tests;
Britannia is the benchmark board.
"""

from pathlib import Path

from openfrontbench.engine import EngineWorker

BRITANNIA = (
    Path(__file__).resolve().parent.parent
    / "vendor"
    / "OpenFrontIO"
    / "resources"
    / "maps"
    / "britannia"
)


def _britannia(**kwargs):
    return EngineWorker(map_dir=BRITANNIA, **kwargs)


def test_britannia_boots_at_online_resolution():
    with _britannia() as engine:
        started = engine.start(
            nations=3, difficulty="easy", map_size="compact", spawn=None
        )
        assert (started["width"], started["height"]) == (800, 1044)
        assert started["human"]["tiles"] > 0
        assert len(started["nations"]) == 3
        assert all(n["tiles"] > 0 for n in started["nations"])


def test_britannia_spawn_is_deterministic():
    first = second = None
    with _britannia() as engine:
        first = engine.start(
            nations=3, difficulty="easy", map_size="compact", spawn=None
        )
    with _britannia() as engine:
        second = engine.start(
            nations=3, difficulty="easy", map_size="compact", spawn=None
        )
    assert first["human"]["spawnTile"] == second["human"]["spawnTile"]
    assert [n["name"] for n in first["nations"]] == [
        n["name"] for n in second["nations"]
    ]


def test_britannia_boat_targets_are_launchable():
    # The agent cannot see terrain; boat_targets is its only aim. Every
    # listed target must be launchable through the production boat intent.
    with _britannia() as engine:
        started = engine.start(
            nations=0, difficulty="easy", map_size="compact", spawn=None
        )
        targets = started["boat_targets"]
        assert targets, "coastal spawn on an island must expose crossings"
        target = targets[0]
        engine.boat_attack(x=target["x"], y=target["y"], troops=1000)
        advanced = engine.advance(1)
        assert advanced["boats"], "boat order to a listed target must launch"


def test_britannia_rejects_bad_map_size():
    with _britannia() as engine:
        try:
            engine.start(nations=1, difficulty="easy", map_size="huge")  # type: ignore[arg-type]
        except Exception:
            pass
        else:
            raise AssertionError("britannia accepted bad map_size")
