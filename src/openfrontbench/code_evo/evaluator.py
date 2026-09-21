"""Headless N-spawn evaluator for code-evo candidates.

Runs one policy module over every fixed spawn in the registry with no
LLM in the loop (``overview -> decide -> apply -> end_decision``) until
a winner is declared, the human is eliminated, or ``max_ticks`` is hit.
Scores territory + survival per spawn and aggregates across spawns.
Spawns run sequentially by default; ``jobs > 1`` fans them out over
spawn-context worker processes (one engine worker each, per-process
tape routing — threads would share ``OPENFRONT_RECORD_DIR``).
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import multiprocessing
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from openfrontbench.atomic import ensure_fresh_dir, write_json_atomic
from openfrontbench.code_evo.spawns import Spawn, SpawnRegistry
from openfrontbench.experiment import write_experiment
from openfrontbench.paths import REPO_ROOT
from openfrontbench.policies.base import apply_orders
from openfrontbench.run_summary import build_summary, write_summary
from openfrontbench.session import DECISION_TICKS, GameSession

log = logging.getLogger(__name__)

MAX_TICKS = 100_000
HUMAN_NAME = "Agent"
WIN_BONUS = 500_000
SURVIVAL_WEIGHT = 5
MAX_CONSECUTIVE_ERRORS = 5


@dataclass(frozen=True)
class EvalConfig:
    nations: int = 52
    tribes: int = 400
    difficulty: str = "medium"
    max_ticks: int = MAX_TICKS
    decision_ticks: int = DECISION_TICKS


@dataclass(frozen=True)
class EpisodeResult:
    spawn_id: str
    ticks: int
    decisions: int
    tiles_peak: int
    final_tiles: int
    final_troops: int
    winner: str | None
    policy_errors: int
    score: float
    spawn_tile: tuple[int, int] | None = None
    game_id: str | None = None
    troops_peak: int = 0
    gold_peak: float = 0.0
    city_ever: bool = False
    outcome: str = "unknown"


@dataclass
class CandidateReport:
    policy_sha256: str
    episodes: list[EpisodeResult] = field(default_factory=list)


class PolicyError(RuntimeError):
    """The candidate policy module is missing or unusable."""


def load_policy(path: Path) -> Any:
    """Import *path* and return an ``EvolvingPolicy()`` instance."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PolicyError(f"cannot read policy {path}: {error}") from error
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    name = f"candidate_{digest[:12]}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PolicyError(f"cannot import policy {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise PolicyError(f"policy import failed: {error}") from error
    factory = getattr(module, "EvolvingPolicy", None)
    if factory is None:
        raise PolicyError("policy has no EvolvingPolicy class")
    try:
        policy = factory()
    except Exception as error:
        raise PolicyError(f"policy construction failed: {error}") from error
    if not callable(getattr(policy, "decide", None)):
        raise PolicyError("policy EvolvingPolicy has no decide method")
    return policy


BANNED_TS_PATTERNS: tuple[str, ...] = (
    "Math.random",
    "Date.now",
    "performance.now",
    "process.",
    "require(",
    "node:",
    "child_process",
    "fetch(",
    "Worker(",
    "importScripts",
    "eval(",
)
# P0 policies must be self-contained: any line whose left-stripped text
# starts with "import " is rejected alongside BANNED_TS_PATTERNS, so the
# candidate cannot pull in node builtins or files outside its markers.


@dataclass(frozen=True)
class EnginePolicy:
    """A validated TS policy that only decides inside the engine worker."""

    source: Path
    bundle: Path
    sha256: str
    in_engine: bool = True

    def decide(self, _overview: dict[str, Any]) -> Any:
        raise PolicyError("EnginePolicy cannot decide in Python")


def validate_ts_source(text: str, path: Path) -> None:
    """Check TS markers, interface and banned patterns without bundling."""
    if text.count("// EVOLVE-START") != 1 or text.count("// EVOLVE-END") != 1:
        raise PolicyError("TS policy must contain exactly one EVOLVE block")
    if text.index("// EVOLVE-START") > text.index("// EVOLVE-END"):
        raise PolicyError("TS policy must contain exactly one EVOLVE block")
    if "class EvolvingPolicy" not in text or "decide(" not in text:
        raise PolicyError("TS policy has no EvolvingPolicy class with decide")
    # Only the agent-editable EVOLVE block is scanned: the header comment
    # names banned APIs to forbid them, and the harness scaffolding below
    # the markers is trusted (not agent-editable).
    block = text.split("// EVOLVE-START", 1)[1].split("// EVOLVE-END", 1)[0]
    for pattern in BANNED_TS_PATTERNS:
        if pattern in block:
            raise PolicyError(f"TS policy uses banned pattern {pattern!r}")
    for line in block.splitlines():
        if line.lstrip().startswith("import "):
            raise PolicyError("TS policy uses banned pattern 'import '")


def load_ts_policy(path: Path) -> EnginePolicy:
    """Validate a TS policy and bundle it to ESM with esbuild."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PolicyError(f"cannot read TS policy {path}: {error}") from error
    validate_ts_source(text, path)
    esbuild = REPO_ROOT / "engine" / "node_modules" / ".bin" / "esbuild"
    if not esbuild.is_file():
        raise PolicyError(f"esbuild not found: {esbuild}")
    bundle = path.with_name(path.stem + ".bundle.mjs")
    proc = subprocess.run(
        [
            str(esbuild),
            str(path),
            "--bundle",
            "--platform=node",
            "--format=esm",
            f"--outfile={bundle}",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        raise PolicyError(f"esbuild failed: {proc.stderr[-2000:]}")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return EnginePolicy(source=path, bundle=bundle, sha256=digest)


def _spawn_tile_of(started: dict[str, Any]) -> tuple[int, int] | None:
    """Read back the actually-conquered spawn tile from a start projection."""
    human = started.get("human")
    if not isinstance(human, dict):
        return None
    tile = human.get("spawn")
    if not isinstance(tile, dict):
        return None
    x, y = tile.get("x"), tile.get("y")
    if isinstance(x, bool) or not isinstance(x, int):
        return None
    if isinstance(y, bool) or not isinstance(y, int):
        return None
    return (x, y)


def sanitize_game_id(value: str) -> str:
    """Clamp an experiment/spawn label pair to the engine gameId charset."""
    cleaned = "".join(
        c if (c.isascii() and (c.isalnum() or c in "-_")) else "_" for c in value
    )
    cleaned = cleaned.strip("_") or "game"
    return cleaned[:32]


def game_id_for(prefix: str | None, spawn: Spawn) -> str | None:
    """Per-spawn world id: same spawn replays the same world, else None.

    FROZEN (legacy scheme): the run-name tail (the distinctive part) is
    kept with the spawn id so truncation to the 32-char engine limit can
    never merge two spawns of one run into the same world. Kept byte for
    byte so in-flight runs keep their worlds; new runs should use
    ``compact_game_id_for`` (replay-faithful, converter-safe).
    """
    if prefix is None:
        return None
    tail = sanitize_game_id(prefix)[-20:]
    sid = sanitize_game_id(spawn.id)[:11]
    return f"{tail}-{sid}"


def fnv1a32_hex(text: str) -> str:
    """FNV-1a 32-bit of UTF-8 bytes as 8 lowercase hex chars.

    Mirrors ``tapeGameId`` in engine/worker.ts (verified equal on test
    vectors incl. multibyte input); the shared derivation for tape labels.
    """
    digest = 0x811C9DC5
    for byte in text.encode("utf-8"):
        digest ^= byte
        digest = (digest * 0x01000193) & 0xFFFFFFFF
    return format(digest, "08x")


def compact_game_id_for(prefix: str | None, spawn: Spawn) -> str | None:
    """Replay-faithful world id: FNV-1a of the legacy id, 8 alnum chars.

    The archived-GameRecord schema (converter AND client) only accepts
    ``^[A-Za-z0-9]{8}$`` gameIDs, and the client re-derives tribe/nation
    ids by seeding from the recorded gameID. A tape whose label differs
    from the live seed replays expands correctly but silently drops every
    tribe/nation-targeted attack (``target not found``). Compact ids are
    already safe, so the tape label IS the live seed and replays are
    faithful. Same spawn replays the same world; ``None`` keeps the
    legacy single engine constant. Worlds differ from the legacy scheme
    (different seeds), so scores do not compare across schemes.
    """
    if prefix is None:
        return None
    return fnv1a32_hex(game_id_for(prefix, spawn) or "game")


def world_id_for(
    prefix: str | None, spawn: Spawn, world_scheme: str = "legacy"
) -> str | None:
    """Select the world-id scheme: ``"legacy"`` or ``"compact"``."""
    if world_scheme == "legacy":
        return game_id_for(prefix, spawn)
    if world_scheme == "compact":
        return compact_game_id_for(prefix, spawn)
    raise ValueError(
        f"unknown world_scheme {world_scheme!r}: expected 'legacy' or 'compact'"
    )


def score_episode(tiles_peak: int, ticks: int, winner: str | None) -> float:
    """v1 territory + survival score for one episode."""
    score = float(tiles_peak) + SURVIVAL_WEIGHT * float(ticks)
    if winner == HUMAN_NAME:
        score += WIN_BONUS
    return score


def run_episode(
    spawn: Spawn,
    policy: Any,
    map_name: str,
    config: EvalConfig,
    session_factory: Callable[[], GameSession] = GameSession,
    record_dir: Path | None = None,
    game_id: str | None = None,
) -> EpisodeResult:
    """Play one fixed spawn to completion; policy errors never escape.

    When *record_dir* is given, the engine worker writes ``record.json``
    there after every decision (tapes for everything); the previous
    value of ``OPENFRONT_RECORD_DIR`` is restored afterwards. *game_id*
    overrides the legacy engine constant so each spawn plays a distinct
    but reproducible world; ``None`` keeps the legacy behavior.
    The dir is absolutized: the worker runs with its own cwd, so a
    relative path would land the tape in the wrong place (or fail).
    """
    previous_record_dir = os.environ.get("OPENFRONT_RECORD_DIR")
    if record_dir is not None:
        os.environ["OPENFRONT_RECORD_DIR"] = os.path.abspath(record_dir)
    try:
        return _run_episode_inner(
            spawn, policy, map_name, config, session_factory, game_id
        )
    finally:
        if previous_record_dir is None:
            os.environ.pop("OPENFRONT_RECORD_DIR", None)
        else:
            os.environ["OPENFRONT_RECORD_DIR"] = previous_record_dir


def _run_episode_inner(
    spawn: Spawn,
    policy: Any,
    map_name: str,
    config: EvalConfig,
    session_factory: Callable[[], GameSession],
    game_id: str | None = None,
) -> EpisodeResult:
    session = session_factory()
    in_engine = bool(getattr(policy, "in_engine", False))
    if in_engine:
        started = session.start(
            nations=config.nations,
            difficulty=config.difficulty,
            map=map_name,
            tribes=config.tribes,
            spawn=(spawn.x, spawn.y),
            game_id=game_id,
            policy_path=str(policy.bundle),
        )
    else:
        started = session.start(
            nations=config.nations,
            difficulty=config.difficulty,
            map=map_name,
            tribes=config.tribes,
            spawn=(spawn.x, spawn.y),
            game_id=game_id,
        )
    spawn_tile = _spawn_tile_of(started)
    tick = int(started.get("tick", 0))
    tiles_peak = 0
    troops_peak = 0
    gold_peak = 0.0
    city_ever = False
    outcome = "ceiling"
    errors = 0
    consecutive = 0
    decisions = 0
    max_decisions = config.max_ticks // config.decision_ticks
    overview: dict[str, Any] = started
    winner: str | None = None
    final_tiles = 0
    final_troops = 0
    while decisions < max_decisions:
        human = overview.get("human", {})
        tiles = human.get("tiles", 0)
        if isinstance(tiles, int):
            tiles_peak = max(tiles_peak, tiles)
            final_tiles = tiles
            if tiles == 0 and not overview.get("in_spawn_phase"):
                outcome = "eliminated"
                break
        troops = human.get("troops", 0)
        if isinstance(troops, int):
            troops_peak = max(troops_peak, troops)
            final_troops = troops
        gold = human.get("gold", 0)
        if isinstance(gold, bool):
            pass
        elif isinstance(gold, (int, float)):
            gold_peak = max(gold_peak, float(gold))
        units = overview.get("units", [])
        if isinstance(units, list) and any(
            isinstance(unit, dict) and unit.get("type") == "City" for unit in units
        ):
            city_ever = True
        seen = overview.get("winner")
        if isinstance(seen, str) and seen:
            winner = seen
            outcome = f"winner:{seen}"
            break
        if in_engine:
            try:
                overview = session.run_policy_decision()
                consecutive = 0
            except Exception as exc:
                errors += 1
                consecutive += 1
                log.debug("policy decide failed: %s", exc)
                if consecutive >= MAX_CONSECUTIVE_ERRORS:
                    outcome = "errors"
                    break
        else:
            try:
                orders = policy.decide(dict(overview))
                consecutive = 0
            except Exception as exc:
                errors += 1
                consecutive += 1
                log.debug("policy decide failed: %s", exc)
                if consecutive >= MAX_CONSECUTIVE_ERRORS:
                    outcome = "errors"
                    break
                orders = []
            if not isinstance(orders, list):
                errors += 1
                orders = []
            apply_orders(session, [o for o in orders if o is not None])
        try:
            stepped = session.end_decision()
        except Exception as exc:
            log.debug("end_decision failed: %s", exc)
            outcome = "errors"
            break
        decisions += 1
        tick = int(stepped.get("tick", tick))
        if tick >= config.max_ticks:
            break
        overview = session.overview()
        seen = overview.get("winner")
        if isinstance(seen, str) and seen:
            winner = seen
            outcome = f"winner:{seen}"
            human = overview.get("human", {})
            if isinstance(human.get("tiles"), int):
                final_tiles = human["tiles"]
                tiles_peak = max(tiles_peak, final_tiles)
            if isinstance(human.get("troops"), int):
                final_troops = human["troops"]
                troops_peak = max(troops_peak, final_troops)
            break
    try:
        session.close()
    except Exception as exc:
        log.debug("session close failed: %s", exc)
    return EpisodeResult(
        spawn_id=spawn.id,
        ticks=tick,
        decisions=decisions,
        tiles_peak=tiles_peak,
        final_tiles=final_tiles,
        final_troops=final_troops,
        winner=winner,
        policy_errors=errors,
        score=score_episode(tiles_peak, tick, winner),
        spawn_tile=spawn_tile,
        game_id=game_id,
        troops_peak=troops_peak,
        gold_peak=gold_peak,
        city_ever=city_ever,
        outcome=outcome,
    )


def aggregate(report: CandidateReport) -> dict[str, Any]:
    """Mean/min score plus per-spawn breakdown for one candidate."""
    scores = [ep.score for ep in report.episodes]
    mean = sum(scores) / len(scores) if scores else 0.0
    return {
        "policy_sha256": report.policy_sha256,
        "episodes": len(report.episodes),
        "mean_score": mean,
        "min_score": min(scores) if scores else 0.0,
        "max_score": max(scores) if scores else 0.0,
        "wins": sum(1 for ep in report.episodes if ep.winner == HUMAN_NAME),
        "spawns": [
            {
                "spawn_id": ep.spawn_id,
                "ticks": ep.ticks,
                "decisions": ep.decisions,
                "tiles_peak": ep.tiles_peak,
                "final_tiles": ep.final_tiles,
                "final_troops": ep.final_troops,
                "winner": ep.winner,
                "policy_errors": ep.policy_errors,
                "score": ep.score,
                "spawn_tile": list(ep.spawn_tile) if ep.spawn_tile else None,
                "game_id": ep.game_id,
                "troops_peak": ep.troops_peak,
                "gold_peak": ep.gold_peak,
                "city_ever": ep.city_ever,
                "outcome": ep.outcome,
            }
            for ep in report.episodes
        ],
    }


def _serialize_orders(orders: Any) -> tuple[Any, ...]:
    """Hashable order signature for trajectory comparison."""
    if not isinstance(orders, list):
        return (("invalid", None),)
    return tuple(
        (
            getattr(order, "kind", "?"),
            getattr(order, "target", None),
            getattr(order, "percent", None),
            getattr(order, "unit", None),
            getattr(order, "x", None),
            getattr(order, "y", None),
        )
        for order in orders
        if order is not None
    )


class RecordingPolicy:
    """Wrap a policy, recording every decide() output for comparison."""

    def __init__(self, policy: Any) -> None:
        self._policy = policy
        self.calls: list[tuple[tuple[str, Any], ...]] = []

    def decide(self, overview: dict[str, Any]) -> Any:
        orders = self._policy.decide(dict(overview))
        self.calls.append(_serialize_orders(orders))
        return orders


def order_stream(
    policy_path: Path,
    spawn: Spawn,
    map_name: str,
    config: EvalConfig,
    game_id: str | None,
) -> list[tuple[Any, ...]]:
    """Short trajectory probe: the serialized order stream of one episode."""
    recorder = RecordingPolicy(load_policy(policy_path))
    run_episode(spawn, recorder, map_name, config, GameSession, None, game_id)
    return recorder.calls


def _serialize_ts_orders(orders: Any) -> tuple[Any, ...]:
    """Hashable order signature for runner dicts (same 6-tuple shape)."""
    if not isinstance(orders, list):
        return (("invalid", None),)
    items: list[tuple[Any, ...]] = []
    for order in orders:
        if order is None:
            continue
        if isinstance(order, dict):
            items.append(
                (
                    order.get("kind", "?"),
                    order.get("target"),
                    order.get("percent"),
                    order.get("unit"),
                    order.get("x"),
                    order.get("y"),
                )
            )
        else:
            items.append(
                (
                    getattr(order, "kind", "?"),
                    getattr(order, "target", None),
                    getattr(order, "percent", None),
                    getattr(order, "unit", None),
                    getattr(order, "x", None),
                    getattr(order, "y", None),
                )
            )
    return tuple(items)


def _ts_decide_batch(
    bundle: Path, overviews: list[dict[str, Any]]
) -> list[tuple[Any, ...]]:
    """Replay overviews through the TS bundle via decide_runner (one node)."""
    import json
    import shutil

    if not overviews:
        return []
    node = shutil.which("node")
    if node is None:
        raise PolicyError("node is not on PATH")
    runner = REPO_ROOT / "policies" / "decide_runner.ts"
    payload = "\n".join(json.dumps(overview) for overview in overviews) + "\n"
    proc = subprocess.run(
        [node, str(runner), str(bundle)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        raise PolicyError(f"decide_runner failed: {proc.stderr[-2000:]}")
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) != len(overviews):
        raise PolicyError(
            f"decide_runner returned {len(lines)} lines for {len(overviews)} overviews"
        )
    streams: list[tuple[Any, ...]] = []
    for line in lines:
        try:
            orders = json.loads(line)
        except json.JSONDecodeError as error:
            raise PolicyError(f"decide_runner bad JSON: {error}") from error
        streams.append(_serialize_ts_orders(orders))
    return streams


def ts_order_stream(
    policy_path: Path,
    spawn: Spawn,
    map_name: str,
    config: EvalConfig,
    game_id: str | None,
    max_ticks: int = 500,
) -> list[tuple[Any, ...]]:
    """Short TS trajectory probe: runner-decided order stream, capped."""
    policy = load_ts_policy(policy_path)
    bundle = policy.bundle
    session = GameSession()
    started = session.start(
        nations=config.nations,
        difficulty=config.difficulty,
        map=map_name,
        tribes=config.tribes,
        spawn=(spawn.x, spawn.y),
        game_id=game_id,
        policy_path=str(bundle),
    )
    overviews: list[dict[str, Any]] = []
    overview: dict[str, Any] = started
    max_decisions = max_ticks // config.decision_ticks
    consecutive_errors = 0
    try:
        for _ in range(max_decisions):
            human = overview.get("human", {})
            tiles = human.get("tiles", 0) if isinstance(human, dict) else 0
            if (
                isinstance(tiles, int)
                and tiles == 0
                and not overview.get("in_spawn_phase")
            ):
                break
            winner = overview.get("winner")
            if isinstance(winner, str) and winner:
                break
            overviews.append(dict(overview))
            try:
                overview = session.run_policy_decision()
                consecutive_errors = 0
            except Exception as exc:
                consecutive_errors += 1
                log.debug("TS policy decide failed: %s", exc)
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    break
            try:
                stepped = session.end_decision()
            except Exception as exc:
                log.debug("end_decision failed: %s", exc)
                break
            tick = int(stepped.get("tick", 0))
            if tick >= max_ticks:
                overview = session.overview()
                winner = overview.get("winner")
                if isinstance(winner, str) and winner:
                    pass
                break
            overview = session.overview()
            winner = overview.get("winner")
            if isinstance(winner, str) and winner:
                break
    finally:
        try:
            session.close()
        except Exception as exc:
            log.debug("session close failed: %s", exc)
    return _ts_decide_batch(bundle, overviews)


def probe_divergence(
    candidate_path: Path,
    parent_path: Path,
    registry: SpawnRegistry,
    config: EvalConfig,
    game_id_prefix: str,
    max_ticks: int = 500,
    world_scheme: str = "legacy",
) -> tuple[bool, str]:
    """True when the candidate behaves differently from its parent.

    Runs both policies for *max_ticks* on the first two registry spawns
    (same worlds as the full eval) and compares order streams. Identical
    streams mean the edit never fired there — shipping the full eval
    would replay the parent's scores exactly.
    """
    import dataclasses

    candidate_is_ts = candidate_path.suffix == ".ts"
    parent_is_ts = parent_path.suffix == ".ts"
    if candidate_is_ts != parent_is_ts:
        raise ValueError(
            f"refuse to compare across languages: {candidate_path.suffix} "
            f"vs {parent_path.suffix}"
        )
    use_ts = candidate_is_ts and parent_is_ts
    probe_config = dataclasses.replace(config, max_ticks=max_ticks)
    spawns = list(registry.spawns)[:2]
    try:
        for spawn in spawns:
            game_id = world_id_for(game_id_prefix, spawn, world_scheme)
            if use_ts:
                candidate_calls = ts_order_stream(
                    candidate_path,
                    spawn,
                    registry.map,
                    probe_config,
                    game_id,
                    max_ticks,
                )
                parent_calls = ts_order_stream(
                    parent_path, spawn, registry.map, probe_config, game_id, max_ticks
                )
            else:
                candidate_calls = order_stream(
                    candidate_path, spawn, registry.map, probe_config, game_id
                )
                parent_calls = order_stream(
                    parent_path, spawn, registry.map, probe_config, game_id
                )
            if candidate_calls != parent_calls:
                first = next(
                    i
                    for i, (a, b) in enumerate(zip(candidate_calls, parent_calls))
                    if a != b
                )
                return True, (
                    f"diverged on {spawn.id} at decision {first} "
                    f"({len(candidate_calls)} decisions probed)"
                )
    except Exception as exc:
        log.warning("divergence probe failed, failing open to eval: %s", exc)
        return True, f"probe error, failing open: {exc}"
    probed = ", ".join(s.id for s in spawns)
    return False, (
        f"identical order streams on {probed} "
        f"({max_ticks} ticks each) — the edit never fired there"
    )


def _spawn_job(
    args: tuple[str, str, EvalConfig, str, Spawn, str | None],
) -> tuple[EpisodeResult, float]:
    """Pool worker: load the policy fresh and play one spawn to completion.

    The policy is constructed per spawn (no cross-episode state leaks);
    the tape dir is routed through this process's own environment, so
    parallel spawns never share ``OPENFRONT_RECORD_DIR``.
    """
    policy_path, map_name, config, game_dir, spawn, game_id = args
    path = Path(policy_path)
    if path.suffix == ".ts":
        policy: Any = load_ts_policy(path)
    else:
        policy = load_policy(path)
    episode_start = time.time()
    episode = run_episode(
        spawn, policy, map_name, config, GameSession, Path(game_dir), game_id
    )
    return episode, time.time() - episode_start


def evaluate_candidate(
    policy_path: Path,
    registry: SpawnRegistry,
    config: EvalConfig,
    output: Path,
    write_experiment_manifest: bool = True,
    game_id_prefix: str | None = None,
    jobs: int = 1,
    world_scheme: str = "legacy",
) -> dict[str, Any]:
    """Run every registry spawn; write per-spawn tapes + aggregate.

    The output dir is an experiment (``experiment.json`` + ``games/``)
    unless *write_experiment_manifest* is False, in which case the
    per-spawn games belong to an ancestor experiment (evolution iters).
    *game_id_prefix* gives each spawn a distinct but reproducible world;
    ``None`` keeps the legacy single engine constant. *jobs* fans spawns
    out over worker processes (``1`` = sequential, same code path).
    *world_scheme* selects the id derivation: ``"legacy"`` (default,
    frozen 32-char ids, tapes replay expands only) or ``"compact"``
    (8-alnum ids, tapes replay faithfully). Schemes seed different
    worlds, so scores never compare across them.
    """
    ensure_fresh_dir(output)
    eval_started_at = time.time()
    # Fail fast on an unloadable policy before fanning out; children load
    # their own copy per spawn (no cross-episode state leaks).
    if policy_path.suffix == ".ts":
        _policy: Any = load_ts_policy(policy_path)
    else:
        _policy = load_policy(policy_path)
    assert _policy is not None
    policy_sha = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    config_dict = {
        "nations": config.nations,
        "tribes": config.tribes,
        "difficulty": config.difficulty,
        "max_ticks": config.max_ticks,
        "decision_ticks": config.decision_ticks,
    }
    if isinstance(jobs, bool) or not isinstance(jobs, int) or jobs < 1:
        raise ValueError(f"jobs must be a positive integer, got {jobs!r}")
    if write_experiment_manifest:
        write_experiment(
            output,
            name=output.name,
            kind="code-evo",
            config={"map": registry.map, **config_dict},
            notes=f"spawns registry sha256: {registry.sha256}",
        )
    tasks = [
        (
            str(policy_path),
            registry.map,
            config,
            str(output / "games" / spawn.id),
            spawn,
            world_id_for(game_id_prefix, spawn, world_scheme),
        )
        for spawn in registry.spawns
    ]
    world_ids = [task[5] for task in tasks if task[5] is not None]
    if len(set(world_ids)) != len(world_ids):
        raise ValueError(
            f"world id collision under scheme {world_scheme!r}: {world_ids}"
        )
    for _, _, _, game_dir, _, _ in tasks:
        ensure_fresh_dir(Path(game_dir))
    if jobs == 1 or len(tasks) == 1:
        outcomes = [_spawn_job(task) for task in tasks]
    else:
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(processes=min(jobs, len(tasks))) as pool:
            outcomes = pool.map(_spawn_job, tasks)
    report = CandidateReport(policy_sha256=policy_sha)
    for (episode, episode_wall), spawn in zip(outcomes, registry.spawns, strict=True):
        game_dir = output / "games" / spawn.id
        report.episodes.append(episode)
        write_summary(
            game_dir,
            build_summary(
                game=f"{output.name}/{spawn.id}",
                experiment=output.name,
                pipeline="code-evo",
                policy_sha256=policy_sha,
                map=registry.map,
                spawn_id=spawn.id,
                difficulty=config.difficulty,
                config=config_dict,
                decisions=episode.decisions,
                tick_last=episode.ticks,
                winner=episode.winner,
                tiles_peak=episode.tiles_peak,
                tiles_final=episode.final_tiles,
                troops_final=episode.final_troops,
                score=episode.score,
                wall_s=episode_wall,
                tool_errors=episode.policy_errors,
                extra={
                    "spawn_xy": [spawn.x, spawn.y],
                    "spawn_tile": list(episode.spawn_tile)
                    if episode.spawn_tile is not None
                    else None,
                    "game_id": episode.game_id,
                    "outcome": episode.outcome,
                    "troops_peak": episode.troops_peak,
                    "gold_peak": episode.gold_peak,
                    "city_ever": episode.city_ever,
                },
            ),
        )
        log.info(
            "spawn %s: ticks=%d peak=%d final=%d winner=%s score=%.0f",
            episode.spawn_id,
            episode.ticks,
            episode.tiles_peak,
            episode.final_tiles,
            episode.winner,
            episode.score,
        )
    result = aggregate(report)
    result["spawns_sha256"] = registry.sha256
    result["map"] = registry.map
    result["config"] = config_dict
    result["wall_s"] = time.time() - eval_started_at
    write_json_atomic(output / "aggregate.json", result)
    return result
