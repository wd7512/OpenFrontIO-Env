"""Single-entity baseline sweep on The Box.

One entity per game (no competition), no units/structures:
  - agent variants: threshold-ratio expansion at fixed decision cadences
    (1/10/20/30/40/45/50/52/60 ticks), run until the engine declares a winner
    (>80% land, FFA rule). Parameters are the analytical optima from
    analytical_model.py, game-verified (50-tick uses the robust ungated
    optimum — the raw gated optimizer spike is phase overfitting, i.e. it
    does not transfer in-game; see verify_optimum.py). 45/52/60-tick
    bracket the Hard nation decision cadence (attackRate = U{45..60}).
  - one nation at each production difficulty (easy/medium/hard/impossible),
    human idle (no orders), run until the engine declares a winner.
  - seeded Improved-Hard nations (new "improved-hard" difficulty: Hard
    economy, custom threshold-ratio behavior from
    engine/improvedHardBehavior.ts), 3 game_ids.

Sampling is per-tick; sends happen only on cadence ticks
(``(tick - FIRST_DECISION_TICK) % interval == 0``), so trajectories are
identical to batched advance(interval) (deterministic engine, same intents
at the same ticks) while crossing/declaration ticks are exact instead of
batch-end artifacts.

Games (and verify's optimizer runs) execute in a process pool (``--jobs``,
default up to 8): each game is an independent engine subprocess with its
own record dir, and results are collected in order so output is
deterministic. ``--jobs 1`` runs serially.

Records are cleaned in place (turn hashes stripped, map name set) so the
raw directory is directly servable. Results (crossing/declared ticks,
winners, provenance) are written as JSON.

Usage:
  uv run python analysis/sweep_single_entity.py --raw /tmp/replay_raw
  uv run python analysis/sweep_single_entity.py --raw /tmp/replay_raw --only box-agent-solo,box-nation-hard-solo
  uv run python analysis/sweep_single_entity.py --raw /tmp/replay_raw --jobs 1 --no-progress
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analytical_model import (
    FIRST_DECISION_TICK,
    NATION_ECONOMY,
    TOTAL_LAND,
    WIN_SHARE,
    find_optimum,
    max_troops,
)

from openfrontbench.engine import EngineWorker
from openfrontbench.experiment import write_experiment
from openfrontbench.run_summary import build_summary, write_summary

from tqdm import tqdm

logger = logging.getLogger(__name__)

MAP_DIR = (
    Path(__file__).resolve().parent.parent / "vendor/OpenFrontIO/resources/maps/thebox"
)
SPAWN = (1024, 1024)
MAX_TICKS = 300000

# (threshold, ratio, interval) per agent variant. 1/10/20/30/40-tick use
# gated optima; 50-tick uses the robust ungated optimum (gating is
# phase-fragile at 5s cadence). 45/52/60-tick bracket the Hard nation
# decision cadence (attackRate = U{45..60}, mean ~52) with rounded optima.
AGENTS = {
    "box-agent-solo": (0.36, 0.005, 1),
    "box-agent-10tick": (0.375, 0.05, 10),
    "box-agent-20tick": (0.375, 0.065, 20),
    "box-agent-30tick": (0.38, 0.095, 30),
    "box-agent-40tick": (0.37, 0.115, 40),
    "box-agent-50tick": (0.0, 0.12, 50),
    "box-agent-45tick": (0.38, 0.15, 45),
    "box-agent-52tick": (0.38, 0.15, 52),
    "box-agent-60tick": (0.37, 0.18, 60),
}
DIFFICULTIES = ("easy", "medium", "hard", "impossible")
# Seeded runs of the improved-hard nation difficulty (Hard economy, custom
# threshold-ratio behavior wired in engine/improvedHardBehavior.ts).
NATION_SEEDS = {"improved-hard": ("BOX-IH-A", "BOX-IH-B", "BOX-IH-C")}
# Tribe races on the same map: production tribe count (400, the solo
# default), human idle, one nation each — hard vs improved-hard.
TRIBES = 400
NATION_TRIBES_RACES = {
    "hard": "BOX-TR-HARD",
    "improved-hard": "BOX-TR-IH",
}

# Replay-library layout: run name -> experiment dir. Runs are written
# straight into their suite so re-runs land in place (no moves, no ghost
# route IDs); unknown names fall back to the raw root (legacy bucket).
EXPERIMENTS = {
    "box-cadence-ladder": {
        "kind": "box-cadence",
        "notes": (
            "Box solo cadence ladder: threshold/ratio/interval sweep, "
            "one run each. Declared = engine 80% tick."
        ),
    },
    "box-solo-baseline": {
        "kind": "box-solo",
        "notes": "Reference 1-tick solo policy on The Box (threshold 0.36).",
    },
    "box-nation-difficulty": {
        "kind": "box-nation",
        "notes": "Production nation opponents by difficulty, human idle.",
    },
    "box-improved-hard-solo": {
        "kind": "box-improved-hard",
        "notes": (
            "Custom improved-hard nation behavior (52-tick 15% expansion, "
            "never attacks players), seeds A/B/C. Client replays reproduce "
            "it via the archived sidecar meta (nationBehavior)."
        ),
    },
    "box-tribes-race": {
        "kind": "box-tribes",
        "notes": (
            "Nation vs 400 tribes. Client replays reproduce custom behavior "
            "via the archived sidecar meta (nationBehavior)."
        ),
    },
}
EXP_OF = {
    name: "box-cadence-ladder"
    for name in (
        "box-agent-10tick",
        "box-agent-20tick",
        "box-agent-30tick",
        "box-agent-40tick",
        "box-agent-45tick",
        "box-agent-50tick",
        "box-agent-52tick",
        "box-agent-60tick",
    )
}
EXP_OF["box-agent-solo"] = "box-solo-baseline"
for _difficulty in (*DIFFICULTIES,):
    EXP_OF[f"box-nation-{_difficulty}-solo"] = "box-nation-difficulty"
for _difficulty, _seeds in NATION_SEEDS.items():
    for _seed in _seeds:
        EXP_OF[f"box-nation-{_difficulty}-{_seed}"] = "box-improved-hard-solo"
for _difficulty, _seed in NATION_TRIBES_RACES.items():
    EXP_OF[f"box-nation-{_difficulty}-{_seed}-tribes{TRIBES}"] = "box-tribes-race"


def exp_dir(raw: Path, name: str) -> Path:
    """Game dir for a run: inside its suite, or the raw root (legacy)."""
    exp = EXP_OF.get(name)
    return raw / exp / name if exp else raw / name


def ensure_experiments(raw: Path) -> None:
    """Write missing experiment.json manifests (never overwrite)."""
    for exp, spec in EXPERIMENTS.items():
        manifest = raw / exp / "experiment.json"
        if not manifest.is_file():
            manifest.parent.mkdir(parents=True, exist_ok=True)
            write_experiment(
                manifest.parent,
                name=exp,
                kind=spec["kind"],
                notes=spec["notes"],
            )


def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def clean_record(outdir: Path) -> None:
    """Strip per-turn hashes and stamp the map name so raw output is servable."""
    record_path = outdir / "record.json"
    record = json.loads(record_path.read_text())
    for turn in record.get("turns", []):
        turn.pop("hash", None)
    game_config = record.get("gameConfig", {})
    game_config["gameMap"] = "The Box"
    record["gameConfig"] = game_config
    record_path.write_text(json.dumps(record))


def _economy_label(difficulty: str) -> str | None:
    """Compact start/max/regen label for the suite table, e.g. 12500/0.5x/0.9x."""
    econ = NATION_ECONOMY.get(difficulty)
    if econ is None:
        return None
    start, max_mult, regen_mult = econ
    return f"{start:.0f}/{max_mult}x/{regen_mult}x"


def _winner_kind(record: dict[str, Any], winner: object) -> str | None:
    """Winner kind from the record's player roster (human/nation/tribe)."""
    if not isinstance(winner, str):
        return None
    players = record.get("players")
    if not isinstance(players, list):
        return None
    for p in players:
        if isinstance(p, dict) and p.get("name") == winner:
            kind = p.get("kind")
            return kind if isinstance(kind, str) else None
    return None


