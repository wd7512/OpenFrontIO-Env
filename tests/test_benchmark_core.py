"""Benchmark core process tests against a fake driver (no MCP server).

The smoke episode (``tests/test_episode.py``) is the worked example;
these tests prove the core takes any driver as input. All fixtures are
synthetic; nothing touches the engine, the vendor tree, or the network.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openfront_mcp import benchmark
from openfront_mcp.episodes.smoke import SMOKE_DRIVER


@dataclass(frozen=True)
class FakeDriver:
    scenario: str = "fake-scenario"
    controller: str = "fake-controller"
    allowed_scenarios: frozenset[str] = frozenset({"fake-scenario"})
    allowed_controllers: frozenset[str] = frozenset({"fake-controller"})
    server_module: str = "fake_server"
    decision_tool: str = "take_turn"
    source: str = "fake"
    completion_reason: str = "fake cap reached"
    winner: Any = "nobody"
    metrics: dict[str, Any] = field(default_factory=lambda: {"custom": 1})
    engine_bundle_rel: str = "fake/worker.bin"
    engine_bundle_path: Path = Path("/nonexistent/worker.bin")
    map_assets: tuple[tuple[str, Path], ...] = ()
    vendor_tag: str = "v0"
    vendor_pin: str = "0" * 40

    def build_steps(self, max_decisions: int) -> list[tuple[str, dict[str, Any]]]:
        return [("take_turn", {"n": n}) for n in range(1, max_decisions + 1)]

    def probe_issues(self) -> tuple[str | None, list[str]]:
        return None, []


FAKE = FakeDriver()


def _config(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "version": 1,
        "scenario": "fake-scenario",
        "controller": "fake-controller",
        "max_decisions": 3,
    }
    base.update(overrides)
    return base


def test_parse_uses_driver_sets() -> None:
    config = benchmark.parse_episode_config(_config(), FAKE)
    assert (config.scenario, config.controller) == ("fake-scenario", "fake-controller")
    try:
        benchmark.parse_episode_config(_config(scenario="plains-human-smoke"), FAKE)
    except benchmark.ConfigError as error:
        assert "fake-scenario" in str(error)
    else:
        raise AssertionError("fake driver must reject the smoke scenario")


def test_parse_default_driver_still_accepts_smoke() -> None:
    config = benchmark.parse_episode_config(
        {
            "version": 1,
            "scenario": SMOKE_DRIVER.scenario,
            "controller": SMOKE_DRIVER.controller,
            "max_decisions": 1,
        }
    )
    assert config.scenario == SMOKE_DRIVER.scenario


def test_build_result_uses_driver_record() -> None:
    stats = {
        "errors": [],
        "decisions_taken": 3,
        "tick_start": 1,
        "tick_end": 2,
        "tool_calls": 5,
        "tool_errors": 0,
    }
    result = benchmark._build_result(
        benchmark.EpisodeConfig("fake-scenario", "fake-controller", 3),
        stats,
        [],
        FAKE,
    )
    assert result["outcome"] == "decision_cap"
    assert result["reason"] == "fake cap reached"
    assert result["source"] == "fake"
    assert result["winner"] == "nobody"
    assert result["metrics"] == {"custom": 1}
    assert result["metrics"] is not FAKE.metrics


def test_build_result_error_path_uses_first_problem() -> None:
    stats = {
        "errors": [],
        "decisions_taken": 0,
        "tick_start": None,
        "tick_end": None,
        "tool_calls": 0,
        "tool_errors": 0,
    }
    result = benchmark._build_result(
        benchmark.EpisodeConfig("fake-scenario", "fake-controller", 3),
        stats,
        ["boom"],
        FAKE,
    )
    assert result["outcome"] == "error"
    assert result["reason"] == "boom"


def test_build_manifest_uses_driver_artifacts(tmp_path: Path) -> None:
    bundle = tmp_path / "worker.bin"
    bundle.write_bytes(b"bundle-bytes")
    tile = tmp_path / "tile.bin"
    tile.write_bytes(b"tile-bytes")
    trace = tmp_path / "trace.jsonl"
    trace.write_text("{}\n", encoding="utf-8")
    result_path = tmp_path / "result.json"
    result_path.write_text("{}\n", encoding="utf-8")
    driver = dataclasses.replace(
        FAKE,
        engine_bundle_path=bundle,
        map_assets=(("fake/tile.bin", tile),),
    )
    manifest = benchmark.build_manifest(b"{}", trace, result_path, driver, None)
    assert manifest["engine_bundle"]["label"] == "fake/worker.bin"
    assert manifest["map_assets"][0]["label"] == "fake/tile.bin"
    assert manifest["vendor_pin"]["expected_commit"] == "0" * 40
    assert manifest["vendor_pin"]["actual_commit"] is None
    assert manifest["vendor_pin"]["matches"] is False
    assert manifest["config_sha256"] == benchmark._sha256_bytes(b"{}")
    assert manifest["trace_sha256"] == benchmark._sha256_file(trace)


def test_smoke_driver_builds_bounded_steps() -> None:
    steps = SMOKE_DRIVER.build_steps(2)
    names = [name for name, _ in steps]
    assert names.count(SMOKE_DRIVER.decision_tool) == 2
    assert names[0] == "start_smoke_game"
    assert names[-1] == "close_game"
