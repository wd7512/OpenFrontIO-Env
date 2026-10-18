# Phase framework: benchmark first, derive the optimum, compose by trigger

Status: framework adopted; phases 1 (expansion, two scales) and 2 (farming)
rebuilt under it.

## Why: the phase that fooled us

Phase 1 optimized expansion on a single benchmark — ticks to win a
tribeless race — and crowned Improved-Hard (IH). On that metric it is
optimal: 7,825 ticks vs Hard's ~9,151, and +1,685 paired. But IH loses
the *opening* badly: it owns 2,400 tiles at tick 260 while production Hard
owns ~5,300. A benchmark that scores only the end state hid the sub-scale
where IH is worse than the thing it beats. The fix is not a cleverer
policy; it is a better benchmark. This document makes that structural.

## The framework

A phase is a triple **⟨Benchmarks, Optima, Trigger⟩**.

- **Benchmarks** — one or more, each **⟨arena, metric, gate⟩**:
  - *arena*: the scenario (Box, entity counts, human idle, seeds);
  - *metric*: a single scalar the phase is judged on;
  - *gate*: the pass/fail bar against production Hard.
  A multi-scale skill gets one benchmark per scale, each judged
  independently — never averaged into one number that can hide a scale.
- **Optima** — per benchmark, the policy **derived analytically** from the
  engine equations (never swept): the argmax of that benchmark's metric.
- **Trigger** — the predicate under which the composed agent runs each
  optimum, so phases stack without regression.

Two invariants keep composition honest:

1. **Nesting.** Benchmark(N)'s arena contains Benchmark(N−1)'s arena as a
   special case (0 tribes ⊂ N tribes). Phase code is a no-op where its
   trigger is dormant, so adding a phase cannot change a lower phase's
   result — verified bit-identical, not assumed.
2. **Metric = gate.** The metric *is* the gate; no proxies. IH's opening
   was missed precisely because the metric (race) was not the scale where
   it failed — so the opening got its own benchmark instead of being
   folded away.

**Derivation recipe** (per benchmark): read the governing equations from
the pinned vendor source → reduce to a closed-form model → verify each
equation against the engine → solve for the optimum analytically → pin,
confirm on paired seeds, verify one tape FAITHFUL.

## Phase 1 — Expansion (two scales)

Expansion is multi-scale, so it has two benchmarks. Phase 1 originally had
only 1b.

### 1a — Opening · metric: tiles at tick 260, tribeless Box

**Arena:** Box, human agent, 0 nations, 0 tribes, center spawn.
**Gate:** reach Hard's opening (production nation, mean ~5,300 @260).

