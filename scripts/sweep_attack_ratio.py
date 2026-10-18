"""Sweep attack ratios for optimal long-term territory growth (expansion-only, plains)."""

import json
import logging
import statistics
import time

from openfrontbench.engine import EngineWorker

logging.basicConfig(level=logging.WARNING)

RATIOS = [5, 10, 15, 20, 25, 30, 35, 40, 50, 60, 70, 80]
TRIALS = 3
TOTAL_TICKS = 5000
DECISION_TICKS = 50
MILESTONES = [5000, 10000, 20000, 30000, 36000]  # tiles to reach
EARLY_CHECKPOINTS = [100, 250, 500, 1000]  # ticks


def run_trial(ratio: int, trial: int) -> dict:
    """Run one game. Return {milestone_tiles: ticks_to_reach, early_ticks: tiles}."""
    milestone_ticks = {m: None for m in MILESTONES}
    early_tiles = {}
    with EngineWorker(
        map_dir="/Users/ky23812/Repos/OpenFrontIO-Env/vendor/OpenFrontIO/tests/testdata/maps/big_plains"
    ) as engine:
        state = engine.start(nations=0, tribes=0, spawn=(100, 100))
        tick = state["tick"]
        tiles = state["human"]["tiles"]
        # check milestones at start
        for m in MILESTONES:
            if milestone_ticks[m] is None and tiles >= m:
                milestone_ticks[m] = tick
        if tick in EARLY_CHECKPOINTS or tick >= EARLY_CHECKPOINTS[0]:
            pass

        while tick < TOTAL_TICKS:
            troops = state["human"]["troops"]
            send = troops * ratio / 100.0
            try:
                engine.attack(target="expand", troops=send)
            except Exception:
                pass
            advance_by = min(DECISION_TICKS, TOTAL_TICKS - tick)
            state = engine.advance(advance_by)
            tick = state["tick"]
            tiles = state["human"]["tiles"]

            for m in MILESTONES:
                if milestone_ticks[m] is None and tiles >= m:
                    milestone_ticks[m] = tick

            for ec in EARLY_CHECKPOINTS:
                if ec not in early_tiles and tick >= ec:
                    early_tiles[ec] = tiles

        # fill remaining
        for m in MILESTONES:
            if milestone_ticks[m] is None:
                milestone_ticks[m] = TOTAL_TICKS
        for ec in EARLY_CHECKPOINTS:
            if ec not in early_tiles:
                early_tiles[ec] = tiles

    return {
        "milestones": milestone_ticks,
        "early": early_tiles,
        "final_tiles": tiles,
        "final_tick": tick,
    }


def main():
    results = {r: [] for r in RATIOS}
    for ratio in RATIOS:
        for trial in range(TRIALS):
            t0 = time.time()
            res = run_trial(ratio, trial)
            elapsed = time.time() - t0
            results[ratio].append(res)
            mt = res["milestones"]
            print(
                f"ratio={ratio}% trial={trial} t@36000={mt[36000]} final={res['final_tiles']} ({elapsed:.1f}s)"
            )

    # Summary: ticks to reach 9000 tiles (lower = better)
    print("\n" + "=" * 90)
    print("TICKS TO REACH MILESTONE (lower = better growth)")
    header = f"{'Ratio':>6} | " + " | ".join(f"{m:>7}" for m in MILESTONES)
    print(header)
    print("-" * 90)
    for ratio in RATIOS:
        vals = []
        for m in MILESTONES:
            ts = [r["milestones"][m] for r in results[ratio]]
            vals.append(statistics.mean(ts))
        print(f"{ratio:>5}% | " + " | ".join(f"{v:>7.0f}" for v in vals))

    print("\n" + "=" * 90)
    print("TILES AT EARLY CHECKPOINT")
    header2 = f"{'Ratio':>6} | " + " | ".join(f"t={ec:>5}" for ec in EARLY_CHECKPOINTS)
    print(header2)
    print("-" * 90)
    for ratio in RATIOS:
        vals = []
        for ec in EARLY_CHECKPOINTS:
            ts = [r["early"][ec] for r in results[ratio]]
            vals.append(statistics.mean(ts))
        print(f"{ratio:>5}% | " + " | ".join(f"{v:>7.0f}" for v in vals))

    with open(
        "/Users/ky23812/Repos/OpenFrontIO-Env/scripts/sweep_results.json", "w"
    ) as f:
        json.dump({str(r): results[r] for r in RATIOS}, f, indent=2)
    print("\nRaw results saved to scripts/sweep_results.json")


if __name__ == "__main__":
    main()
