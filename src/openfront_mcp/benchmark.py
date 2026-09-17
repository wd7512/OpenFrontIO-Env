"""Keyless scripted-episode CLI over the real MCP stdio server.

``python -m openfront_mcp.benchmark --config <json> --output <dir>`` runs the
pinned single-human smoke episode (start, overview, ``end_decision`` x N,
overview, close) against the packaged MCP server over a real stdio transport,
then writes ``result.json``, ``trace.jsonl`` and ``manifest.json`` atomically
into a fresh output directory. No LLM and no API key: the ``scripted``
controller makes every decision, and every tool request/result/error is traced
in order with its decision id and simulation tick.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from openfront_mcp import pins as _pins
from openfront_mcp.engine import DEFAULT_ENGINE_DIR, PLAINS_MAP_DIR
from openfront_mcp.session import SMOKE_SCENARIO

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_KEYS = frozenset({"version", "scenario", "controller", "max_decisions"})
ALLOWED_SCENARIOS = frozenset({SMOKE_SCENARIO})
ALLOWED_CONTROLLERS = frozenset({"scripted"})
SCHEMA_VERSION = 1
MAX_DECISIONS_MIN = 1
MAX_DECISIONS_MAX = 1000
DEFAULT_TOOL_TIMEOUT_S = 60.0
DEFAULT_CONNECT_TIMEOUT_S = 10.0

ENGINE_BUNDLE_REL = "engine/dist/worker.mjs"
MAP_ASSET_DIR = "vendor/OpenFrontIO/tests/testdata/maps/plains"
MAP_ASSET_NAMES = ("manifest.json", "map.bin", "map4x.bin")


class ConfigError(ValueError):
    """The episode config violates the strict JSON schema."""


class OutputError(RuntimeError):
    """The requested output path is unusable."""


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


def parse_episode_config(data: object) -> EpisodeConfig:
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
    if scenario not in ALLOWED_SCENARIOS:
        raise ConfigError(
            f"unsupported scenario {scenario!r}; supported: {sorted(ALLOWED_SCENARIOS)}"
        )

    controller = raw["controller"]
    if not isinstance(controller, str):
        raise ConfigError("controller must be a string")
    if controller not in ALLOWED_CONTROLLERS:
        raise ConfigError(
            f"unsupported controller {controller!r}; supported: {sorted(ALLOWED_CONTROLLERS)}"
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


def write_text_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


class TraceWriter:
    """Appends one JSON object per line to an atomic trace file."""

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


def _actual_vendor_pin() -> str | None:
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(REPO_ROOT / "vendor" / "OpenFrontIO"),
                "rev-parse",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value if value else None


def _manifest_probe() -> tuple[str | None, list[str]]:
    """Check pinned-artifact integrity before writing results.

    Returns ``(actual_pin, issues)`` where ``issues`` is empty only when the
    engine bundle, map assets and the vendored core all check out.
    """
    issues: list[str] = []
    if not (DEFAULT_ENGINE_DIR / "dist" / "worker.mjs").is_file():
        issues.append(f"engine bundle missing: {ENGINE_BUNDLE_REL}")
    for name in MAP_ASSET_NAMES:
        if not (PLAINS_MAP_DIR / name).is_file():
            issues.append(f"map asset missing: {MAP_ASSET_DIR}/{name}")
    actual = _actual_vendor_pin()
    if actual is None:
        issues.append("cannot verify vendor pin (git unavailable)")
    elif actual != _pins.VENDOR_PIN:
        issues.append(
            f"vendor pin mismatch: expected {_pins.VENDOR_PIN}, actual {actual}"
        )
    return actual, issues


def build_manifest(
    config_bytes: bytes,
    trace_path: Path,
    result_path: Path,
    actual_pin: str | None,
) -> dict[str, Any]:
    engine_path = DEFAULT_ENGINE_DIR / "dist" / "worker.mjs"
    map_dir = PLAINS_MAP_DIR
    assets = [
        _file_asset(f"{MAP_ASSET_DIR}/{name}", map_dir / name)
        for name in MAP_ASSET_NAMES
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "vendor_pin": {
            "tag": _pins.VENDOR_TAG,
            "expected_commit": _pins.VENDOR_PIN,
            "actual_commit": actual_pin,
            "matches": actual_pin is not None and actual_pin == _pins.VENDOR_PIN,
        },
        "engine_bundle": _file_asset(ENGINE_BUNDLE_REL, engine_path),
        "map_assets": assets,
        "config_sha256": _sha256_bytes(config_bytes),
        "trace_sha256": _sha256_file(trace_path),
        "result_sha256": _sha256_file(result_path),
    }


# ---------------------------------------------------------------------------
# Scripted episode over a real stdio MCP session
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


async def _run_scripted(
    config: EpisodeConfig,
    trace: TraceWriter,
    tool_timeout: float,
    connect_timeout: float,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "tool_calls": 0,
        "tool_errors": 0,
        "decisions_taken": 0,
        "tick_start": None,
        "tick_end": None,
        "errors": [],
    }
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if p)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "openfront_mcp"],
        env=env,
        cwd=str(REPO_ROOT),
    )
    steps: list[tuple[str, dict[str, Any]]] = [
        ("start_smoke_game", {}),
        ("get_overview", {}),
    ]
    steps.extend(
        ("end_decision", {"decision": n}) for n in range(1, config.max_decisions + 1)
    )
    steps.extend([("get_overview", {}), ("close_game", {})])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), connect_timeout)
            for name, args in steps:
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
                    break
                _trace_tool_write(trace, name, parsed)
                if not parsed:
                    continue
                tick = parsed.get("tick")
                if isinstance(tick, int):
                    if stats["tick_start"] is None:
                        stats["tick_start"] = tick
                    stats["tick_end"] = tick
                if name == "end_decision":
                    stats["decisions_taken"] += 1
    return stats


# ---------------------------------------------------------------------------
# Episode orchestration and CLI entry point
# ---------------------------------------------------------------------------


def _build_result(
    config: EpisodeConfig, stats: dict[str, Any], problems: list[str]
) -> dict[str, Any]:
    errors = stats["errors"]
    if errors:
        outcome, reason = "error", str(errors[0])
    elif problems:
        outcome, reason = "error", problems[0]
    else:
        outcome, reason = "decision_cap", "scripted maximum decisions reached"
    return {
        "schema_version": SCHEMA_VERSION,
        "outcome": outcome,
        "reason": reason,
        "winner": None,
        "metrics": {
            "PMR": None,
            "RAG_at_10": None,
            "unavailable_reason": (
                "unavailable in smoke: the scripted controller records no "
                "strategic-query or commitment events, so PMR (proactive "
                "monitoring rate) and RAG@10 (reflection-action gap) cannot be "
                "scored from this trace"
            ),
        },
        "source": "scripted_not_llm",
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


def run_episode(
    config: EpisodeConfig,
    config_path: Path,
    output: Path,
    *,
    tool_timeout: float,
    connect_timeout: float,
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
    if output.exists():
        raise OutputError(
            f"output path already exists (refusing to overwrite): {output}"
        )
    try:
        output.mkdir(parents=True)
        config_bytes = config_path.read_bytes()
    except OSError as error:
        raise OutputError(f"cannot prepare output {output}: {error}") from error

    trace = TraceWriter(output / "trace.jsonl")
    stats: dict[str, Any] = {
        "tool_calls": 0,
        "tool_errors": 0,
        "decisions_taken": 0,
        "tick_start": None,
        "tick_end": None,
        "errors": [],
    }
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
                _run_scripted(config, trace, tool_timeout, connect_timeout)
            )
        except Exception as error:  # last-resort failure artefact
            log.exception("unexpected episode failure")
            stats["errors"].append(f"unexpected failure: {error}")
            trace.emit(event="episode_error", error=f"unexpected failure: {error}")
    finally:
        actual_pin, probe_issues = _manifest_probe()
        problems = list(probe_issues)
        result = _build_result(config, stats, problems)
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
                actual_pin,
            )
        except EpisodeError as error:
            log.error("manifest error: %s", error)
            problems.append(f"manifest build failed: {error}")
            result = _build_result(config, stats, problems)
            _write_result(output, result)
            manifest = {"schema_version": SCHEMA_VERSION, "error": str(error)}
        write_json_atomic(output / "manifest.json", manifest)

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
        prog="python -m openfront_mcp.benchmark",
        description="Run a keyless scripted smoke episode over real MCP stdio.",
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