**Derivation.** A fresh player holds 52 tiles → cap 121,500 troops with
25,000 start. The phase-1 rhythm gates sends at `0.38·cap = 46,170`, which
start troops do not reach until regen crosses it at tick ~60 — so IH *holds
still* (52 tiles at tick 60) while Hard expands from tick 1. The opening
optimum therefore starts **ungated**: the regen base sits far below cap
(marginal regen near its max), so early tiles compound into both the cap
and the frontier. A one-shot **burst** (Hard's Tick-1 throw) is the wrong
lever — it parks troops in the front, where they earn no regen (governing
eq. 6), starving the base: model burst 0.85 → 1,381 tiles @260 *and* a
slower race (7,915), worse on both metrics. The optimum is a **period** of
aggressive, ungated, short-cadence expansion, not a single send.

**Derived optimum (1a):** threshold 0.20, ratio 0.30, 13-tick cadence, from
tick 2 through tick 260.

### 1b — Sustained race · metric: crossing tick, tribeless Box

**Arena:** as 1a but run to the 80% win. **Gate:** beat Hard paired.

**Derived optimum (1b):** threshold near the regen argmax (0.42), dynamic
value slightly below (0.36–0.38); ratio balances feeding the front against
keeping the regen reserve. Enshrined: **0.38 / 0.15 / 52**. (Full
derivation: `box_single_entity_baseline.md`.)

### Composition → the phase-1 policy

**Trigger:** opening policy while `tick ≤ 260`, then the race rhythm.
Model (5,172 @260 / 7,822) agrees with the game (5,178 / 7,823).

`sweep_opening.py`, six tribeless seeds (`results/opening_race.json`):

| brain | t60 | t130 | t260 | t520 | race crossing |
|---|---|---|---|---|---|
| IH (race rhythm) | 52 | 493 | 2,400 | 10,972 | 7,825 |
| **graft (1a∘1b)** | 521 | 1,917 | **5,178** | 11,219 | **7,823** |
| Hard (nation) | 847 | 1,722 | 5,315 | 16,504 | ~9,151 |

IH cedes 60 ticks behind its gate; the graft reaches Hard parity by t260
(5,178 vs 5,315) at **no race cost** (7,823 ≤ 7,825). Hard leads again by
t520 (16,504 vs 11,219) yet still loses the race by ~1,300 — so an early
tile lead is *not* a race outcome. The opening's real value can only be
cashed in a contested game, which is phase 3's benchmark: 1a is now derived
and pinned, and whether it is worth running is phase 3's question, not
phase 1's.

## Phase 2 — Tribe farming

**Arena (nesting: 0 tribes ⇒ phase 1):** Box, external nation, N tribes,
0 rival nations. **Metric:** crossing tick. **Gate:** faster than Hard on
every seed at every N.

**Derived optimum (farm-p4):** production's own bot constants (read from
`AiAttackBehavior`), expressed through `nation_order`, plus two structural
edges production cannot field: simultaneous TN-expansion + farming, and
enclosure-aware targeting. The kill model (`analytical_model.py`: pacing ÷
per-tile cost, the stall condition, <100-tile flip, surround-deletion)
pins every knob; nothing swept. Full derivation: `box_tribe_farming.md`.

**Trigger:** a bordering tribe exists. Dormant ⇒ phase 1 bit-identical
(tribeless race, 0 orders).

| arena | farm-p4 | production | margin |
|---|---|---|---|
| N=20 ×5 | 6,035 | 6,898 | −12.5% |
| N=100 ×5 | 5,660 | 6,097 | −7.2% |
| N=100 holdout ×4 | 5,762 | 6,126 | −5.9% |
| N=400 ×2 | 7,023 / 7,127 | 7,335 / 7,439 | −4.2% |

## The scaffold, both phases

| | 1a opening | 1b race | 2 farming |
|---|---|---|---|
| arena | Box, tribeless | Box, tribeless | Box, N tribes, no rivals |
| metric | tiles@260 | crossing tick | crossing tick |
| gate | Hard's opening | beats Hard paired | beats Hard every seed |
| optimum | 0.20/0.30/13 → 260 | 0.38/0.15/52 | farm-p4 |
| trigger | `tick ≤ 260` | always | bordering tribe |
| model / game | 5,172 / 5,178 | 7,824 / 7,825 | net faster everywhere |

Composed, the agent runs: aggressive opening → race rhythm → farm orders on
contact. Each stage is a no-op below its trigger, so the stack equals phase
1 on a clean map and adds farming exactly when there is a tribe to farm.

## What went wrong before, precisely

- **One metric, one scale.** Phase 1's single race metric could not see
  the opening, so an opening regression passed as "solved."
- **A benchmark that isn't a game.** Pre-contact tribaless racing is a
  slice of a real game; a policy optimal on the slice need not be optimal
  in the whole. The framework fixes this by *nesting* benchmarks so each is
  a strict sub-scenario of a real game, and by making the metric the gate.
- **Optimizing the wrong thing.** IH's gate is right for the race and wrong
  for the opening; only a separate benchmark makes the two optima visible
  and composable.

## Next: phases 3–7 as framework instances

Each phase starts by writing its benchmark (arena + metric + gate), then
derives the optimum:

- **3 Nation fighting.** Benchmark: paired duels vs Hard (metric: win rate
  and margin). The opening's value gets tested here; the peel graph
  transfers to targeting.
- **4 Economy.** Needs `build_unit`/`upgrade_structure`; benchmark: troop-cap
  curve + first-city tick. The ~8-city gap measured at phase 2 is its
  starting metric.
- **5–7 Naval / WMD / Diplomacy.** Each needs its order surface first; then
  benchmark, then optimum.
