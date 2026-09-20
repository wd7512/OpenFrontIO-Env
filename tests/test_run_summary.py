"""Unified run summaries and experiment manifests."""

from __future__ import annotations

import json
from pathlib import Path

from openfrontbench.experiment import read_experiment, write_experiment
from openfrontbench.run_summary import (
    build_summary,
    from_live_result,
    read_summary,
    write_summary,
)


def test_build_summary_versioned_shape() -> None:
    summary = build_summary(game="g", pipeline="code-evo", score=12.0)
    assert summary["version"] == 1
    assert summary["game"] == "g"
    assert summary["score"] == 12.0
    assert summary["created_at"]
    json.dumps(summary)


def test_write_and_read_summary_roundtrip(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    write_summary(run, build_summary(game="run", model="m", tiles_final=7))
    read = read_summary(run)
    assert read is not None and read["model"] == "m" and read["tiles_final"] == 7


def test_read_summary_falls_back_to_live_result(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "live_result.json").write_text(
        json.dumps(
            {
                "model": "m",
                "scenario": "solo",
                "difficulty": "hard",
                "max_decisions": 100,
                "duration_s": 9.0,
                "summary": {
                    "decisions": [1],
                    "ticks": [53, 103],
                    "winner": None,
                    "tool_calls": 4,
                    "final_human": {"tiles": 10, "troops": 20},
                    "metrics": {"tiles_peak": 99},
                },
            }
        )
    )
    read = read_summary(run)
    assert read is not None
    assert read["pipeline"] == "live"
    assert read["tick_first"] == 53
    assert read["tick_last"] == 103
    assert read["tiles_peak"] == 99


def test_read_summary_none_when_empty(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    assert read_summary(run) is None


def test_from_live_result_tolerates_garbage() -> None:
    summary = from_live_result("g", {"summary": None})
    assert summary["game"] == "g"
    assert summary["decisions"] is None


def test_experiment_manifest_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "exp"
    root.mkdir()
    write_experiment(root, name="exp", kind="code-evo", config={"a": 1})
    meta = read_experiment(root)
    assert meta is not None and meta["kind"] == "code-evo"
    assert read_experiment(tmp_path / "missing") is None
