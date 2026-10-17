import json, time
from pathlib import Path
from openfrontbench.engine import EngineWorker

md = Path('/Users/ky23812/Repos/OpenFrontIO-Env/vendor/OpenFrontIO/tests/testdata/maps/big_plains')
THRESHOLDS = [0, 10, 25, 50, 75, 90]
RATIOS = [10, 15, 20, 25, 30, 35, 40]
TOTAL_TICKS = 5000
DECISION_TICKS = 1
MILESTONES = [1000, 2500, 5000, 7500, 9000]

results = {}
for thresh in THRESHOLDS:
    for ratio in RATIOS:
        milestone_ticks = {m: None for m in MILESTONES}
        with EngineWorker(map_dir=md) as engine:
            state = engine.start(nations=0, tribes=0, spawn=(100, 100))
            tick = state["tick"]; tiles = state["human"]["tiles"]
            for m in MILESTONES:
                if milestone_ticks[m] is None and tiles >= m:
                    milestone_ticks[m] = tick
            while tick < TOTAL_TICKS:
                troops = state["human"]["troops"]
                max_troops = 2 * (tiles ** 0.6 * 1000 + 50000) if tiles > 0 else 50000
                if thresh == 0 or troops >= thresh / 100.0 * max_troops:
                    try:
                        engine.attack(target="expand", troops=troops * ratio / 100.0)
                    except Exception:
                        pass
                state = engine.advance(1)
                tick = state["tick"]; tiles = state["human"]["tiles"]
                for m in MILESTONES:
                    if milestone_ticks[m] is None and tiles >= m:
                        milestone_ticks[m] = tick
            for m in MILESTONES:
                if milestone_ticks[m] is None:
                    milestone_ticks[m] = TOTAL_TICKS
        key = f"{thresh}_{ratio}"
        results[key] = {"thresh": thresh, "ratio": ratio, "milestones": milestone_ticks, "final": tiles}
        print(f"thresh={thresh:>3}% ratio={ratio:>3}% t@9000={milestone_ticks[9000]:>6} final={tiles:>6}")

best = min(results.values(), key=lambda r: r["milestones"][9000])
print(f"\nBest for 9000 tiles: thresh={best['thresh']}% ratio={best['ratio']}% -> {best['milestones'][9000]} ticks, final={best['final']}")
