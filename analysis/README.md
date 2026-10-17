# OpenFrontIO Attack Ratio Analysis

Empirical study of optimal attack ratios for long-term territory growth,
run against the real OpenFrontIO engine (not a simulation).

## Setup

- **Engine**: OpenFrontIO v577819ba, built via `engine/npm run build`
- **Map**: `big_plains` (200×200, 40,000 tiles) for plains; `alps` (compact, 1000×918) for mixed terrain
- **Mode**: 1 human player, 0 nations, 0 tribes, spawn at (100,100)
- **Strategy**: Expansion-only (`target="expand"`), no buildings, no combat
- **Metric**: Ticks to reach 9,000 tiles (plains) or 400,000 tiles (alps)

## Key Formulas (from engine source)

**Troop regen** (`Config.troopIncreaseRate`):
```
max_troops = 2 × (tiles^0.6 × 1000 + 50000)
regen = (10 + troops^0.73 / 4) × (1 - troops / max_troops)
```

**Expansion combat** (`EngineConfig.attackLogic`, TerraNullius):
```
attacker_loss_per_tile = mag / 5          # mag=80 (plains), 100 (highland), 120 (mountain)
tick_fraction = within(2000 × tileCost / attackTroops, 5, 100) / (borderSize × 2)
# tileCost: 16.5 (plains), 20 (highland), 25 (mountain)
```

**Tick rate**: 1 tick = 100ms (10 ticks/second).

## Results Summary

### 1. Optimal Attack Ratio (plains, 50-tick decisions)

| Ratio | t@9000 |
|-------|--------|
| 5%    | 802 |
| 10%   | 552 |
| 15%   | 452 |
| 20%   | 452 |
| **25%** | **402** |
| 30%   | 402 |
| 35%   | 402 |
| 40%   | 402 |
| 50%   | 452 |
| 60%   | 502 |
| 70%   | 702 |
| 80%   | 1102 |

**Optimal: ~25%** (range 25-40% all tie at 402 ticks).

### 2. Optimal Threshold (plains, 25% ratio, 50-tick decisions)

| Threshold | t@9000 |
|-----------|--------|
| 0% (always) | **402** |
| 10% | 402 |
| 25% | 402 |
| 50% | 502 |
| 75% | 702 |
| 90% | 1052 |
| 100% (wait for max) | 20000 (stalled at 52 tiles) |

**Optimal: 0%** — attack immediately, don't wait for troops to accumulate.

### 3. Terrain Effect (alps, 50-tick decisions)

| Ratio | t@400000 | Final Tiles |
|-------|-----------|-------------|
| 15%   | 3202 | 914,292 |
| 20%   | 3202 | 846,667 |
| 25%   | 3552 | 684,713 |
| 30%   | 4152 | 525,383 |
| 40%   | 5000 | 262,461 |
| 50%   | 5000 | 126,533 |

**Optimal: 15-20%** on mixed terrain (vs 25% on plains). Higher troop cost per tile (mag 100-120 vs 80) drains faster, requiring conservative sends.

### 4. Decision Interval vs Threshold (plains, 25% ratio)

| Interval (D) | Optimal Threshold | t@9000 |
|-------------|-------------------|--------|
| 1 tick  | 20% | 344 |
| 5 ticks | 20% | 347 |
| 10 ticks | 20% | 352 |
| 25 ticks | 0% | 377 |
| 50 ticks | 0% | 402 |

**Transition at D≈15-20 ticks**: Below this, 20% threshold needed to protect regen. Above, 0% suffices.

### 5. Full Grid Search (plains, 50-tick decisions)

Best: threshold 0%, ratio 25-40% → 402 ticks.

### 6. Full Grid Search (plains, 1-tick decisions)

Best: threshold 25%, ratio 40% → 349 ticks.
Threshold 0% is catastrophic for ratios ≥20% (stalls at ~6,700 tiles).

### 7. Speed Comparison (plains)

| Speed | Interval | Threshold | Ratio | t@9000 |
|-------|----------|-----------|-------|--------|
| Max speed | 1 tick (0.1s) | 25% | 40% | 349 |
| 1 second | 10 ticks (1.0s) | 0% | 10% | 352 |
| 10 seconds | 100 ticks (10.0s) | 0% | 25% | 502 |

## Reproduction

All scripts are in `analysis/`. Run from repo root:

```bash
# Prerequisites
cd engine && npm install && npm run build && cd ..

# 1. Attack ratio sweep (plains, 50-tick)
uv run python analysis/sweep_attack_ratio.py  # (in scripts/)

# 2. Grid search (50-tick decisions)
uv run python analysis/grid_search_50tick.py

# 3. Grid search (1-tick decisions)
uv run python analysis/grid_search_1tick.py

# 4. Decision interval sweep
uv run python analysis/decision_interval_sweep.py

# 5. Speed grid (1s and 10s)
uv run python analysis/speed_grid.py

# 6. Terrain sweep (alps)
uv run python analysis/terrain_sweep.py

# 7. Threshold sweep
uv run python analysis/threshold_sweep.py

# 8. Fine sweep (22-28%)
uv run python analysis/fine_sweep.py
```

Note: `sweep_attack_ratio.py` is in `scripts/` and uses plains map with spawn (100,100).
Terrain sweep uses alps compact map with random spawn.

## Limitations

These results apply to **pure expansion into empty land with no opponents, no economy, no combat**.
Real-game optimal ratios likely shift based on threat level, terrain, gold income, and opponent proximity.
The most transferable finding: **don't delay expansion** — tile growth drives max troops, which drives regen.

## The Box Map (2048×2048, 4,194,304 tiles, all land)

### Optimal Ratio Sweep

| Ratio | Ticks to Full Map |
|-------|-------------------|
| 5%    | 12,352 |
| **10%** | **9,152** |
| 15%   | 9,302 |
| 20%   | 11,202 |
| 25%   | 15,202 |
| 30%   | 22,002 |
| 40%   | 48,202 |

**Optimal: 10%** (vs 25% on plains). Larger map → bigger border → each attack costs more troops → lower ratio preserves regen.

### Decision Interval Sweep

| Interval (D) | Ticks to Full Map |
|-------------|-------------------|
| 1 tick  | 100,000 (stalled) |
| 5 ticks | 100,000 (stalled) |
| 10 ticks | 52,362 |
| 25 ticks | 10,652 |
| **50 ticks** | **9,152** |

**Optimal: 50 ticks** (vs 1 tick on plains). Larger border → more troops spent per attack → need longer regen gaps.

### Threshold Sweep (10% ratio, 50-tick)

All thresholds 0-25% tie at 9,152 ticks. Threshold doesn't matter on large maps.

### Full Grid (50-tick decisions)

Best: threshold 0%, ratio 10% → 9,152 ticks (915 seconds game time).

### Key Insight: Map Size Inverts the Strategy

| Factor | Small Map (plains 200×200) | Large Map (The Box 2048×2048) |
|--------|---------------------------|-------------------------------|
| Optimal ratio | 25% | 10% |
| Optimal threshold | 0% (or 25% for 1-tick) | 0% (any threshold ties) |
| Optimal interval | 1 tick | 50 ticks |
| Ticks to full map | 852 (40K tiles) | 9,152 (4.2M tiles) |
| Tiles/tick (avg) | ~47 | ~458 |

On small maps, frequent micro-decisions with high ratios win. On large maps, less frequent decisions with conservative ratios win because the border is so large that each attack is expensive.
