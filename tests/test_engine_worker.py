"""Real-engine JSONL worker smoke tests (one human on the plains fixture).

These tests drive the actual pinned OpenFrontIO core through a persistent
Node/TS worker process. Nothing here is mocked: the worker boots the vendor
``Config``/``createGame``/``Executor`` path, spawns the human through the
production ``SpawnExecution``, and advances the real production tick loop
(``PlayerExecution`` production included).

The Python wrapper (``openfront_mcp.engine.EngineWorker``) owns the subprocess
boundary: bounded reads, JSONL request/response, and an actionable error when
the engine bundle or its Node dependencies are missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openfront_mcp.engine import EngineError, EngineWorker

REPO_ROOT = Path(__file__).resolve().parents[1]

# plains is the genuine pinned 100x100 all-land fixture; the worker spawns the
# human at the map centre so snapshots are fully deterministic.
# GameImpl double-buffers executions: a spawn intent added before a tick is
# init()ed at that tick's tail and only tick()s on the next, so the spawn lands
# on the second tick (production truth, not a guess).
EXPECTED_START_TICK = 2
EXPECTED_WIDTH = 100
EXPECTED_HEIGHT = 100
EXPECTED_SPAWN = {"x": 50, "y": 50}
EXPECTED_START_TROOPS = 25_000
# Production default: GameConfigSchema.startingGold is optional with no default,
# so Config.startingGoldFor returns 0n when the host did not set it.
EXPECTED_START_GOLD = "0"


def _human(snapshot: dict) -> dict:
    human = snapshot.get("human")
    assert isinstance(human, dict), snapshot
    return human


def test_start_returns_plains_fixture_with_spawned_human() -> None:
    with EngineWorker() as engine:
        snapshot = engine.start()

    assert snapshot["status"] == "started"
    assert snapshot["width"] == EXPECTED_WIDTH
    assert snapshot["height"] == EXPECTED_HEIGHT
    assert snapshot["inSpawnPhase"] is False
    assert snapshot["tick"] == EXPECTED_START_TICK

    human = _human(snapshot)
    assert human["id"] == "engine-smoke-human"
    assert human["name"] == "Smoke"
    assert human["spawnTile"] == EXPECTED_SPAWN
    assert human["tiles"] > 0
    assert human["troops"] == EXPECTED_START_TROOPS
    assert human["gold"] == EXPECTED_START_GOLD
    assert isinstance(human["hash"], int)


def test_query_is_pure_and_repeatable() -> None:
    with EngineWorker() as engine:
        snapshot = engine.start()
        first = engine.query()
        second = engine.query()

    assert first == second
    assert first["tick"] == snapshot["tick"]
    assert _human(first) == _human(snapshot)


def test_advance_50_ticks_grows_production() -> None:
    with EngineWorker() as engine:
        engine.start()
        before = engine.query()
        after = engine.advance(50)

    assert after["tick"] == before["tick"] + 50
    assert after["inSpawnPhase"] is False
    assert _human(after)["troops"] > _human(before)["troops"]
    assert int(_human(after)["gold"]) > int(_human(before)["gold"])


def test_fresh_instances_are_identical() -> None:
    with EngineWorker() as first:
        first_start = first.start()
        first_advanced = first.advance(50)

    with EngineWorker() as second:
        second_start = second.start()
        second_advanced = second.advance(50)

    assert first_start == second_start
    assert first_advanced == second_advanced


@pytest.mark.parametrize("bad_ticks", [0, -1, 1.5, True, 10**9])
def test_invalid_advance_is_rejected_and_engine_survives(bad_ticks: object) -> None:
    with EngineWorker() as engine:
        engine.start()
        with pytest.raises(EngineError):
            engine.advance(bad_ticks)  # type: ignore[arg-type]
        # A rejected request must not poison the worker.
        assert _human(engine.query())["tiles"] > 0


def test_missing_engine_bundle_raises_actionable_error(tmp_path: Path) -> None:
    with pytest.raises(EngineError) as excinfo:
        with EngineWorker(engine_dir=tmp_path) as engine:
            engine.start()

    message = str(excinfo.value)
    assert "engine" in message.lower()
    assert "npm" in message.lower()
