# The whole story: phases, detours, and an honest scoreboard

## The idea

OpenFront is one continuous simulation, but play decomposes into phases
that arrive in order: **expand → farm tribes → fight nations → economy →
naval → late game → diplomacy**. Each phase gets solved analytically the
way phase 1 was solved — derive from engine math, pin the config, confirm
on paired seeds — and each phase's bar is production Hard. No RL, no grid
sweeps. Details: `analysis/phase_plan.md`.

| # | Phase | Status |
|---|---|---|
| 1 | Expansion (neutral land) | solved — Improved-Hard `52/38%/15%`, +1,685 paired, duels 6-0 |
| 2 | Tribe farming (bots) | solved — farm-p4, beats production everywhere (this doc + `box_tribe_farming.md`) |
| 3 | Nation fighting | probe done (scripted cycle 6/6); not yet derived |
| 4–7 | Economy / naval / WMD / diplomacy | not expressible (need build/boat/alliance order surface) |

## Detour 1: the RL sandbox (parked, not wasted)

We built `DuelEnv` (external nation + 3 fight actions) and a 24-episode
probe: raid/cycle won 6/6 worlds where pure expansion won 2/6, and
fight-games cost ~5s. Conclusion: the action space contains dominating
policies, so learning was unnecessary — the policies were simple enough
to derive. Idea filed at `analysis/rl_idea.md`; sandbox kept as
infrastructure (`nation_order` / `nation_observe` carry phases 2–3).

## Detour 2: the grid sweep (the mistake, and the correction)

Phase 2 started correctly (peel-order theory, N=20 confirmatory grid),
then drifted: every surprise added an axis — share → parallel → gate →
target rule → cadence, ~350 episodes of curve-fitting. The correction,
per the phase-1 recipe: **read production's bot algorithm from the
pinned source** (`AiAttackBehavior`: density sort, 4× tranche, 0.35
reserve, 2×-skip, 3 parallel, 52 cadence) and **derive the kill model**
(`analytical_model.py`: pacing ÷ per-tile cost, the stall condition
damage > regen, <100-tile flip, surround-deletion). farm-p4's knobs are
all pinned by source or derivation. The 5-axis grid machinery was
deleted from the runner; old sweep aggregates survive only as
model-validation curves in `box_tribe_farming.md`.

## Phase 2 result

farm-p4 = production's parity floor (its own constants, expressed
through `nation_order`) **plus** two structural edges production can't
use: simultaneous TN expansion + farming (its attack loop does one or
the other per tick), and enclosure-aware targeting (its density sort is
enclosure-blind; new worker-side `enclosed` flag mirrors the engine's
surround rule).

| Arena | farm-p4 | production | margin |
|---|---|---|---|
| N=20 ×5 | 6,035 | 6,898 | −12.5% |
| N=100 ×5 | 5,660 | 6,097 | −7.2% |
| N=100 holdout ×4 | 5,762 | 6,126 | −5.9% |
| N=400 ×2 | 7,023 / 7,127 | 7,335 / 7,439 | −4.2% |

A 109-order tape verifies FAITHFUL through the real client pipeline.

## Honest scoreboard: is farm-p4 better at *farming*?

**At winning races with tribes on the map: yes, measured, everywhere**
(table above). **At the isolated skill of killing tribes: no
measurable difference** — and the data says so plainly:

- Kill counts are identical: N=100 74 vs 72, holdout 71 vs 71, N=400
  291 vs 289. Kill trajectories overlap tick-for-tick (both first-blood
  ~783, ~40 dead by ~5.2k on BOX-TRIBE-A). The model predicts this:
  same rules ⇒ same kill dynamics.
- farm-p4 converts the same kills into the win faster (+18% tiles at
  equal early ticks: 342k vs 290k at tick 2,863) because it never stops
  expanding while it farms. The phase-level win is real; the mechanism
  is parallelism of income streams, not superior killing.
- The enclosure refinement — the one genuinely new idea vs production
  — fired **zero times in 35 races** (`annex_pokes = 0` everywhere). No
  enclosed tribes occurred on these open Box maps. It is implemented
  and unit-tested but contributed zero measured ticks; its value is
  unproven, not disproven.
- The margin shrinks with N (12.5% → 7.2% → 4.2%) for a derived
  reason: production builds ~8 city-levels mid-race (19.8M cap vs
  17.8M tile-formula at its N=100 win). That economy is phase-4
  surface, and it bounds how far farming alone can go.

So: farm-p4 is the best farmer we can field without an economy — it
beats production at the farming *phase* on every tested map, ties it at
the *killing* skill by construction, and the remaining gap is
quantified and assigned to phase 4, not hand-waved.

## Stage scoreboard: the two agents vs Hard

The two agents are not two different players — farm-p4 *contains* the
expansion agent (same IH autopilot body; verified bit-identical without
tribes: tribeless BOX-BARE-A, both win at exactly 7,959 ticks with 0
orders). The ladder is cumulative: each phase adds a skill without
regressing the previous one. Hard is a different shape at every stage:

| Stage | IH (expansion agent) | farm-p4 | Hard |
|---|---|---|---|
| Opening (~260 ticks, same seed/spawn) | 2,400 tiles (gated rhythm) | same as IH (0 orders pre-contact) | **5,746 tiles** (Tick-1 burst at 80–90%) — wins the opening |
| Sustained expansion (tribeless race) | **7,959**, beats Hard (phase-1 paired 6/6, +1,685) | identical to IH (verified) | 9,155 — loses the long game |
| Farming (tribes present) | 0 wins everywhere, dies (N=400: dead at 86,401) | **beats Hard everywhere**; same kills, faster races | parity kills, slower races |

Read across: Hard wins the opening, loses the race, ties the kills.
IH wins the race, dies to contact. farm-p4 keeps IH's race, adds
contact, and the contact costs nothing when there is nothing to fight
(0 orders, identical tape). The open question is no longer "which
agent" — it is which *phase* the next map demands, and phases 3+ are
still Hard's territory (nation fighting, then economy).

## What's next

- Phase 3 (nation fighting): same recipe — read production's
  nation-targeting pipeline, derive, confirm on paired duels. The peel
  infrastructure transfers to target selection.
- Enclosure arenas: the `enclosed` machinery needs a map where pockets
  actually occur (dense tribes, maze-like maps) to test the annex edge.
- Phase 4 (economy): needs `build_unit`/`upgrade_structure` in
  `nation_order`; the ~8-city measurement is its starting benchmark.
