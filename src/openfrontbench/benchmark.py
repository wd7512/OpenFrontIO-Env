"""Keyless episode CLI over a real MCP stdio server.

``python -m openfrontbench.benchmark --config <json> --output <dir>`` runs an
episode (start, overview, decisions, overview, close) against the packaged
MCP server over a real stdio transport, then writes ``result.json``,
``trace.jsonl`` and ``manifest.json`` atomically into a fresh output
directory. No LLM and no API key: the driver script makes every decision,
and every tool request/result/error is traced in order with its decision
id and simulation tick.

Process lives here; domain specifics arrive via an ``EpisodeDriver`` (see
``openfrontbench.episodes``). The default driver is the pinned single-human
smoke episode (``episodes.smoke.SMOKE_DRIVER``) — the single worked example.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from openfrontbench.atomic import (
    OutputExistsError,
    ensure_fresh_dir,
    write_json_atomic as _write_json_atomic,
    write_text_atomic as _write_text_atomic,
)
from openfrontbench.episodes import EpisodeDriver
from openfrontbench.episodes.smoke import SMOKE_DRIVER
from openfrontbench.paths import REPO_ROOT

log = logging.getLogger(__name__)
CONFIG_KEYS = frozenset({"version", "scenario", "controller", "max_decisions"})
SCHEMA_VERSION = 1
MAX_DECISIONS_MIN = 1
MAX_DECISIONS_MAX = 1000
DEFAULT_TOOL_TIMEOUT_S = 60.0
DEFAULT_CONNECT_TIMEOUT_S = 10.0


class ConfigError(ValueError):
    """The episode config violates the strict JSON schema."""


class OutputError(OutputExistsError):
    """The requested output path is unusable.

    Migration note: this was a ``RuntimeError`` before the atomic-write
    dedup; it is now a ``FileExistsError`` (via ``OutputExistsError``),
    so ``except RuntimeError`` no longer catches fresh-dir refusals —
    catch ``OutputError``, ``OSError``, or ``ValueError`` instead.
    """


class EpisodeError(RuntimeError):
    """A tool call failed or timed out during the scripted episode."""


@dataclass(frozen=True)
class EpisodeConfig:
    scenario: str
    controller: str
    max_decisions: int


@dataclass(frozen=True)
class RunOutcome:
    exit_code: int
    result: dict[str, Any]


def load_episode_config(path: Path) -> EpisodeConfig:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"cannot read config {path}: {error}") from error
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ConfigError(f"config is not valid JSON: {error}") from error
    return parse_episode_config(data)


def parse_episode_config(
    data: object, driver: EpisodeDriver = SMOKE_DRIVER
) -> EpisodeConfig:
    """Validate a config dict against the core schema plus driver sets."""
    if isinstance(data, bool) or not isinstance(data, dict):
        raise ConfigError("config must be a JSON object")
    raw = cast(dict[str, Any], data)
    unknown = set(raw) - CONFIG_KEYS
    if unknown:
        raise ConfigError(f"unknown config field(s): {sorted(unknown)}")
    missing = CONFIG_KEYS - set(raw)
    if missing:
        raise ConfigError(f"missing config field(s): {sorted(missing)}")

    version = raw["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise ConfigError("version must be the integer 1")
    if version != SCHEMA_VERSION:
        raise ConfigError(
            f"unsupported config version {version!r}; expected {SCHEMA_VERSION}"
        )

    scenario = raw["scenario"]
    if not isinstance(scenario, str):
        raise ConfigError("scenario must be a string")
    if scenario not in driver.allowed_scenarios:
        raise ConfigError(
            f"unsupported scenario {scenario!r}; "
            f"supported: {sorted(driver.allowed_scenarios)}"
        )

    controller = raw["controller"]
    if not isinstance(controller, str):
        raise ConfigError("controller must be a string")
    if controller not in driver.allowed_controllers:
        raise ConfigError(
            f"unsupported controller {controller!r}; "
            f"supported: {sorted(driver.allowed_controllers)}"
        )

    max_decisions = raw["max_decisions"]
    if isinstance(max_decisions, bool) or not isinstance(max_decisions, int):
        raise ConfigError("max_decisions must be an integer")
    if not (MAX_DECISIONS_MIN <= max_decisions <= MAX_DECISIONS_MAX):
        raise ConfigError(
            f"max_decisions must be between {MAX_DECISIONS_MIN} and {MAX_DECISIONS_MAX}"
        )
    return EpisodeConfig(
        scenario=scenario,
        controller=controller,
        max_decisions=max_decisions,
    )


# ---------------------------------------------------------------------------
# Manifest hashing, atomic writes, trace writer
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text_atomic(path: Path, text: str) -> Path:
    return _write_text_atomic(path, text)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> Path:
    return _write_json_atomic(path, payload)


class TraceWriter:
    """Appends one JSON object per line to an atomic trace file.

    Streaming variant of :func:`openfrontbench.atomic.write_text_atomic`:
    same hidden-tmp + flush/fsync + ``os.replace`` scheme, kept separate
    because the trace is written incrementally, not in one shot.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._tmp = path.with_name(f".{path.name}.tmp")
        self._file = self._tmp.open("w", encoding="utf-8")
        self._seq = 0

    def emit(self, **fields: Any) -> int:
        self._seq += 1
        self._file.write(
            json.dumps({"seq": self._seq, **fields}, sort_keys=True) + "\n"
        )
        return self._seq

    def finalize(self) -> None:
        self._file.flush()
        os.fsync(self._file.fileno())
        self._file.close()
        os.replace(self._tmp, self._path)


