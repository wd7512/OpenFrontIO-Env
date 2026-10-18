# Phase plan: solve OpenFront one phase at a time

Status: framework adopted (`framework.md`); phases 1 (two scales) and 2
solved; phase 3 scoped.

The methodology is now **benchmark-first**: each phase is
⟨Benchmarks, Optima, Trigger⟩ with nested arenas and metric = gate
(see `analysis/framework.md`). This table is the roadmap; `framework.md`
is the source of truth for phases 1–2.

## Objective

Decompose the game into its native progression — expansion, tribe
farming, fighting, economy, naval, late game, diplomacy — and solve each
analytically the way phase 1 was solved: sealed Box arenas, paired
seeds, parameter grids, a documented best policy, holdout seeds, FAITHFUL
tapes. No RL anywhere on this ladder; each phase's bar is "beats the
production Hard nation".

## The ladder

| # | Phase | Status | Gate on Box |
|---|---|---|---|
| 0 | Spawn choice | out of scope (config, not policy) | — |
| 1a | Expansion — opening | solved + maxed — ungated opening `0.20/0.15/21`→260 composed with the 1-tick race (`maxed_agents.md`) | opening 5,409 @260 vs Hard 5,315; crossing 7,798 < IH 7,825 |
| 1b | Expansion — race | solved — Improved-Hard rhythm `52/0.38/0.15`; 1-tick optimum `0.36/0.005/1` composed into 1a | beats Hard paired 6/6 (+1,685 mean) |
| 2 | Tribe farming (bots) | solved + maxed — farm-p4 (`box_tribe_farming.md`); three derived edges null/negative (`maxed_agents.md`) | beats Hard everywhere (N=20 −12.5%, N=100 −7.2%, N=400 −4.2%) |
| 3 | Nation fighting | 3a benchmarked (`sweep_duel.py`): IH 0/12, retargeted rhythm 12/12; kill model doesn't transfer | win paired duels vs Hard |
| 4 | Economy (city/port/factory) | not expressible (needs build orders) | troop-cap curve, first-city tick |
| 5 | Naval (boats/warships) | not expressible | — |
| 6 | Late game (silo/SAM/MIRV) | not expressible | — |
| 7 | Diplomacy (alliances/betrayal) | not expressible | — |

Ordering evidence: production's own `AiAttackBehavior` attacks in the
order expansion → bots → players; the community meta is
wildlands → bots → players (40–45% growth band, peak ~42%); and the
tribes race measured it — Hard + 400 tribes wins at **7,661** ticks
(faster than its 9,151 solo: tribes are free tempo), while
Improved-Hard, which can only attack neutral land, **dies to a tribe at
86,401**. Farming is the real gap between our agent and Hard.

Prior writeups: `box_single_entity_baseline.md` (phase 1 proof),
`probe_fight.py` + `results/probe_fight.json` (phase 3 probe),
`rl_idea.md` (parked RL thread — superseded by this ladder).

## Phase 2: tribe farming (solved — see `box_tribe_farming.md`)

**Arena.** Pure race, no rival nations, human idle on the Box: 1 external
nation vs N tribes. Scale up in stages — analytical model first, then
N=20 grids (fast episodes), confirm at N=100, optional N=400 headline vs
Hard's 7,661. Box only.

**Harness enabler (small, no vendor change).** Today `nation_order`
accepts only `nation-N` (`engine/worker.ts`); the human path already
accepts `tribe-N` through the same `AttackExecution`, and the
external-order tape stores the raw `targetID`, so accepting `tribe-N`
replays FAITHFUL with no bridge change. Also expose tribes in
`nationObserve` (`tribe_list`: troops/tiles/alive/`borders_me`) plus a
`tribe_graph` adjacency field built from pairwise `sharesBorderWith`
(n=20 → 190 pairs; n=400 → 80k; trivial at decision cadence).

**Graph solution (the targeting policy).** Optimal killing is a peel
order on the tribe adjacency graph:
1. Annex-ready first — tribes fully enclosed by our tiles die to a ~1%
   attack (encirclement rules): free land plus inherited gold, no siege.
2. Then fewest-live-neighbors (each kill encloses the next ring).
3. Tie-break cheapest: siege cost ≈ defender troops with the 2:1
   attacker:defender speed cap and the ≥20%-of-target minimum
   (production's own rule). At small N tribes sit near their 10k start,
   so ~10–20% shares should suffice and *order* dominates tranche size.

Policy family for the grid: {pure-expand baseline, greedy-weakest,
graph-peel} × share {10,20,30%} × cadence {52,104}, ≈18 configs × 5
seeds at N=20, neighborhood refinement around the winner, fresh
holdout seeds for the final number.

**Metrics.** Ticks-to-win vs Hard's race time, troops spent per tile
gained, annex-vs-siege kill mix, live-front count. Deliverable:
`analysis/box_tribe_farming.md` with the analytical best, same shape as
the phase-1 baseline. If the peel order beats Hard at small N and
survives the scale-up, phase 2 is solved — and phase 3 inherits the
graph for target selection.

## Phases 3–7 (later, sketched)

- **3 Fighting:** parametric sweep (share × cadence × troop/target
  gates) vs production Hard in paired duels, holdout seeds. No new
  harness work.
- **4 Economy:** needs `build_unit`/`upgrade_structure` in
  `nation_order`; gate is first-city tick + troop-cap curve vs Hard.
- **5–7 Naval / WMD / Diplomacy:** each needs its order surface
  (boats, silo launch, alliance lifecycle); decide order after 3–4 land.

## Conventions for all phases

Box only. Paired seeds vs production Hard. Fresh holdout seeds for the
final number. Best tape verifies FAITHFUL. New scripts live in
`analysis/`, results in `analysis/results/`. `ruff check`, `ty check`,
`pytest` before every commit; push to `main` with CI green.
