"""Evaluator scoring, policy loading and tiny headless runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openfrontbench.code_evo import evaluator as evo
from openfrontbench.code_evo.evaluator import EvalConfig
from openfrontbench.code_evo.spawns import Spawn, SpawnRegistry
from openfrontbench.paths import REPO_ROOT

BASELINE = REPO_ROOT / "src" / "openfrontbench" / "policies" / "evolve_me.py"


def test_score_episode_weights() -> None:
    plain = evo.score_episode(1000, 500, None)
    assert plain == 1000 + 5 * 500
    assert evo.score_episode(1000, 500, "Agent") == plain + evo.WIN_BONUS
    assert evo.score_episode(0, 0, "Gaul") == 0


def test_load_policy_baseline() -> None:
    policy = evo.load_policy(BASELINE)
    orders = policy.decide({"in_spawn_phase": True})
    assert orders == []


def test_run_episode_tiny_plains() -> None:
    policy = evo.load_policy(BASELINE)
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    episode = evo.run_episode(Spawn(id="T", x=50, y=50), policy, "plains", config)
    assert episode.decisions == 3
    assert episode.tiles_peak > 0
    assert episode.policy_errors == 0


def test_run_episode_relative_record_dir_lands_correctly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Relative tape dirs must resolve against the caller cwd, not the
    worker's (the engine subprocess runs with its own cwd)."""
    import os

    monkeypatch.chdir(tmp_path)
    game_dir = Path("games") / "T"
    game_dir.mkdir(parents=True)
    policy = evo.load_policy(BASELINE)
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    evo.run_episode(
        Spawn(id="T", x=50, y=50), policy, "plains", config, record_dir=game_dir
    )
    assert (game_dir / "record.json").is_file()
    assert os.environ.get("OPENFRONT_RECORD_DIR") is None


def test_compact_game_ids_are_safe_distinct_and_stable() -> None:
    import re

    from openfrontbench.code_evo.evaluator import (
        compact_game_id_for,
        game_id_for,
    )

    registry = SpawnRegistry(
        map="europe",
        spawns=tuple(
            Spawn(id=sid, x=x, y=y)
            for sid, x, y in [
                ("ctr", 1450, 1000),
                ("fne", 2500, 300),
                ("fse", 2500, 1300),
                ("wsw", 700, 1200),
                ("e", 2000, 700),
                ("w", 900, 700),
                ("n", 1800, 300),
                ("s", 2000, 1350),
            ]
        ),
        sha256="abc",
        raw={},
    )
    prefix = "openfront-research-v2-20260920-1158"
    ids = [compact_game_id_for(prefix, s) for s in registry.spawns]
    assert all(i is not None and re.fullmatch(r"[A-Za-z0-9]{8}", i) for i in ids)
    assert len(set(ids)) == len(ids)
    assert ids == [compact_game_id_for(prefix, s) for s in registry.spawns]
    assert all(i != game_id_for(prefix, s) for i, s in zip(ids, registry.spawns))
    assert compact_game_id_for(None, registry.spawns[0]) is None


def test_compact_game_id_matches_worker_derivation() -> None:
    """Pin against engine/worker.ts tapeGameId (node-verified vector)."""
    from openfrontbench.code_evo.evaluator import compact_game_id_for

    spawn = Spawn(id="ctr", x=1450, y=1000)
    assert (
        compact_game_id_for("openfront-research-v2-20260920-1158", spawn) == "c6521970"
    )


def test_world_id_for_rejects_unknown_scheme() -> None:
    import pytest as _pytest

    with _pytest.raises(ValueError, match="unknown world_scheme"):
        evo.world_id_for("prefix", Spawn(id="T", x=50, y=50), "fancy")


