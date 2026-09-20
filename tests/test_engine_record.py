"""Turn-recording parity at engine level: every game-tick intent is taped.

The worker buffers {turnNumber, intents} per executed tick (the same shape
the production server archives for replays) and can save a record file:
{gameId, map, ticks, players, turns}. Recording is observer-only — no
intents are added or altered. A later slice can feed the record to the
real client; here we pin that the tape exists and is faithful.
"""

from __future__ import annotations

import json

from openfrontbench.engine import (
    BRITANNIA_MAP_DIR,
    EUROPE_MAP_DIR,
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


def test_flush_record_writes_file_without_tape_over_pipe(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENFRONT_RECORD_DIR", str(tmp_path))
    with EngineWorker(map_dir=EUROPE_MAP_DIR) as engine:
        engine.start(
            nations=5,
            difficulty="easy",
            map_size="full",
            spawn=(1450, 1000),
            tribes=20,
            game_id="flush-1",
        )
        engine.advance(100)
        result = engine.flush_record()
    assert "turns" not in result
    assert result["ticks"] >= 100
    assert result["gameId"] == "flush-1"
    tape = json.loads((tmp_path / "record.json").read_text())
    assert len(tape["turns"]) >= 100
    # Tape label is converter-safe (archived-GameRecord needs 8 alnum
    # chars) while the engine keeps seeding from the raw id.
    assert tape["gameId"] == "dbd370f3"


def test_tape_game_id_passes_through_when_already_safe(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENFRONT_RECORD_DIR", str(tmp_path))
    with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
        _start(engine)
        engine.advance(10)
        record = engine.save_record()
    assert record["gameId"] == "ENGINE01"


def _tape_hashes(game_id: str) -> list[tuple[int, float]]:
    with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
        _start(engine, game_id=game_id)
        engine.advance(60)
        record = engine.save_record()
    return [
        (t["turnNumber"], t["hash"])
        for t in record["turns"]
        if t.get("hash") is not None
    ]


def test_tape_hashes_every_fifty_ticks_and_reproduce() -> None:
    """State hashes ride the tape every 50 ticks and are deterministic:
    the property archive replays rely on (the client verifies these)."""
    first = _tape_hashes("hashdet-1")
    assert [n for n, _ in first] == [0, 50]
    assert all(isinstance(h, (int, float)) for _, h in first)
    assert _tape_hashes("hashdet-1") == first
    assert [h for _, h in _tape_hashes("hashdet-2")] != [h for _, h in first]