def _write_run_summary(
    outdir: Path, result: dict[str, object], record: dict[str, Any]
) -> None:
    """Write the unified summary.json the replay index reads for its columns."""
    players = record.get("players")
    kinds = (
        {p.get("name"): p.get("kind") for p in players}
        if isinstance(players, list)
        else {}
    )
    winner = result.get("winner")
    result["winner_kind"] = _winner_kind(record, winner)
    metrics: dict[str, Any] = {
        "strategy": None,
        "crossing_tick": result.get("crossing_tick"),
        "declared_tick": result.get("declared_tick"),
        "winner_kind": kinds.get(winner) if isinstance(winner, str) else None,
        "behavior": result.get("behavior", "agent-policy"),
        "tribes": result.get("tribes", 0),
        "seed": result.get("game_id"),
        "economy": _economy_label(str(result["difficulty"]))
        if result.get("difficulty")
        else None,
    }
    if (
        isinstance(result.get("threshold"), float)
        and isinstance(result.get("ratio"), float)
        and isinstance(result.get("interval"), int)
    ):
        metrics["strategy"] = (
            f"{result['threshold']}/{result['ratio']}/{result['interval']}t"
        )
    declared_raw = result.get("declared_tick")
    tick_last = declared_raw if isinstance(declared_raw, int) else None
    tiles_raw = result.get("tiles")
    tiles_final = tiles_raw if isinstance(tiles_raw, int) else None
    summary = build_summary(
        game=str(result.get("name", outdir.name)),
        experiment=EXP_OF.get(str(result.get("name", ""))),
        pipeline="engine-sweep",
        map="The Box",
        spawn_id="center-1024-1024",
        difficulty=str(result["difficulty"]) if result.get("difficulty") else None,
        config={
            k: result[k]
            for k in (
                "threshold",
                "ratio",
                "interval",
                "difficulty",
                "behavior",
                "tribes",
                "game_id",
            )
            if k in result
        },
        tick_first=FIRST_DECISION_TICK,
        tick_last=tick_last,
        winner=winner if isinstance(winner, str) else None,
        tiles_final=tiles_final,
        extra={"metrics": metrics},
    )
    write_summary(outdir, summary)


