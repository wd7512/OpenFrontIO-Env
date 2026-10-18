"""Single-entity baseline sweep on The Box.

One entity per game (no competition), no units/structures:
  - agent variants: threshold-ratio expansion at fixed decision cadences
    (1/10/20/30/40/50 ticks), run until the engine declares a winner
    (>80% land, FFA rule). Parameters are the analytical optima from
    analytical_model.py, game-verified (50-tick uses the robust ungated
    optimum — the raw gated optimizer spike is phase overfitting).
  - one nation at each difficulty (easy/medium/hard/impossible), human
    idle (no orders), run until the engine declares a winner.

Sampling is per-tick; sends happen only on cadence ticks, so trajectories
are identical to batched advance(interval) (deterministic engine, same
intents at the same ticks) while crossing/declaration ticks are exact
instead of batch-end artifacts.

Usage:
  uv run python analysis/sweep_single_entity.py --raw /tmp/replay_raw
"""

import argparse
import logging
import os
from pathlib import Path

from openfrontbench.engine import EngineWorker

logger = logging.getLogger(__name__)

MAP_DIR = (
    Path(__file__).resolve().parent.parent / "vendor/OpenFrontIO/resources/maps/thebox"
)
MD = MAP_DIR
TOTAL_LAND = 4194304
WIN_SHARE = 0.80
SPAWN = (1024, 1024)

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


def run_agent(
    raw: Path, name: str, threshold: float, ratio: float, interval: int
) -> dict[str, object]:
    outdir = raw / name
    outdir.mkdir(parents=True, exist_ok=True)
    os.environ["OPENFRONT_RECORD_DIR"] = str(outdir)
    with EngineWorker(map_dir=MD) as engine:
        state = engine.start(nations=0, tribes=0, spawn=SPAWN, map_size="full")
        tick = state["tick"]
        tiles = state["human"]["tiles"]
        winner = None
        crossed = None
        while winner is None and tick < 300000:
            troops = state["human"]["troops"]
            max_t = 2 * (tiles**0.6 * 1000 + 50000) if tiles > 0 else 50000
            if (tick - 2) % interval == 0 and troops >= threshold * max_t:
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
    result = {
        "name": name,
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
    with EngineWorker(map_dir=MD) as engine:
        state = engine.start(
            nations=1,
            difficulty=difficulty,
            tribes=0,
            spawn=SPAWN,
            map_size="full",
        )
        tick = state["tick"]
        winner = None
        while winner is None and tick < 300000:
            # human idle: no orders, the nation plays alone
            state = engine.advance(1)
            tick = state["tick"]
            winner = state.get("winner")
        record = engine.save_record()
    result = {
        "name": f"box-nation-{difficulty}-solo",
        "declared_tick": record["ticks"],
        "winner": winner,
    }
    logger.info(result)
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    args.raw.mkdir(parents=True, exist_ok=True)
    results = [
        run_agent(args.raw, name, th, ra, n) for name, (th, ra, n) in AGENTS.items()
    ]
    for difficulty in DIFFICULTIES:
        results.append(run_nation(args.raw, difficulty))
    print("\n=== Single-entity baseline (The Box, win = >80% land) ===")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()