def test_evaluate_candidate_writes_aggregate(tmp_path: Path) -> None:
    policy = evo.load_policy(BASELINE)
    assert policy is not None
    registry = SpawnRegistry(
        map="plains",
        spawns=(Spawn(id="T", x=50, y=50),),
        sha256="abc",
        raw={},
    )
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    result = evo.evaluate_candidate(BASELINE, registry, config, tmp_path / "out")
    assert result["episodes"] == 1
    assert result["mean_score"] > 0
    payload = json.loads((tmp_path / "out" / "aggregate.json").read_text())
    assert payload["mean_score"] == result["mean_score"]
    game_dir = tmp_path / "out" / "games" / "T"
    assert (game_dir / "record.json").is_file()
    summary = json.loads((game_dir / "summary.json").read_text())
    assert summary["pipeline"] == "code-evo"
    assert summary["spawn_id"] == "T"
    assert summary["score"] == result["mean_score"]
    experiment = json.loads((tmp_path / "out" / "experiment.json").read_text())
    assert experiment["kind"] == "code-evo"


def test_game_id_helpers() -> None:
    assert evo.game_id_for(None, Spawn(id="NW", x=1, y=2)) is None
    assert evo.game_id_for("run", Spawn(id="NW", x=1, y=2)) == "run-NW"
    assert evo.sanitize_game_id("a b/c") == "a_b_c"
    assert len(evo.sanitize_game_id("x" * 100)) == 32
    assert evo.sanitize_game_id("!!") == "game"


def test_engine_rejects_bad_game_id() -> None:
    from openfrontbench.engine import EngineError, EngineWorker

    worker = EngineWorker()
    try:
        worker.start(game_id="not a valid id!")
    except EngineError:
        return
    raise AssertionError("bad game_id was accepted")


def test_run_episode_records_spawn_tile_and_game_id() -> None:
    policy = evo.load_policy(BASELINE)
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    episode = evo.run_episode(
        Spawn(id="T", x=50, y=50),
        policy,
        "plains",
        config,
        game_id="probe-1",
    )
    assert episode.spawn_tile == (50, 50)
    assert episode.game_id == "probe-1"


def test_same_game_id_replays_same_world() -> None:
    policy = evo.load_policy(BASELINE)
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    spawn = Spawn(id="T", x=50, y=50)
    first = evo.run_episode(spawn, policy, "plains", config, game_id="repro-1")
    second = evo.run_episode(spawn, policy, "plains", config, game_id="repro-1")
    assert (first.ticks, first.tiles_peak) == (second.ticks, second.tiles_peak)


def test_evaluate_candidate_game_id_prefix(tmp_path: Path) -> None:
    registry = SpawnRegistry(
        map="plains",
        spawns=(Spawn(id="T", x=50, y=50),),
        sha256="abc",
        raw={},
    )
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    result = evo.evaluate_candidate(
        BASELINE, registry, config, tmp_path / "out", game_id_prefix="exp1"
    )
    summary = json.loads(
        (tmp_path / "out" / "games" / "T" / "summary.json").read_text()
    )
    assert summary["extra"]["spawn_xy"] == [50, 50]
    assert summary["extra"]["spawn_tile"] == [50, 50]
    assert summary["extra"]["game_id"] == "exp1-T"
    assert result["spawns"][0]["game_id"] == "exp1-T"
    assert result["spawns"][0]["outcome"] in ("eliminated", "ceiling", "errors")
    assert result["spawns"][0]["troops_peak"] >= 0
    assert result["spawns"][0]["gold_peak"] >= 0
    assert isinstance(result["spawns"][0]["city_ever"], bool)
    assert summary["extra"]["outcome"] == result["spawns"][0]["outcome"]


def test_game_id_prefix_never_merges_spawns() -> None:
    long_prefix = "openfront-code-evo-20260920-0858"
    ids = [
        evo.game_id_for(long_prefix, Spawn(id=sid, x=0, y=0))
        for sid in ("ctr", "fne", "fse", "wsw", "e", "w", "n", "s")
    ]
    assert None not in ids
    assert len(set(ids)) == 8
    assert all(len(gid) <= 32 for gid in ids if gid is not None)


