"""Single-entity baseline sweep on The Box.

One entity per game (no competition), no units/structures:
  - agent variants: threshold-ratio expansion at fixed decision cadences
    (1/10/20/30/40/50 ticks), run until the engine declares a winner
    (>80% land, FFA rule). Parameters are the analytical optima from
    analytical_model.py, game-verified (50-tick uses the robust ungated
    optimum — the raw gated optimizer spike is phase overfitting, i.e. it
    does not transfer in-game; see verify_optimum.py).
  - one nation at each difficulty (easy/medium/hard/impossible), human
    idle (no orders), run until the engine declares a winner.

Sampling is per-tick; sends happen only on cadence ticks
(``(tick - FIRST_DECISION_TICK) % interval == 0``), so trajectories are
identical to batched advance(interval) (deterministic engine, same intents
at the same ticks) while crossing/declaration ticks are exact instead of
batch-end artifacts.

Records are cleaned in place (turn hashes stripped, map name set) so the
raw directory is directly servable. Results (crossing/declared ticks,
winners, provenance) are written as JSON.

Usage:
  uv run python analysis/sweep_single_entity.py --raw /tmp/replay_raw
  uv run python analysis/sweep_single_entity.py --raw /tmp/replay_raw --only box-agent-solo,box-nation-hard-solo
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analytical_model import FIRST_DECISION_TICK, TOTAL_LAND, WIN_SHARE, max_troops

from openfrontbench.engine import EngineWorker

logger = logging.getLogger(__name__)

MAP_DIR = (
    Path(__file__).resolve().parent.parent / "vendor/OpenFrontIO/resources/maps/thebox"
)
SPAWN = (1024, 1024)
MAX_TICKS = 300000

# (threshold, ratio, interval) per agent variant. 1/10/20/30/40-tick use
# gated optima; 50-tick uses the robust ungated optimum (gating is
# phase-fragile at 5s cadence).
AGENTS = {
    "box-agent-solo": (0.36, 0.005, 1),
    "box-agent-10tick": (0.375, 0.05, 10),
    "box-agent-20tick": (0.375, 0.065, 20),
    "box-agent-30tick": (0.38, 0.095, 30),
    "box-agent-40tick": (0.37, 0.115, 40),
    "box-agent-50tick": (0.0, 0.12, 50),
}
DIFFICULTIES = ("easy", "medium", "hard", "impossible")


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


def run_agent(
    raw: Path, name: str, threshold: float, ratio: float, interval: int
) -> dict[str, object]:
    outdir = raw / name
    outdir.mkdir(parents=True, exist_ok=True)
    os.environ["OPENFRONT_RECORD_DIR"] = str(outdir)
    with EngineWorker(map_dir=MAP_DIR) as engine:
        state = engine.start(nations=0, tribes=0, spawn=SPAWN, map_size="full")
        tick = state["tick"]
        tiles = state["human"]["tiles"]
        winner = None
        crossed = None
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
        "crossing_tick": crossed,
        "declared_tick": record["ticks"],
        "tiles": tiles,
        "winner": winner,
    }
    logger.info(result)
    return result


def run_nation(raw: Path, difficulty: str) -> dict[str, object]:
    outdir = raw / f"box-nation-{difficulty}-solo"
    outdir.mkdir(parents=True, exist_ok=True)
    os.environ["OPENFRONT_RECORD_DIR"] = str(outdir)
    with EngineWorker(map_dir=MAP_DIR) as engine:
        state = engine.start(
            nations=1,
            difficulty=difficulty,
            tribes=0,
            spawn=SPAWN,
            map_size="full",
        )
        tick = state["tick"]
        winner = None
        while winner is None and tick < MAX_TICKS:
            # human idle: no orders, the nation plays alone
            state = engine.advance(1)
            tick = state["tick"]
            winner = state.get("winner")
        record = engine.save_record()
    clean_record(outdir)
    result = {
        "name": f"box-nation-{difficulty}-solo",
        "difficulty": difficulty,
        "declared_tick": record["ticks"],
        "winner": winner,
    }
    logger.info(result)
    return result


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
    args = parser.parse_args()
    args.raw.mkdir(parents=True, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None

    results: list[dict[str, object]] = []
    for name, (threshold, ratio, interval) in AGENTS.items():
        if only is None or name in only:
            results.append(run_agent(args.raw, name, threshold, ratio, interval))
    for difficulty in DIFFICULTIES:
        run_name = f"box-nation-{difficulty}-solo"
        if only is None or run_name in only:
            results.append(run_nation(args.raw, difficulty))

    payload = {
        "created": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
        "map": "The Box",
        "win_rule": "tile share > 80% (FFA)",
        "runs": results,
    }
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(payload, indent=2))
    logger.info("wrote %d results to %s", len(results), args.results)


if __name__ == "__main__":
    main()