def run_agent(
    raw: Path,
    name: str,
    threshold: float,
    ratio: float,
    interval: int,
    progress: bool = False,
    spawn: tuple[int, int] | None = SPAWN,
    game_id: str | None = None,
) -> dict[str, object]:
    outdir = exp_dir(raw, name)
    outdir.mkdir(parents=True, exist_ok=True)
    os.environ["OPENFRONT_RECORD_DIR"] = str(outdir)
    with EngineWorker(map_dir=MAP_DIR) as engine:
        state = engine.start(
            nations=0, tribes=0, spawn=spawn, map_size="full", game_id=game_id
        )
        tick = state["tick"]
        tiles = state["human"]["tiles"]
        winner = None
        crossed = None
        with tqdm(
            desc=name, unit="tick", disable=not progress, leave=False, miniters=50
        ) as bar:
            while winner is None and tick < MAX_TICKS:
                troops = state["human"]["troops"]
                cap = max_troops(max(tiles, 1))
                if (
                    tick - FIRST_DECISION_TICK
                ) % interval == 0 and troops >= threshold * cap:
                    try:
                        engine.attack(target="expand", troops=troops * ratio)
                    except Exception:
                        pass
                state = engine.advance(1)
                tick = state["tick"]
                tiles = state["human"]["tiles"]
                bar.update(tick - bar.n)
                bar.set_postfix_str(f"tick={tick} tiles={tiles}")
                if crossed is None and tiles > WIN_SHARE * TOTAL_LAND:
                    crossed = tick
                winner = state.get("winner")
        record = engine.save_record()
    clean_record(outdir)
    result = {
        "name": name,
        "threshold": threshold,
        "ratio": ratio,
        "interval": interval,
        "spawn": list(spawn) if spawn is not None else None,
        "game_id": game_id,
        "crossing_tick": crossed,
        "declared_tick": record["ticks"],
        "tiles": tiles,
        "winner": winner,
    }
    _write_run_summary(outdir, result, record)
    logger.info(result)
    return result