def _file_asset(label: str, path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise EpisodeError(f"manifest asset not found: {label} ({path})")
    return {
        "label": label,
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
    }


def build_manifest(
    config_bytes: bytes,
    trace_path: Path,
    result_path: Path,
    driver: EpisodeDriver,
    actual_pin: str | None,
) -> dict[str, Any]:
    """Hash config/trace/result plus the driver's pinned artifacts."""
    assets = [_file_asset(label, path) for label, path in driver.map_assets]
    return {
        "schema_version": SCHEMA_VERSION,
        "vendor_pin": {
            "tag": driver.vendor_tag,
            "expected_commit": driver.vendor_pin,
            "actual_commit": actual_pin,
            "matches": actual_pin is not None and actual_pin == driver.vendor_pin,
        },
        "engine_bundle": _file_asset(
            driver.engine_bundle_rel, driver.engine_bundle_path
        ),
        "map_assets": assets,
        "config_sha256": _sha256_bytes(config_bytes),
        "trace_sha256": _sha256_file(trace_path),
        "result_sha256": _sha256_file(result_path),
    }


# ---------------------------------------------------------------------------
# Episode run over a real stdio MCP session (driver supplies the script)
# ---------------------------------------------------------------------------


async def _call_tool(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any],
    timeout: float,
) -> dict[str, Any] | None:
    try:
        result = await asyncio.wait_for(session.call_tool(name, arguments), timeout)
    except TimeoutError as error:
        raise EpisodeError(f"tool call {name} timed out after {timeout:g}s") from error
    text = "".join(c.text for c in result.content if isinstance(c, TextContent)).strip()
    if result.isError:
        raise EpisodeError(f"tool {name} failed: {text or '(no message)'}")
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"unparsed": text}
    return parsed if isinstance(parsed, dict) else None


def _trace_tool_read(trace: TraceWriter, name: str, args: dict[str, Any]) -> None:
    expected_decision = args.get("decision")
    trace.emit(
        event="tool_request",
        tool=name,
        decision=expected_decision,
        tick=None,
        arguments=args,
    )


def _trace_tool_write(
    trace: TraceWriter, name: str, parsed: dict[str, Any] | None
) -> None:
    decision = parsed.get("decision") if parsed else None
    tick = parsed.get("tick") if parsed else None
    trace.emit(
        event="tool_result",
        tool=name,
        decision=decision,
        tick=tick,
        result=parsed,
    )


def _new_stats() -> dict[str, Any]:
    """Fresh per-episode counters (no shared mutable state)."""
    return {
        "tool_calls": 0,
        "tool_errors": 0,
        "decisions_taken": 0,
        "tick_start": None,
        "tick_end": None,
        "errors": [],
    }


