import json, time, statistics
from pathlib import Path
from openfrontbench.engine import EngineWorker

md = Path('/Users/ky23812/Repos/OpenFrontIO-Env/vendor/OpenFrontIO/resources/maps/alps')
RATIOS = [15, 20, 25, 30, 35, 40, 50]
TRIALS = 3
TOTAL_TICKS = 5000
DECISION_TICKS = 50
MILESTONES = [50000, 100000, 200000, 400000]

results = {r: [] for r in RATIOS}
for ratio in RATIOS:
    for trial in range(TRIALS):
        milestone_ticks = {m: None for m in MILESTONES}
        with EngineWorker(map_dir=md) as engine:
            state = engine.start(nations=0, tribes=0, spawn=None, map_size='compact')
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
        print(f"ratio={ratio}% t@400000={milestone_ticks[400000]} final={tiles}")

print("\n" + "="*70)
print(f"{'Ratio':>6} | " + " | ".join(f"{m:>8}" for m in MILESTONES))
print("-"*70)
for ratio in RATIOS:
    r = results[ratio][0]
    print(f"{ratio:>5}% | " + " | ".join(f"{r['milestones'][m]:>8}" for m in MILESTONES))
