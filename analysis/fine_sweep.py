import json, time, statistics
from pathlib import Path
from openfrontbench.engine import EngineWorker

md = Path('/Users/ky23812/Repos/OpenFrontIO-Env/vendor/OpenFrontIO/tests/testdata/maps/big_plains')
RATIOS = [22, 23, 24, 25, 26, 27, 28]
TRIALS = 1
TOTAL_TICKS = 5000
DECISION_TICKS = 50
MILESTONES = [5000, 10000, 20000, 30000, 36000]

results = {r: [] for r in RATIOS}
for ratio in RATIOS:
    for trial in range(TRIALS):
        milestone_ticks = {m: None for m in MILESTONES}
        with EngineWorker(map_dir=md) as engine:
            state = engine.start(nations=0, tribes=0, spawn=(100, 100))
            tick = state["tick"]; tiles = state["human"]["tiles"]
            for m in MILESTONES:
                if milestone_ticks[m] is None and tiles >= m:
                    milestone_ticks[m] = tick
            while tick < TOTAL_TICKS:
                troops = state["human"]["troops"]
                try:
                    engine.attack(target="expand", troops=troops * ratio / 100.0)
                except Exception:
                    pass
                state = engine.advance(min(DECISION_TICKS, TOTAL_TICKS - tick))
                tick = state["tick"]; tiles = state["human"]["tiles"]
                for m in MILESTONES:
                    if milestone_ticks[m] is None and tiles >= m:
                        milestone_ticks[m] = tick
            for m in MILESTONES:
                if milestone_ticks[m] is None:
                    milestone_ticks[m] = TOTAL_TICKS
        results[ratio].append({"milestones": milestone_ticks, "final": tiles})
        print(f"ratio={ratio}% t@36000={milestone_ticks[36000]} final={tiles}")

print("\n" + "="*70)
print(f"{'Ratio':>6} | " + " | ".join(f"{m:>7}" for m in MILESTONES))
print("-"*70)
for ratio in RATIOS:
    r = results[ratio][0]
    print(f"{ratio:>5}% | " + " | ".join(f"{r['milestones'][m]:>7}" for m in MILESTONES))
