"""Nation duel regression tests: two nations with different brains in one
world (Hard production vs Improved-Hard), same seed, idle human third
party. The roster must tape each nation's behavior so replays reproduce
the duel instead of running both nations on one logic.
"""

from __future__ import annotations

from openfrontbench.engine import (
    BRITANNIA_MAP_DIR,
    EngineWorker,
)


def _duel_hashes(
    game_id: str, behaviors: list[str] | None, difficulty: str = "hard"
) -> tuple[list[dict], list]:
    with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
        engine.start(
            nations=2,
            difficulty=difficulty,
            map_size="compact",
            spawn=None,
            tribes=0,
            game_id=game_id,
            nation_behaviors=behaviors,
        )
        engine.advance(60)
        record = engine.save_record()
    nations = [p for p in record["players"] if p.get("kind") == "nation"]
    hashes = [t["hash"] for t in record["turns"] if t.get("hash") is not None]
    return nations, hashes


def test_duel_mixed_behaviors_taped_in_order() -> None:
    """Per-nation behavior rides the roster in spawn order: nation 0 plays
    production Hard, nation 1 plays Improved-Hard."""
    nations, _ = _duel_hashes("duel-mix-1", ["production", "improved-hard"])
    assert len(nations) == 2
    assert [n["behavior"] for n in nations] == ["production", "improved-hard"]


def test_duel_mixed_behaviors_deterministic() -> None:
    """Same seed + same behavior assignment replays the same duel world."""
    _, first = _duel_hashes("duel-mix-1", ["production", "improved-hard"])
    _, second = _duel_hashes("duel-mix-1", ["production", "improved-hard"])
    assert [n for n, _ in enumerate(first)] == [n for n, _ in enumerate(second)]
    assert first == second


def test_duel_mixed_differs_from_all_production() -> None:
    """The mixed duel is a different world from all-production on the same
    seed — the second nation's logic actually changes the sim."""
    _, mixed = _duel_hashes("duel-mix-1", ["production", "improved-hard"])
    _, prod = _duel_hashes("duel-mix-1", ["production", "production"])
    assert mixed != prod


def test_single_difficulty_tapes_uniform_behavior() -> None:
    """Backward compat: no nation_behaviors means every nation plays the
    game difficulty (production label, or improved-hard for that mode)."""
    nations, _ = _duel_hashes("duel-uniform-1", None)
    assert len(nations) == 2
    assert [n["behavior"] for n in nations] == ["production", "production"]
    nations_ih, _ = _duel_hashes("duel-uniform-ih", None, difficulty="improved-hard")
    assert [n["behavior"] for n in nations_ih] == [
        "improved-hard",
        "improved-hard",
    ]