def run_nation(
    raw: Path,
    difficulty: str,
    game_id: str | None = None,
    progress: bool = False,
    tribes: int = 0,
) -> dict[str, object]:
    tag = (
        f"box-nation-{difficulty}-{game_id}"
        if game_id
        else f"box-nation-{difficulty}-solo"
    )
    if tribes:
        tag += f"-tribes{tribes}"
    outdir = exp_dir(raw, tag)
    outdir.mkdir(parents=True, exist_ok=True)
    os.environ["OPENFRONT_RECORD_DIR"] = str(outdir)
    with EngineWorker(map_dir=MAP_DIR) as engine:
        state = engine.start(
            nations=1,
            difficulty=difficulty,
            tribes=tribes,
            spawn=SPAWN,
            map_size="full",
            game_id=game_id,
        )
        tick = state["tick"]
        winner = None
        with tqdm(
            desc=tag, unit="tick", disable=not progress, leave=False, miniters=50
        ) as bar:
            while winner is None and tick < MAX_TICKS:
                # human idle: no orders, the nation plays alone
                state = engine.advance(1)
                tick = state["tick"]
                bar.update(tick - bar.n)
                bar.set_postfix_str(f"tick={tick}")
                winner = state.get("winner")
        record = engine.save_record()
    clean_record(outdir)
    result = {
        "name": tag,
        "difficulty": difficulty,
        "behavior": "improved-hard" if difficulty == "improved-hard" else "production",
        "game_id": game_id,
        "tribes": tribes,
        "declared_tick": record["ticks"],
        "winner": winner,
    }
    _write_run_summary(outdir, result, record)
    logger.info(result)
    return result


# Full dispatcher spec: (raw_dir, tick_progress, kind, payload), where the
# agent payload is (name, threshold, ratio, interval, spawn, game_id),
# the nation payload is (difficulty, game_id, tribes), and the opt payload is
# (interval, max_mult, regen_mult, start_troops).
TaskSpec = tuple[str, bool, str, Sequence[Any]]


