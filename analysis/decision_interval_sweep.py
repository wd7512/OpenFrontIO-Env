import json, time
from pathlib import Path
from openfrontbench.engine import EngineWorker

md = Path('/Users/ky23812/Repos/OpenFrontIO-Env/vendor/OpenFrontIO/tests/testdata/maps/big_plains')
INTERVALS = [1, 5, 10, 25, 50]
THRESHOLDS = [0, 5, 10, 15, 20, 25, 30, 40, 50]
RATIO = 25  # fixed ratio
TOTAL_TICKS = 5000
MILESTONES = [9000]

results = {}
for D in INTERVALS:
    best_thresh = None
    best_ticks = 99999
    for thresh in THRESHOLDS:
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
                        engine.attack(target="expand", troops=troops * RATIO / 100.0)
                    except Exception:
                        pass
                state = engine.advance(min(D, TOTAL_TICKS - tick))
                tick = state["tick"]; tiles = state["human"]["tiles"]
                if milestone_ticks[9000] is None and tiles >= 9000:
                    milestone_ticks[9000] = tick
            if milestone_ticks[9000] is None:
                milestone_ticks[9000] = TOTAL_TICKS
        t9 = milestone_ticks[9000]
        results.setdefault(D, {})[thresh] = t9
        if t9 < best_ticks:
            best_ticks = t9
            best_thresh = thresh
        print(f"D={D:>2} thresh={thresh:>3}% -> t@9000={t9:>6}")
    print(f"  => Best threshold for D={D}: {best_thresh}% ({best_ticks} ticks)\n")

print("="*60)
print("DECISION INTERVAL vs OPTIMAL THRESHOLD")
print("="*60)
for D in INTERVALS:
    best = min(results[D].items(), key=lambda x: x[1])
    print(f"D={D:>2} ticks: optimal threshold = {best[0]:>3}% (t@9000={best[1]})")
