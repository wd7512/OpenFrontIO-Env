import json, time, statistics
from pathlib import Path
from openfrontbench.engine import EngineWorker

md = Path('/Users/ky23812/Repos/OpenFrontIO-Env/vendor/OpenFrontIO/tests/testdata/maps/big_plains')
RATIO = 25
THRESHOLDS = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
TRIALS = 1
TOTAL_TICKS = 20000
DECISION_TICKS = 50
MILESTONES = [1000, 2500, 5000, 7500, 9000]

results = {t: [] for t in THRESHOLDS}
for thresh in THRESHOLDS:
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
                max_troops = 2 * (tiles ** 0.6 * 1000 + 50000) if tiles > 0 else 50000
                # only attack if troops >= thresh * max_troops
                if thresh == 0.0 or troops >= thresh * max_troops:
                    try:
                        engine.attack(target="expand", troops=troops * RATIO / 100.0)
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
        results[thresh].append({"milestones": milestone_ticks, "final": tiles})
        print(f"thresh={thresh:.0%} t@9000={milestone_ticks[9000]} final={tiles}")

print("\n" + "="*70)
print(f"{'Thresh':>7} | " + " | ".join(f"{m:>7}" for m in MILESTONES))
print("-"*70)
for thresh in THRESHOLDS:
    r = results[thresh][0]
    print(f"{thresh:>6.0%} | " + " | ".join(f"{r['milestones'][m]:>7}" for m in MILESTONES))