def _run_task(spec: TaskSpec) -> dict[str, object]:
    """Module-level (picklable) single-game dispatcher for process pools.

    spec = (raw_dir, tick_progress, kind, payload); payload mirrors the
    run_agent / run_nation arguments.
    """
    raw_dir, tick_progress, kind, payload = spec
    raw = Path(raw_dir)
    if kind == "agent":
        name, threshold, ratio, interval, spawn_raw, game_id_raw = payload
        assert isinstance(name, str)
        assert isinstance(threshold, float)
        assert isinstance(ratio, float)
        assert isinstance(interval, int)
        spawn = cast("tuple[int, int] | None", spawn_raw)
        game_id = cast("str | None", game_id_raw)
        assert spawn is None or isinstance(spawn, tuple)
        assert game_id is None or isinstance(game_id, str)
        return run_agent(
            raw,
            name,
            threshold,
            ratio,
            interval,
            progress=tick_progress,
            spawn=spawn,
            game_id=game_id,
        )
    if kind == "opt":
        # Pure-Python optimizer run (no engine), same pool.
        interval, max_mult, regen_mult, start_troops = payload
        assert isinstance(interval, int)
        assert isinstance(max_mult, float)
        assert isinstance(regen_mult, float)
        assert isinstance(start_troops, float)
        opt = find_optimum(
            interval,
            max_mult=max_mult,
            regen_mult=regen_mult,
            start_troops=start_troops,
        )
        return {
            "threshold": opt["threshold"],
            "ratio": opt["ratio"],
            "crossing_tick": opt["crossing_tick"],
        }
    (difficulty, nation_game_id, nation_tribes) = payload
    assert isinstance(difficulty, str)
    assert nation_game_id is None or isinstance(nation_game_id, str)
    assert isinstance(nation_tribes, int)
    assert kind == "nation"
    return run_nation(
        raw,
        difficulty,
        game_id=nation_game_id,
        progress=tick_progress,
        tribes=nation_tribes,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument(
        "--results",
        type=Path,
        default=Path(__file__).resolve().parent / "results" / "sweep_results.json",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="comma-separated run names to execute (default: all)",
    )
    parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="show tqdm progress bars (per-run tick bars on stderr)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=min(8, os.cpu_count() or 1),
        help="parallel game processes (1 = serial; each game is an "
        "independent engine subprocess with its own record dir)",
    )
    args = parser.parse_args()
    args.raw.mkdir(parents=True, exist_ok=True)
    ensure_experiments(args.raw)
    only = set(args.only.split(",")) if args.only else None

    # Tasks are (kind, payload) tuples; results are collected in order so
    # the results file is deterministic regardless of completion order.
    tasks: list[tuple[str, Sequence[Any]]] = []
    for name, (threshold, ratio, interval) in AGENTS.items():
        if only is None or name in only:
            tasks.append(("agent", (name, threshold, ratio, interval, SPAWN, None)))
    for difficulty in DIFFICULTIES:
        run_name = f"box-nation-{difficulty}-solo"
        if only is None or run_name in only:
            tasks.append(("nation", (difficulty, None, 0)))
    for difficulty, seeds in NATION_SEEDS.items():
        for game_id in seeds:
            run_name = f"box-nation-{difficulty}-{game_id}"
            if only is None or run_name in only:
                tasks.append(("nation", (difficulty, game_id, 0)))
    for difficulty, game_id in NATION_TRIBES_RACES.items():
        run_name = f"box-nation-{difficulty}-{game_id}-tribes{TRIBES}"
        if only is None or run_name in only:
            tasks.append(("nation", (difficulty, game_id, TRIBES)))

    tick_progress = args.progress and args.jobs == 1
    specs: list[TaskSpec] = [
        (str(args.raw), tick_progress, kind, payload) for kind, payload in tasks
    ]

    results: list[dict[str, object]] = []
    if args.jobs <= 1:
        for spec in tqdm(specs, desc="runs", unit="run", disable=not args.progress):
            results.append(_run_task(spec))
    else:
        # Separate processes (not threads): OPENFRONT_RECORD_DIR is
        # process-global, and each game deserves its own engine subprocess.
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            for result in tqdm(
                pool.map(_run_task, specs),
                total=len(specs),
                desc="runs",
                unit="run",
                disable=not args.progress,
            ):
                results.append(result)

    # Merge into any existing results file so --only runs update entries in
    # place instead of clobbering the runs they did not execute.
    merged: dict[str, dict[str, object]] = {}
    order: list[str] = []
    if args.results.is_file():
        try:
            previous = json.loads(args.results.read_text())
        except ValueError:
            previous = {}
        for run in previous.get("runs", []):
            if isinstance(run, dict) and isinstance(run.get("name"), str):
                merged[run["name"]] = run
                order.append(run["name"])
    for run in results:
        name = run.get("name")
        if isinstance(name, str):
            if name not in merged:
                order.append(name)
            merged[name] = run
    payload = {
        "created": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
        "map": "The Box",
        "win_rule": "tile share > 80% (FFA)",
        "runs": [merged[name] for name in order],
    }
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(payload, indent=2))
    logger.info(
        "wrote %d results to %s (%d new)",
        len(payload["runs"]),
        args.results,
        len(results),
    )


if __name__ == "__main__":
    main()