def _open_session(driver: EpisodeDriver) -> StdioServerParameters:
    """Build stdio params for the driver's server module (no side effects)."""
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if p)
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", driver.server_module],
        env=env,
        cwd=str(REPO_ROOT),
    )


def _record_tick(
    stats: dict[str, Any],
    parsed: dict[str, Any] | None,
    name: str,
    driver: EpisodeDriver,
) -> None:
    """Fold one tool result's tick/decision counts into *stats*."""
    if not parsed:
        return
    tick = parsed.get("tick")
    if isinstance(tick, int):
        if stats["tick_start"] is None:
            stats["tick_start"] = tick
        stats["tick_end"] = tick
    if name == driver.decision_tool:
        stats["decisions_taken"] += 1


async def _execute_step(
    session: ClientSession,
    trace: TraceWriter,
    stats: dict[str, Any],
    name: str,
    args: dict[str, Any],
    tool_timeout: float,
    driver: EpisodeDriver,
) -> bool:
    """Run one scripted tool step; return False when the episode must stop."""
    _trace_tool_read(trace, name, args)
    stats["tool_calls"] += 1
    try:
        parsed = await _call_tool(session, name, args, tool_timeout)
    except EpisodeError as error:
        stats["tool_errors"] += 1
        stats["errors"].append(str(error))
        trace.emit(
            event="tool_error",
            tool=name,
            decision=args.get("decision"),
            tick=None,
            error=str(error),
        )
        return False
    _trace_tool_write(trace, name, parsed)
    _record_tick(stats, parsed, name, driver)
    return True


async def _run_scripted(
    config: EpisodeConfig,
    trace: TraceWriter,
    tool_timeout: float,
    connect_timeout: float,
    driver: EpisodeDriver,
) -> dict[str, Any]:
    stats = _new_stats()
    params = _open_session(driver)
    steps = driver.build_steps(config.max_decisions)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), connect_timeout)
            for name, args in steps:
                if not await _execute_step(
                    session, trace, stats, name, args, tool_timeout, driver
                ):
                    break
    return stats


# ---------------------------------------------------------------------------
# Episode orchestration and CLI entry point
# ---------------------------------------------------------------------------


def _build_result(
    config: EpisodeConfig,
    stats: dict[str, Any],
    problems: list[str],
    driver: EpisodeDriver,
) -> dict[str, Any]:
    errors = stats["errors"]
    if errors:
        outcome, reason = "error", str(errors[0])
    elif problems:
        outcome, reason = "error", problems[0]
    else:
        outcome, reason = "decision_cap", driver.completion_reason
    return {
        "schema_version": SCHEMA_VERSION,
        "outcome": outcome,
        "reason": reason,
        "winner": driver.winner,
        "metrics": dict(driver.metrics),
        "metrics_note": driver.metrics_note,
        "source": driver.source,
        "scenario": config.scenario,
        "controller": config.controller,
        "max_decisions": config.max_decisions,
        "decisions_taken": stats["decisions_taken"],
        "tick_start": stats["tick_start"],
        "tick_end": stats["tick_end"],
        "tool_calls": stats["tool_calls"],
        "tool_errors": stats["tool_errors"],
    }


def _write_result(output: Path, result: dict[str, Any]) -> None:
    write_text_atomic(
        output / "result.json", json.dumps(result, indent=2, sort_keys=True) + "\n"
    )


def _ensure_output(output: Path, config_path: Path) -> bytes:
    """Create a fresh output dir; return the config bytes.

    Only raises ``OutputError``.
    """
    try:
        ensure_fresh_dir(output)
        return config_path.read_bytes()
    except OutputExistsError as error:
        raise OutputError(str(error)) from error
    except OSError as error:
        raise OutputError(f"cannot prepare output {output}: {error}") from error


