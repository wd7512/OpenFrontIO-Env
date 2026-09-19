"""Real MCP lifecycle tools + keyless scripted-episode CLI (vertical slice).

Two real integration surfaces, no engine mocks:

1. The four lifecycle tools (start_smoke_game / get_overview / end_decision /
   close_game) are driven over a real stdio MCP session against the packaged
   server, with a real pinned-engine worker behind the server lifespan.
2. The keyless episode CLI (`python -m openfrontbench.benchmark --config
   examples/smoke.json --output <dir>`) drives that same MCP server over real
   stdio and writes result.json / trace.jsonl / manifest.json atomically into
   a fresh directory. No LLM, no API key, no engine import in the CLI: it
   talks only to the MCP tools.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from openfrontbench import benchmark

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = REPO_ROOT / "examples" / "smoke.json"

PINNED_VENDOR_COMMIT = "577819ba0e1e13ecdbc8dede2ba33de542c88a67"
SMOKE_SCENARIO = "plains-human-smoke"
START_TICK = 2
START_TROOPS = 25_000
END_DECISION_TICKS = 50

LIFECYCLE_TOOLS = {"start_smoke_game", "get_overview", "end_decision", "close_game"}
METADATA_TOOLS = {"get_pin"}


def _server_params() -> StdioServerParameters:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if p)
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "openfrontbench"],
        env=env,
        cwd=str(REPO_ROOT),
    )


@asynccontextmanager
async def _client(timeout: float = 30.0):
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout)
            yield session


async def _call(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any],
    timeout: float = 20.0,
) -> tuple[bool, str]:
    result = await asyncio.wait_for(session.call_tool(name, arguments), timeout)
    text = "\n".join(c.text for c in result.content if isinstance(c, TextContent))
    return result.isError, text


# ---------------------------------------------------------------------------
# Real MCP lifecycle session over stdio
# ---------------------------------------------------------------------------


def test_lifecycle_over_real_stdio() -> None:
    async def scenario() -> None:
        async with _client() as session:
            tools = (await asyncio.wait_for(session.list_tools(), 20.0)).tools
            names = {t.name for t in tools}
            assert names >= (LIFECYCLE_TOOLS | METADATA_TOOLS)

            start_def = next(t for t in tools if t.name == "start_smoke_game")
            assert start_def.inputSchema.get("properties") in ({}, None)
            end_def = next(t for t in tools if t.name == "end_decision")
            assert end_def.inputSchema.get("required") == ["decision"]

            is_err, start_text = await _call(session, "start_smoke_game", {})
            assert is_err is False
            start = json.loads(start_text)
            assert start["scenario"] == SMOKE_SCENARIO
            assert start["label"] == "single-human-smoke"
            assert start["tick"] == START_TICK
            assert start["decision"] == 0
            assert start["next_decision"] == 1
            assert start["human"]["troops"] == START_TROOPS

            is_err, ov_text = await _call(session, "get_overview", {})
            assert is_err is False
            overview = json.loads(ov_text)
            assert overview["tick"] == START_TICK
            assert overview["decision"] == 0

            for expected, want_tick in ((1, 52), (2, 102), (3, 152)):
                is_err, decision_text = await _call(
                    session, "end_decision", {"decision": expected}
                )
                assert is_err is False
                assert json.loads(decision_text) == {
                    "decision": expected,
                    "tick": want_tick,
                }

            is_err, ov_text = await _call(session, "get_overview", {})
            final = json.loads(ov_text)
            assert is_err is False
            assert final["tick"] == 152
            assert final["decision"] == 3
            assert final["next_decision"] == 4

            is_err, close_text = await _call(session, "close_game", {})
            assert is_err is False
            assert json.loads(close_text)["status"] == "closed"

    asyncio.run(scenario())


def test_query_is_pure_and_never_advances() -> None:
    async def scenario() -> None:
        async with _client() as session:
            await _call(session, "start_smoke_game", {})
            is_err, first_text = await _call(session, "get_overview", {})
            is_err2, second_text = await _call(session, "get_overview", {})
            assert is_err is False and is_err2 is False
            first = json.loads(first_text)
            second = json.loads(second_text)
            assert first == second
            assert first["tick"] == START_TICK

            await _call(session, "end_decision", {"decision": 1})
            is_err, after_text = await _call(session, "get_overview", {})
            after = json.loads(after_text)
            assert is_err is False
            assert after["tick"] == START_TICK + END_DECISION_TICKS
            assert after["decision"] == 1

    asyncio.run(scenario())


def test_lifecycle_tools_reject_calls_before_start() -> None:
    async def scenario() -> None:
        async with _client() as session:
            for name, args in (
                ("get_overview", {}),
                ("end_decision", {"decision": 1}),
                ("close_game", {}),
            ):
                is_err, text = await _call(session, name, args)
                assert is_err is True, f"{name} should have been rejected"
                assert "start" in text.lower() or "not started" in text.lower()
            is_err, _ = await _call(session, "start_smoke_game", {})
            assert is_err is False

    asyncio.run(scenario())


def test_duplicate_start_is_rejected() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, _ = await _call(session, "start_smoke_game", {})
            assert is_err is False
            is_err, text = await _call(session, "start_smoke_game", {})
            assert is_err is True
            assert "already" in text.lower()

    asyncio.run(scenario())


def test_end_decision_expected_decisions_reject_stale() -> None:
    async def scenario() -> None:
        async with _client() as session:
            await _call(session, "start_smoke_game", {})
            is_err, _ = await _call(session, "end_decision", {"decision": 1})
            assert is_err is False
            for stale in (1, 3, 5):
                is_err, text = await _call(session, "end_decision", {"decision": stale})
                assert is_err is True, f"stale decision {stale} must be rejected"
                assert "expected 2" in text
            is_err, _ = await _call(session, "end_decision", {"decision": 2})
            assert is_err is False
            is_err, text = await _call(session, "end_decision", {"decision": 2})
            assert is_err is True
            assert "expected 3" in text

    asyncio.run(scenario())


def test_overview_is_controlled_human_state_not_engine_internals() -> None:
    expected_human = {
        "id": "human-1",
        "name": "Agent",
        "troops": START_TROOPS,
        "gold": "0",
        "tiles": 52,
        "spawn": {"x": 50, "y": 50},
    }

    async def scenario() -> None:
        async with _client() as session:
            is_err, start_text = await _call(session, "start_smoke_game", {})
            assert is_err is False
            start = json.loads(start_text)
            assert set(start) == {
                "status",
                "scenario",
                "label",
                "tick",
                "decision",
                "next_decision",
                "in_spawn_phase",
                "winner",
                "tribes",
                "tribes_list",
                "boats",
                "units",
                "alliances",
                "alliance_requests",
                "embargoes",
                "human",
                "nations",
                "attacks",
            }
            assert start["human"] == expected_human
            assert start["nations"] == []
            assert start["attacks"] == []
            assert start["tribes"] == 0
            assert start["winner"] is None

            is_err, ov_text = await _call(session, "get_overview", {})
            assert is_err is False
            overview = json.loads(ov_text)
            assert overview["human"] == start["human"]
            assert overview["tick"] == start["tick"] == START_TICK

            for text in (start_text, ov_text):
                assert "hash" not in text
                assert "gameId" not in text
                assert "vendor" not in text
                assert "engine" not in text
                assert "worker.mjs" not in text

    asyncio.run(scenario())


def test_end_decision_rejects_non_integer_payloads_over_real_transport() -> None:
    async def scenario() -> None:
        async with _client() as session:
            is_err, _ = await _call(session, "start_smoke_game", {})
            assert is_err is False

            for payload in (
                {"decision": "1"},
                {"decision": True},
                {"decision": 1.5},
                {"decision": "1.5"},
            ):
                is_err, text = await _call(session, "end_decision", payload)
                assert is_err is True, (
                    f"{payload!r} must be rejected over the transport"
                )
                assert "stale decision" not in text

            is_err, ov_text = await _call(session, "get_overview", {})
            assert is_err is False
            assert json.loads(ov_text)["decision"] == 0

            is_err, text = await _call(session, "end_decision", {"decision": 1})
            assert is_err is False
            assert json.loads(text)["tick"] == START_TICK + END_DECISION_TICKS

            is_err, text = await _call(session, "end_decision", {"decision": "2"})
            assert is_err is True, (
                "a string equal to the expected decision must still be rejected"
            )

            is_err, text = await _call(session, "end_decision", {"decision": 2})
            assert is_err is False
            assert json.loads(text)["tick"] == START_TICK + 2 * END_DECISION_TICKS

    asyncio.run(scenario())


def _worker_pids() -> set[str]:
    if shutil.which("pgrep") is None:
        return set()
    try:
        out = subprocess.run(
            ["pgrep", "-f", "dist/worker.mjs"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    return {line.strip() for line in out.stdout.splitlines() if line.strip().isdigit()}


def _wait_until(predicate: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not reached before timeout")


def test_clean_lifespan_close_and_fresh_run_is_repeatable() -> None:
    baseline = _worker_pids()

    async def lifespans() -> tuple[int, int]:
        # First session never calls close_game: the lifespan teardown must reap
        # the engine worker on its own.
        async with _client() as session:
            await _call(session, "start_smoke_game", {})
            is_err, text = await _call(session, "end_decision", {"decision": 1})
            assert is_err is False
            first_tick = json.loads(text)["tick"]
        _wait_until(lambda: not (_worker_pids() - baseline))

        # Second session calls close_game explicitly and must be identical.
        async with _client() as session:
            await _call(session, "start_smoke_game", {})
            is_err, text = await _call(session, "end_decision", {"decision": 1})
            assert is_err is False
            second_tick = json.loads(text)["tick"]
            is_err, close_text = await _call(session, "close_game", {})
            assert is_err is False
            assert json.loads(close_text)["status"] == "closed"
        _wait_until(lambda: not (_worker_pids() - baseline))
        return first_tick, second_tick

    tick1, tick2 = asyncio.run(lifespans())
    assert tick1 == tick2 == START_TICK + END_DECISION_TICKS


# ---------------------------------------------------------------------------
# Keyless scripted-episode CLI over real stdio
# ---------------------------------------------------------------------------


def _cli(
    config: Path,
    output: Path,
    *extra: str,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if p)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "openfrontbench.benchmark",
            "--config",
            str(config),
            "--output",
            str(output),
            *extra,
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=timeout,
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_cli_full_scripted_episode_writes_artifact_trio(tmp_path: Path) -> None:
    output = tmp_path / "new"
    proc = _cli(EXAMPLE_CONFIG, output)
    assert proc.returncode == 0, proc.stderr

    result = _read_json(output / "result.json")
    assert result["schema_version"] == 1
    assert result["outcome"] == "decision_cap"
    assert result["winner"] is None
    assert result["source"] == "scripted_not_llm"
    assert result["scenario"] == SMOKE_SCENARIO
    assert result["controller"] == "scripted"
    assert result["max_decisions"] == 3
    assert result["decisions_taken"] == 3
    assert result["tick_start"] == START_TICK
    assert result["tick_end"] == 152
    assert result["tool_calls"] == 7
    assert result["tool_errors"] == 0
    metrics = result["metrics"]
    assert metrics == {}
    assert "unavailable in smoke" in result["metrics_note"]
    assert "LLM" not in result["metrics_note"], (
        "PMR/RAG are scoreable from scripted traces; smoke simply lacks "
        "strategic-query and commitment instrumentation"
    )

    trace = _read_jsonl(output / "trace.jsonl")
    events = [line["event"] for line in trace]
    assert events == [
        "episode_start",
        "tool_request",
        "tool_result",
        "tool_request",
        "tool_result",
        "tool_request",
        "tool_result",
        "tool_request",
        "tool_result",
        "tool_request",
        "tool_result",
        "tool_request",
        "tool_result",
        "tool_request",
        "tool_result",
        "episode_end",
    ]
    seqs = [line["seq"] for line in trace]
    assert seqs == list(range(1, len(trace) + 1))
    decisions = [
        line.get("decision")
        for line in trace
        if line["event"] == "tool_request" and line["tool"] == "end_decision"
    ]
    assert decisions == [1, 2, 3]
    ticks = [
        line["tick"]
        for line in trace
        if line["event"] == "tool_result" and line["tool"] == "end_decision"
    ]
    assert ticks == [52, 102, 152]

    manifest = _read_json(output / "manifest.json")
    assert manifest["schema_version"] == 1
    assert manifest["vendor_pin"]["tag"] == "v0.33.14"
    assert manifest["vendor_pin"]["expected_commit"] == PINNED_VENDOR_COMMIT
    assert manifest["vendor_pin"]["actual_commit"] == PINNED_VENDOR_COMMIT
    assert manifest["vendor_pin"]["matches"] is True
    assert len(manifest["engine_bundle"]["sha256"]) == 64
    assert len(manifest["map_assets"]) == 3
    for key in ("config_sha256", "trace_sha256", "result_sha256"):
        assert len(manifest[key]) == 64


def test_cli_artifacts_repeatable_across_output_paths(tmp_path: Path) -> None:
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    first = _cli(EXAMPLE_CONFIG, out1)
    second = _cli(EXAMPLE_CONFIG, out2)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    for name in ("result.json", "trace.jsonl", "manifest.json"):
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes(), name


def test_cli_refuses_existing_output_dir(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    (output / "sentinel.txt").write_text("x", encoding="utf-8")
    proc = _cli(EXAMPLE_CONFIG, output)
    assert proc.returncode != 0
    assert "already exists" in proc.stderr
    assert (output / "sentinel.txt").exists()


def test_cli_tool_timeout_writes_failure_artefact_and_exits_nonzero(
    tmp_path: Path,
) -> None:
    output = tmp_path / "fail"
    proc = _cli(EXAMPLE_CONFIG, output, "--tool-timeout", "0.05")
    assert proc.returncode != 0
    trace = _read_jsonl(output / "trace.jsonl")
    errors = [line for line in trace if line["event"] == "tool_error"]
    assert any(
        line["tool"] == "start_smoke_game" and "timed out" in line["error"]
        for line in errors
    )
    result = _read_json(output / "result.json")
    assert result["outcome"] == "error"
    assert result["tool_errors"] >= 1


BAD_CONFIGS: list[tuple[str, object]] = [
    ("raw-text-not-json", "this is not json at all"),
    ("array-not-object", [1, 2, 3]),
    ("missing-fields", {"version": 1}),
    (
        "unknown-field",
        {
            "version": 1,
            "scenario": "plains-human-smoke",
            "controller": "scripted",
            "max_decisions": 3,
            "extra": True,
        },
    ),
    (
        "bool-version",
        {
            "version": True,
            "scenario": "plains-human-smoke",
            "controller": "scripted",
            "max_decisions": 3,
        },
    ),
    (
        "wrong-version",
        {
            "version": 2,
            "scenario": "plains-human-smoke",
            "controller": "scripted",
            "max_decisions": 3,
        },
    ),
    (
        "unsupported-scenario",
        {
            "version": 1,
            "scenario": "box-small-2nations",
            "controller": "scripted",
            "max_decisions": 3,
        },
    ),
    (
        "unsupported-controller",
        {
            "version": 1,
            "scenario": "plains-human-smoke",
            "controller": "llm",
            "max_decisions": 3,
        },
    ),
    (
        "bool-max-decisions",
        {
            "version": 1,
            "scenario": "plains-human-smoke",
            "controller": "scripted",
            "max_decisions": True,
        },
    ),
    (
        "max-decisions-too-low",
        {
            "version": 1,
            "scenario": "plains-human-smoke",
            "controller": "scripted",
            "max_decisions": 0,
        },
    ),
    (
        "max-decisions-too-high",
        {
            "version": 1,
            "scenario": "plains-human-smoke",
            "controller": "scripted",
            "max_decisions": 1001,
        },
    ),
]


def test_cli_rejects_invalid_configs_without_touching_output(tmp_path: Path) -> None:
    output = tmp_path / "out"
    for index, (label, payload) in enumerate(BAD_CONFIGS):
        cfg = tmp_path / f"bad-{index}.json"
        if isinstance(payload, str):
            cfg.write_text(payload, encoding="utf-8")
        else:
            cfg.write_text(json.dumps(payload), encoding="utf-8")
        proc = _cli(cfg, output)
        assert proc.returncode != 0, f"{label}: expected a nonzero exit"
        assert not output.exists(), f"{label}: output dir was created"


BAD_TIMEOUTS: list[tuple[str, str]] = [
    ("--tool-timeout", "nan"),
    ("--tool-timeout", "inf"),
    ("--tool-timeout", "-inf"),
    ("--tool-timeout", "0"),
    ("--tool-timeout", "-1"),
    ("--connect-timeout", "nan"),
    ("--connect-timeout", "inf"),
    ("--connect-timeout", "0"),
]


def test_cli_rejects_non_finite_or_non_positive_timeouts(tmp_path: Path) -> None:
    for index, pair in enumerate(BAD_TIMEOUTS):
        output = tmp_path / f"out-{index}"
        proc = _cli(EXAMPLE_CONFIG, output, *pair)
        assert proc.returncode != 0, pair
        assert "timeout" in proc.stderr.lower(), pair
        assert not output.exists(), pair


# ---------------------------------------------------------------------------
# Unit-level guarantees behind the CLI contract
# ---------------------------------------------------------------------------


def test_timeout_validation_rejects_non_finite_and_non_positive() -> None:
    assert benchmark._positive_finite(None, 5.0) == 5.0
    assert benchmark._positive_finite(0.05, 5.0) == 0.05
    for bad in (0.0, -1.0, float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            benchmark._positive_finite(bad, 5.0)


def test_parse_config_accepts_valid_and_bounds() -> None:
    base = {
        "version": 1,
        "scenario": "plains-human-smoke",
        "controller": "scripted",
    }
    assert (
        benchmark.parse_episode_config({**base, "max_decisions": 1}).max_decisions == 1
    )
    assert (
        benchmark.parse_episode_config({**base, "max_decisions": 1000}).max_decisions
        == 1000
    )
    for bad in (0, 1001, True):
        with pytest.raises(benchmark.ConfigError):
            benchmark.parse_episode_config({**base, "max_decisions": bad})
    with pytest.raises(benchmark.ConfigError):
        benchmark.parse_episode_config(
            {
                "version": True,
                "scenario": "plains-human-smoke",
                "controller": "scripted",
                "max_decisions": 3,
            }
        )
    with pytest.raises(benchmark.ConfigError):
        benchmark.parse_episode_config({**base, "max_decisions": 3, "extra": 1})


def test_atomic_write_leaves_no_temp_and_survives_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "result.json"
    benchmark.write_json_atomic(target, {"a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    assert list(tmp_path.glob(".*.tmp")) == []

    def crash_replace(*args: Any, **kwargs: Any) -> None:
        raise OSError("simulated crash during rename")

    monkeypatch.setattr(benchmark.os, "replace", crash_replace)
    target2 = tmp_path / "result2.json"
    with pytest.raises(OSError):
        benchmark.write_json_atomic(target2, {"b": 2})
    assert not target2.exists()


def _tiny_smoke_config(tmp_path: Path) -> Path:
    path = tmp_path / "smoke.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "scenario": "plains-human-smoke",
                "controller": "scripted",
                "max_decisions": 1,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_run_episode_exits_nonzero_on_vendor_pin_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "openfrontbench.episodes.smoke._actual_vendor_pin", lambda: "0" * 40
    )
    cfg = _tiny_smoke_config(tmp_path)
    output = tmp_path / "out"
    outcome = benchmark.run_episode(
        benchmark.load_episode_config(cfg),
        cfg,
        output,
        tool_timeout=30.0,
        connect_timeout=10.0,
    )
    assert outcome.exit_code != 0
    result = _read_json(output / "result.json")
    assert result["outcome"] == "error"
    assert "vendor pin mismatch" in result["reason"]
    manifest = _read_json(output / "manifest.json")
    assert manifest["vendor_pin"]["matches"] is False
    assert manifest["vendor_pin"]["actual_commit"] == "0" * 40


def test_run_episode_exits_nonzero_on_manifest_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(label: str, path: Path) -> dict[str, Any]:
        raise benchmark.EpisodeError(f"manifest asset not found: {label}")

    monkeypatch.setattr(benchmark, "_file_asset", boom)
    cfg = _tiny_smoke_config(tmp_path)
    output = tmp_path / "out"
    outcome = benchmark.run_episode(
        benchmark.load_episode_config(cfg),
        cfg,
        output,
        tool_timeout=30.0,
        connect_timeout=10.0,
    )
    assert outcome.exit_code != 0
    result = _read_json(output / "result.json")
    # The sealed result is frozen: a manifest failure must not rewrite it.
    # The episode itself succeeded, so outcome stays decision_cap and the
    # trace's episode_end agrees (no trio contradiction).
    assert result["outcome"] == "decision_cap"
    trace = _read_jsonl(output / "trace.jsonl")
    episode_end = [line for line in trace if line["event"] == "episode_end"]
    assert len(episode_end) == 1
    assert episode_end[0]["outcome"] == result["outcome"]
    manifest = _read_json(output / "manifest.json")
    assert manifest["schema_version"] == 1
    assert "manifest asset not found" in manifest["error"]
