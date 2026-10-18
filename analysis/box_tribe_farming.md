# Phase 2 solved: analytical tribe farming beats production Hard everywhere

Status: derived from engine math, confirmed on paired seeds, tape FAITHFUL.

## Verdict

farm-p4 (pinned config, zero grid search) beats production Hard's race
time on **every seed at every tribe density**, plus holdout seeds:

| Arena | farm-p4 | production Hard | margin |
|---|---|---|---|
| N=20, 5 seeds | **6,035** | 6,898 | −12.5% |
| N=100, 5 seeds | **5,660** | 6,097 | −7.2% |
| N=100 holdout, 4 fresh seeds | **5,762** | 6,126 | −5.9% |
| N=400, 2 seeds | **7,023 / 7,127** | 7,335 / 7,439 | −4.2% |

Pure expansion (Improved-Hard, no orders) wins 0/5 at every density —
at N=400 it dies to a tribe at 86,401 (OF000036); production wins the
same map at 7,661 (OF000035). Farming is the phase that separates them.

Data: `analysis/results/farm_p4_{n20,n100,holdout,n400}.json`.
Runner: `analysis/sweep_tribes.py` (pinned policies only).
Model: `analysis/analytical_model.py` (kill-model section).

## Derivation (no grid search)

### Kill-rate model (Box plains, nation vs bot)

From `Config.attackLogic` (player branch) + `attackTilesPerTick` +
`AttackExecution.tick`, with nation-vs-bot mag discount (80 × 0.7 = 56):

- Pacing per game tick: `3·B·within(10·A/D, 0.01, 0.5)` tiles of budget
  over a B-tile front (A = attack troops, D = defender troops).
- Cost per tile: `16.5·within(1/(5·A/D), 0.2, 1.5)` ticks of budget.
- Attacker loss per tile: `0.6·within(D/A, 0.6, 2)·44.8 + 0.29·density`.
- At 4× overwhelm (A/D = 4): ~0.45·B tiles/tick, ~16 troops lost/tile —
  a 10k-tile tribe behind a 300-tile front dies in ~73 ticks.
- At 0.2× (A/D = 0.2): ~3× slower, ~3.3× the loss per tile — **and the
  siege never completes**: defender-pool damage (density × tiles/tick)
  falls below tribe regen (`bot_regen`), so the attack stalls forever
  and the sent troops are wasted. `kill_completes()` in the model
  decides this exactly.

Two exact engine rules complete the picture: a target below **100
tiles** flips instantly (`handleDeadDefender` → `conquerPlayer`), and
surrounded clusters are **deleted** (`PlayerExecution.removeClusters`;
largest cluster deleted when surrounded by a single non-friendly
player) — the "surround → annex" meta, grounded.

### Production's bot algorithm, read from source

`AiAttackBehavior.attackBots` + `calculateBotAttackTroops` +
`troopSendCap` + `NationExecution` ratios (`vendor/OpenFrontIO`,
pinned):

| Knob | Production Hard | farm-p4 |
|---|---|---|
| Cadence | 45–60 tick attack loop | **52** |
| Sort | density (troops/tiles) asc, structures first | **same** |
| Tranche | **4× target troops** | **same** |
| Budget | troops − 0.30–0.40·cap − sent | **0.35 midpoint** |
| Skip | front below 2× target | **same** |
| Parallel | **3** | **same** |
| Retain | ≥ 75% of strongest non-bot neighbor | **same** |

### The two edges that beat it (not tie it)

1. **Simultaneous TN + farming.** `maybeAttack` short-circuits: each
   production attack tick does TN expansion *or* bot attacks, never
   both. Our external nation runs the IH autopilot *and* drains farm
   orders on the same tick — strictly more work per tick.
2. **Enclosure-aware sort.** Production's density sort is blind to
   enclosure; enclosed tribes die near-free (token 2% poke → cluster
   deletion + <100 flip). farm-p4 pokes enclosed tribes first via a
   true worker-side enclosure test (border-tile owner scan mirroring
   the engine's surround rule), then density order.

Both edges are mechanisms, not fitted parameters. Every farm-p4 knob
is pinned by source or derivation; nothing was swept.

## Confirmation protocol

Pre-registered bar: strictly faster than production on every seed at
every N. Paired seeds (same world, both brains), fresh holdout seeds
at N=100, N=400 headline vs OF000035's 7,661 neighborhood. One run
each — no axis exploration, no re-rolls.

A 109-order farm-p4 tape (BOX-TRIBE-A, N=100, 5,879 ticks) replays
**FAITHFUL** through the real client pipeline (`verify_replay.ts`,
winner + tick match) — this also proves the new tribe-targeted
`externalOrders` tape path end to end.

## Model-validation notes (superseded exploratory grids)

Early exploratory runs ( since removed from the runner) confirmed each
derived axis independently before the derivation was complete: gate
0.30 ≫ 0.15 (phase-1 growth band re-appearing), share U-curve bottoming
at 0.15–0.25, parallel 2 beating 1 (kill rate = fronts ÷ siege time),
weakest > richest > strongest targets, cadence 52 > 104. The flat-share
`greedy` family this replaces lost 40% to production at N=100 because
fixed shares stall against regenerating defenders — the derived 4×
rule with the 2×-skip is the fix, not a bigger grid.

## Harness changes for this phase

- `nation_order` accepts `tribe-N` (resolves the tribe roster; tape
  stores raw `targetID`, so replays need no bridge change).
- `nation_observe` gains `tribes` (incl. `enclosed`) + `tribeGraph`.
- Tests: `tests/test_nation_tribes.py` (6 tests: order validation,
  tape contents, obs contract, determinism, tribe damage, empty DuelEnv
  fields).

## What's next

Phase 3 (nation fighting) inherits the peel infrastructure for target
selection. Known residual: production builds cities mid-race — at its
N=100 win (3.79M tiles) the tile formula predicts a 17.8M cap but the
trace shows 19.8M (~8 city-levels). That economy is phase-4 surface, not
farming, and it is the documented explanation for the shrinking margin
as N grows (12.5% → 7.2% → 4.2%).