def _finalize_episode(
    config: EpisodeConfig,
    stats: dict[str, Any],
    probe_problems: list[str],
    trace: TraceWriter,
    output: Path,
    config_bytes: bytes,
    driver: EpisodeDriver,
    actual_pin: str | None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Build result, seal trace, write artifacts; result is frozen once.

    A manifest failure appends to *problems* (for the exit code) and yields
    an error manifest — it never rebuilds an already-sealed ``result.json``,
    so ``trace.jsonl`` and ``result.json`` cannot contradict each other.
    """
    problems = list(probe_problems)
    result = _build_result(config, stats, problems, driver)
    trace.emit(
        event="episode_end",
        outcome=result["outcome"],
        decision=result["decisions_taken"],
        tick=result["tick_end"],
    )
    trace.finalize()
    _write_result(output, result)
    try:
        manifest = build_manifest(
            config_bytes,
            output / "trace.jsonl",
            output / "result.json",
            driver,
            actual_pin,
        )
    except EpisodeError as error:
        log.error("manifest error: %s", error)
        problems.append(f"manifest build failed: {error}")
        manifest = {"schema_version": SCHEMA_VERSION, "error": str(error)}
    write_json_atomic(output / "manifest.json", manifest)
    return result, manifest, problems


def run_episode(
    config: EpisodeConfig,
    config_path: Path,
    output: Path,
    *,
    tool_timeout: float,
    connect_timeout: float,
    driver: EpisodeDriver = SMOKE_DRIVER,
) -> RunOutcome:
    if not (
        math.isfinite(tool_timeout)
        and tool_timeout > 0
        and math.isfinite(connect_timeout)
        and connect_timeout > 0
    ):
        raise ValueError(
            "tool_timeout and connect_timeout must be finite positive numbers"
        )
    config_bytes = _ensure_output(output, config_path)

    trace = TraceWriter(output / "trace.jsonl")
    stats: dict[str, Any] = _new_stats()
    result: dict[str, Any] = {"outcome": "error"}
    try:
        trace.emit(
            event="episode_start",
            scenario=config.scenario,
            controller=config.controller,
            max_decisions=config.max_decisions,
        )
        try:
            stats = asyncio.run(
                _run_scripted(config, trace, tool_timeout, connect_timeout, driver)
            )
        except Exception as error:  # last-resort failure artefact
            log.exception("unexpected episode failure")
            stats["errors"].append(f"unexpected failure: {error}")
            trace.emit(event="episode_error", error=f"unexpected failure: {error}")
    finally:
        actual_pin, probe_issues = driver.probe_issues()
        result, _manifest, problems = _finalize_episode(
            config,
            stats,
            list(probe_issues),
            trace,
            output,
            config_bytes,
            driver,
            actual_pin,
        )

    healthy = (
        result["outcome"] == "decision_cap"
        and result["tool_errors"] == 0
        and not problems
    )
    return RunOutcome(exit_code=0 if healthy else 1, result=result)


def _positive_finite(value: float | None, default: float) -> float:
    """Coerce a user-supplied timeout to a finite positive number."""
    chosen = default if value is None else float(value)
    if not math.isfinite(chosen) or chosen <= 0:
        raise ValueError(f"{value!r} must be a finite positive number")
    return chosen


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        prog="python -m openfrontbench.benchmark",
        description="Run a keyless episode over real MCP stdio "
        "(default driver: smoke episode).",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="strict JSON episode config (see examples/smoke.json)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="fresh output directory (refuses to overwrite)",
    )
    parser.add_argument(
        "--tool-timeout",
        type=float,
        default=DEFAULT_TOOL_TIMEOUT_S,
        help="per-tool-call timeout in seconds",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=DEFAULT_CONNECT_TIMEOUT_S,
        help="MCP initialize handshake timeout in seconds",
    )
    args = parser.parse_args(argv)

    try:
        tool_timeout = _positive_finite(args.tool_timeout, DEFAULT_TOOL_TIMEOUT_S)
        connect_timeout = _positive_finite(
            args.connect_timeout, DEFAULT_CONNECT_TIMEOUT_S
        )
    except ValueError as error:
        log.error("timeout error: %s", error)
        return 2

    config_path = Path(args.config)
    try:
        config = load_episode_config(config_path)
    except ConfigError as error:
        log.error("config error: %s", error)
        return 2

    try:
        outcome = run_episode(
            config,
            config_path,
            Path(args.output),
            tool_timeout=tool_timeout,
            connect_timeout=connect_timeout,
        )
    except (OutputError, ValueError) as error:
        log.error("%s", error)
        return 2

    log.info(
        "episode complete: outcome=%s exit=%d output=%s",
        outcome.result["outcome"],
        outcome.exit_code,
        Path(args.output),
    )
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(main())
