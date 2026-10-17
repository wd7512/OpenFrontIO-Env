import json, time
from pathlib import Path
from openfrontbench.engine import EngineWorker

md = Path('/Users/ky23812/Repos/OpenFrontIO-Env/vendor/OpenFrontIO/tests/testdata/maps/big_plains')
INTERVALS = [10, 100]  # ticks per decision
THRESHOLDS = [0, 5, 10, 15, 20, 25, 30, 40, 50]
RATIOS = [10, 15, 20, 25, 30, 35, 40]
TOTAL_TICKS = 10000
MILESTONES = [9000]

for D in INTERVALS:
    print(f"\n{'='*60}")
    print(f"DECISION INTERVAL = {D} ticks ({D/10:.1f}s)")
    print(f"{'='*60}")
    results = {}
    for thresh in THRESHOLDS:
        for ratio in RATIOS:
            milestone_ticks = {9000: None}
            with EngineWorker(map_dir=md) as engine:
                state = engine.start(nations=0, tribes=0, spawn=(100, 100))
                tick = state["tick"]; tiles = state["human"]["tiles"]
                if milestone_ticks[9000] is None and tiles >= 9000:
                    milestone_ticks[9000] = tick
                while tick < TOTAL_TICKS:
                    troops = state["human"]["troops"]
                    max_troops = 2 * (tiles ** 0.6 * 1000 + 50000) if tiles > 0 else 50000
                    if thresh == 0 or troops >= thresh / 100.0 * max_troops:
                        try:
                            engine.attack(target="expand", troops=troops * ratio / 100.0)
                        except Exception:
                            pass
                    state = engine.advance(min(D, TOTAL_TICKS - tick))
                    tick = state["tick"]; tiles = state["human"]["tiles"]
                    if milestone_ticks[9000] is None and tiles >= 9000:
                        milestone_ticks[9000] = tick
                if milestone_ticks[9000] is None:
                    milestone_ticks[9000] = TOTAL_TICKS
            key = f"{thresh}_{ratio}"
            results[key] = {"thresh": thresh, "ratio": ratio, "t9": milestone_ticks[9000], "final": tiles}

    # Print best threshold for each ratio
    print(f"\n{'thresh':>6} | " + " | ".join(f"{r:>4}" for r in RATIOS))
    print("-" * 50)
    for thresh in THRESHOLDS:
        row = [results[f"{thresh}_{r}"]["t9"] for r in RATIOS]
        print(f"{thresh:>5}% | " + " | ".join(f"{v:>4}" for v in row))

    best = min(results.values(), key=lambda r: r["t9"])
    print(f"\nBest: thresh={best['thresh']}% ratio={best['ratio']}% -> {best['t9']} ticks, final={best['final']}")
