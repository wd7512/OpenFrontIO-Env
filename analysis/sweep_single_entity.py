"""Single-entity baseline sweep on The Box.

Five strategies, one entity each (no competition):
  1. agent solo: 1-tick (threshold=0.36, ratio=0.005) expansion, no units,
     run until the engine declares a winner (>80% land, FFA rule).
  2-5. one nation at each difficulty (easy/medium/hard/impossible), human
     idle (no orders), run until the engine declares a winner.

The agent parameters are the analytical optimum from analytical_model.py
(model optimum (0.364, 0.013), game-verified local minimum at (0.36, 0.005)).

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

AGENT_THRESHOLD = 0.36
AGENT_RATIO = 0.005

# 50-tick (5s) variant: threshold gating is phase-fragile at this cadence
# (a missed gate idles the front for a full cycle), so the robust optimum
# sends every cycle. Ratio is the model optimum at threshold=0.
AGENT50_THRESHOLD = 0.0
AGENT50_RATIO = 0.12
AGENT50_INTERVAL = 50

# 20-tick (2s) variant: model optimum (gating viable again — cycles are
# short enough that the war-chest buffer covers missed gates).
AGENT20_THRESHOLD = 0.375
AGENT20_RATIO = 0.065
AGENT20_INTERVAL = 20


def run_agent(raw: Path) -> dict[str, object]:
    outdir = raw / "box-agent-solo"
    outdir.mkdir(parents=True, exist_ok=True)
    os.environ["OPENFRONT_RECORD_DIR"] = str(outdir)
    with EngineWorker(map_dir=MD) as engine:
        state = engine.start(nations=0, tribes=0, spawn=SPAWN, map_size="full")
        tick = state["tick"]
        tiles = state["human"]["tiles"]
        winner = None
        crossed = None
        while winner is None and tick < 200000:
            troops = state["human"]["troops"]
            max_t = 2 * (tiles**0.6 * 1000 + 50000) if tiles > 0 else 50000
            if troops >= AGENT_THRESHOLD * max_t:
                try:
                    engine.attack(target="expand", troops=troops * AGENT_RATIO)
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
        "name": "box-agent-solo",
        "crossing_tick": crossed,
        "declared_tick": record["ticks"],
        "tiles": tiles,
        "winner": winner,
    }
    logger.info(result)
    return result


def run_agent_50(raw: Path) -> dict[str, object]:
    outdir = raw / "box-agent-50tick"
    outdir.mkdir(parents=True, exist_ok=True)
    os.environ["OPENFRONT_RECORD_DIR"] = str(outdir)
    with EngineWorker(map_dir=MD) as engine:
        state = engine.start(nations=0, tribes=0, spawn=SPAWN, map_size="full")
        tick = state["tick"]
        tiles = state["human"]["tiles"]
        winner = None
        crossed = None
        while winner is None and tick < 200000:
            troops = state["human"]["troops"]
            try:
                engine.attack(target="expand", troops=troops * AGENT50_RATIO)
            except Exception:
                pass
            state = engine.advance(AGENT50_INTERVAL)
            tick = state["tick"]
            tiles = state["human"]["tiles"]
            if crossed is None and tiles > WIN_SHARE * TOTAL_LAND:
                crossed = tick
            winner = state.get("winner")
        record = engine.save_record()
    result = {
        "name": "box-agent-50tick",
        "crossing_tick": crossed,
        "declared_tick": record["ticks"],
        "tiles": tiles,
        "winner": winner,
    }
    logger.info(result)
    return result


def run_agent_20(raw: Path) -> dict[str, object]:
    outdir = raw / "box-agent-20tick"
    outdir.mkdir(parents=True, exist_ok=True)
    os.environ["OPENFRONT_RECORD_DIR"] = str(outdir)
    with EngineWorker(map_dir=MD) as engine:
        state = engine.start(nations=0, tribes=0, spawn=SPAWN, map_size="full")
        tick = state["tick"]
        tiles = state["human"]["tiles"]
        winner = None
        crossed = None
        while winner is None and tick < 200000:
            troops = state["human"]["troops"]
            max_t = 2 * (tiles**0.6 * 1000 + 50000) if tiles > 0 else 50000
            if troops >= AGENT20_THRESHOLD * max_t:
                try:
                    engine.attack(target="expand", troops=troops * AGENT20_RATIO)
                except Exception:
                    pass
            state = engine.advance(AGENT20_INTERVAL)
            tick = state["tick"]
            tiles = state["human"]["tiles"]
            if crossed is None and tiles > WIN_SHARE * TOTAL_LAND:
                crossed = tick
            winner = state.get("winner")
        record = engine.save_record()
    result = {
        "name": "box-agent-20tick",
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
            state = engine.advance(50)
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
    results = [run_agent(args.raw), run_agent_20(args.raw), run_agent_50(args.raw)]
    for difficulty in ("easy", "medium", "hard", "impossible"):
        results.append(run_nation(args.raw, difficulty))
    print("\n=== Single-entity baseline (The Box, win = >80% land) ===")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()
