"""Real-engine 1v1: one human vs one generated nation on the plains fixture.

No mocks: the nation spawns through the production NationExecution +
SpawnExecution path, acts through the production AI behaviors, and the
production WinCheckExecution watches for a winner.
"""

from __future__ import annotations

import pytest

from openfrontbench.engine import EngineError, EngineWorker


def _nation(snapshot: dict) -> dict:
    nations = snapshot.get("nations")
    assert isinstance(nations, list) and len(nations) == 1, snapshot
    return nations[0]


def test_1v1_starts_with_spawned_human_and_nation() -> None:
    with EngineWorker() as engine:
        snapshot = engine.start(nations=1)

    assert snapshot["status"] == "started"
    assert snapshot["inSpawnPhase"] is False
    assert snapshot["winner"] is None
    human = snapshot["human"]
    assert human["tiles"] > 0
    nation = _nation(snapshot)
    assert nation["tiles"] > 0
    assert nation["type"] == "nation"
    assert nation["id"] != human["id"]


def test_1v1_nation_acts_on_advance() -> None:
    with EngineWorker() as engine:
        before = engine.start(nations=1)
        after = engine.advance(300)

    assert after["tick"] == before["tick"] + 300
    assert after["winner"] is None
    nation_before, nation_after = _nation(before), _nation(after)
    assert (nation_after["tiles"], nation_after["troops"]) != (
        nation_before["tiles"],
        nation_before["troops"],
    )


def test_1v1_fresh_instances_are_identical() -> None:
    with EngineWorker() as first:
        first_start = first.start(nations=1)
        first_advanced = first.advance(200)
    with EngineWorker() as second:
        second_start = second.start(nations=1)
        second_advanced = second.advance(200)

    assert first_start == second_start
    assert first_advanced == second_advanced


@pytest.mark.parametrize("bad_nations", [-1, True, "1", 1.5, 99])
def test_invalid_nations_rejected_and_engine_survives(bad_nations: object) -> None:
    with EngineWorker() as engine:
        with pytest.raises(EngineError):
            engine.start(nations=bad_nations)  # type: ignore[arg-type]
        snapshot = engine.start()
        assert snapshot["human"]["tiles"] > 0
