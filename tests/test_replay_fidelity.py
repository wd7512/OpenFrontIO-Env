"""Replay-fidelity regression tests: the tape must re-simulate.

OF000018 lesson: the engine seeded its RNG from the raw game id while the
tape carried a derived label, and resolved the map theme by enum key
("The Box" missed, fell back to Asia). Served replays then re-simulated a
*different world* with production AI — the screen showed a nation win that
never happened. These tests pin the three identities a faithful replay
needs: seed, theme, and the verification harness itself.
"""

from __future__ import annotations

from pathlib import Path

from openfrontbench.engine import (
    BRITANNIA_MAP_DIR,
    THEBOX_MAP_DIR,
    EngineWorker,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _fnv1a32_hex(text: str) -> str:
    """Mirror of tapeGameId in engine/worker.ts (FNV-1a over UTF-8 bytes).

    Kept inline so this test has no heavy imports; any change to the
    worker hashing must update both sides together.
    """
    h = 0x811C9DC5
    for byte in text.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return format(h, "08x")


def _tape_hashes(
    engine: EngineWorker, game_id: str
) -> tuple[str, list[tuple[int, float]]]:
    engine.start(
        nations=1,
        difficulty="easy",
        map_size="compact",
        spawn=None,
        tribes=0,
        game_id=game_id,
    )
    engine.advance(60)
    record = engine.save_record()
    hashes = [
        (t["turnNumber"], t["hash"])
        for t in record["turns"]
        if t.get("hash") is not None
    ]
    return record["gameId"], hashes


def test_taped_id_seeds_same_world_as_raw_id() -> None:
    """Single seed identity: a run started with an unsafe raw id must
    produce bit-identical state hashes to a run started directly with its
    taped label — the only id a client replay ever sees. Pre-fix this
    failed: the sim seeded from the raw id, the replay from the label."""
    raw_id = "seed-ident-1"
    taped = _fnv1a32_hex(raw_id)
    assert taped != raw_id  # guard: fixture id must actually need taping
    with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
        raw_label, raw_hashes = _tape_hashes(engine, raw_id)
    with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
        taped_label, taped_hashes = _tape_hashes(engine, taped)
    assert raw_label == taped
    assert taped_label == taped
    assert [n for n, _ in raw_hashes] == [0, 50]
    assert raw_hashes == taped_hashes


def test_box_tape_carries_thebox_theme() -> None:
    """The tape must carry gameMap 'The Box' (enum value), not the Asia
    fallback the old key-lookup produced for spaced manifest names."""
    with EngineWorker(map_dir=THEBOX_MAP_DIR) as engine:
        engine.start(
            nations=1,
            difficulty="easy",
            map_size="compact",
            spawn=None,
            tribes=0,
            game_id="THEMEBOX",
        )
        engine.advance(60)
        record = engine.save_record()
    assert record["gameConfig"]["gameMap"] == "The Box"


def test_verify_replay_harness_promoted() -> None:
    """The client-path replay check must live in the repo, not /tmp:
    scripts/verify_replay.ts replays a served tape through the real
    createGameRunner pipeline and reports FAITHFUL/DIVERGED."""
    harness = REPO_ROOT / "scripts" / "verify_replay.ts"
    assert harness.is_file(), "replay harness lost (was /tmp-only)"
    text = harness.read_text()
    for marker in (
        "createGameRunner",
        "FAITHFUL",
        "DIVERGED",
        "nationBehavior",
        # Invocation must use vendor tsx + tsconfig (bare resources/*
        # imports fail otherwise); pin the documented command.
        "tsconfig",
        # Duel tapes verify through the per-nation assignment, not the
        # uniform behavior (a uniform "duel" string would attach production
        # to every nation and silently diverge).
        "nationBehaviors",
    ):
        assert marker in text, marker
