"""Turn-recording parity at engine level: every game-tick intent is taped.

The worker buffers {turnNumber, intents} per executed tick (the same shape
the production server archives for replays) and can save a record file:
{gameId, map, ticks, players, turns}. Recording is observer-only — no
intents are added or altered. A later slice can feed the record to the
real client; here we pin that the tape exists and is faithful.
"""

from __future__ import annotations

import json

from openfront_mcp.engine import (
    BRITANNIA_MAP_DIR,
    EngineWorker,
)


def _start(engine: EngineWorker, **kwargs):
    params = {
        "nations": 1,
        "difficulty": "easy",
        "map_size": "compact",
        "spawn": None,
        "tribes": 0,
    }
    params.update(kwargs)
    return engine.start(**params)


def test_record_tapes_human_intents(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENFRONT_RECORD_DIR", str(tmp_path))
    with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
        _start(engine)
        engine.advance(60)
        engine.attack("expand", 20000)
        engine.advance(50)
        record = engine.save_record()
    assert record["ticks"] >= 110
    assert record["startedAt"] > 0
    for key in ("gameMap", "gameMode", "difficulty", "bots", "nations"):
        assert key in record["gameConfig"], key
    assert len(record["turns"]) >= 110
    numbers = [t["turnNumber"] for t in record["turns"]]
    assert numbers == sorted(numbers)
    assert len(set(numbers)) == len(numbers)
    attacks = [
        intent
        for turn in record["turns"]
        for intent in turn["intents"]
        if intent.get("type") == "attack"
    ]
    assert len(attacks) >= 1
    path = tmp_path / "record.json"
    assert path.stat().st_size > 0
    assert json.loads(path.read_text())["ticks"] == record["ticks"]


def test_record_without_env_is_noop(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENFRONT_RECORD_DIR", raising=False)
    with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
        _start(engine)
        engine.advance(10)
        record = engine.save_record()
    # Tape still returned in-memory; nothing written to disk.
    assert len(record["turns"]) >= 10
    assert list(tmp_path.iterdir()) == []


def test_record_covers_spawn_ticks() -> None:
    with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
        _start(engine)
        record = engine.save_record()
    spawns = [
        intent
        for turn in record["turns"]
        for intent in turn["intents"]
        if intent.get("type") == "spawn"
    ]
    assert len(spawns) >= 1