def test_jobs_rejects_non_positive() -> None:
    import pytest
    from typing import Any

    registry = SpawnRegistry(map="plains", spawns=(), sha256="abc", raw={})
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        bad_values: list[Any] = [0, -1, True, "8"]
        for bad in bad_values:
            with pytest.raises(ValueError):
                evo.evaluate_candidate(
                    BASELINE, registry, config, Path(tmp) / "out", jobs=bad
                )


def test_parallel_matches_sequential(tmp_path: Path) -> None:
    registry = SpawnRegistry(
        map="plains",
        spawns=(Spawn(id="A", x=50, y=50), Spawn(id="B", x=60, y=60)),
        sha256="abc",
        raw={},
    )
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    seq = evo.evaluate_candidate(
        BASELINE,
        registry,
        config,
        tmp_path / "seq",
        game_id_prefix="par",
        jobs=1,
    )
    par = evo.evaluate_candidate(
        BASELINE,
        registry,
        config,
        tmp_path / "par",
        game_id_prefix="par",
        jobs=2,
    )
    assert par["mean_score"] == seq["mean_score"]
    assert [s["score"] for s in par["spawns"]] == [s["score"] for s in seq["spawns"]]
    assert (tmp_path / "par" / "games" / "A" / "record.json").is_file()
    assert (tmp_path / "par" / "games" / "B" / "record.json").is_file()


def test_evaluate_candidate_compact_scheme_uses_safe_world_ids(
    tmp_path: Path,
) -> None:
    import json
    import re

    registry = SpawnRegistry(
        map="plains",
        spawns=(Spawn(id="A", x=50, y=50),),
        sha256="abc",
        raw={},
    )
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    result = evo.evaluate_candidate(
        BASELINE,
        registry,
        config,
        tmp_path / "compact",
        game_id_prefix="par",
        jobs=1,
        world_scheme="compact",
    )
    (world,) = [s["game_id"] for s in result["spawns"]]
    assert re.fullmatch(r"[A-Za-z0-9]{8}", world)
    tape = json.loads(
        (tmp_path / "compact" / "games" / "A" / "record.json").read_text()
    )
    # Tape label IS the live seed, so replays re-derive identical tribes.
    assert tape["gameId"] == world


def test_evaluate_candidate_rejects_unknown_world_scheme(
    tmp_path: Path,
) -> None:
    import pytest as _pytest

    registry = SpawnRegistry(
        map="plains",
        spawns=(Spawn(id="A", x=50, y=50),),
        sha256="abc",
        raw={},
    )
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    with _pytest.raises(ValueError, match="unknown world_scheme"):
        evo.evaluate_candidate(
            BASELINE,
            registry,
            config,
            tmp_path / "nope",
            game_id_prefix="par",
            world_scheme="fancy",
        )


def _mutant_policy(tmp_path: Path) -> Path:
    """Baseline with a behavior-changing tweak (expand percent 20 -> 99)."""
    text = BASELINE.read_text(encoding="utf-8")
    mutant = text.replace("_EXPAND_PERCENT = 20", "_EXPAND_PERCENT = 99")
    assert mutant != text
    path = tmp_path / "mutant_evolve_me.py"
    path.write_text(mutant, encoding="utf-8")
    return path


def test_order_stream_identical_for_same_policy() -> None:
    spawn = Spawn(id="A", x=50, y=50)
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    first = evo.order_stream(BASELINE, spawn, "plains", config, "s1")
    second = evo.order_stream(BASELINE, spawn, "plains", config, "s1")
    assert first == second
    assert len(first) == 3


def test_probe_divergence_detects_behavior_change(tmp_path: Path) -> None:
    registry = SpawnRegistry(
        map="plains",
        spawns=(Spawn(id="A", x=50, y=50), Spawn(id="B", x=60, y=60)),
        sha256="x",
        raw={},
    )
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    diverged, detail = evo.probe_divergence(
        BASELINE, BASELINE, registry, config, "probe"
    )
    assert diverged is False
    assert "identical" in detail
    mutant = _mutant_policy(tmp_path)
    diverged, detail = evo.probe_divergence(mutant, BASELINE, registry, config, "probe")
    assert diverged is True
    assert "diverged on A at decision 0" in detail
