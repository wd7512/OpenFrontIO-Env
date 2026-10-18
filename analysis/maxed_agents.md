# The two maxed agents

Status: phases 1 and 2 pushed to their optima; one agent per phase. Phase 3
is benchmarked, not yet maxed (see `framework.md`).

The framework (`framework.md`) gives each phase ⟨benchmark, derived
optimum, trigger⟩. "Maxing" a phase means: take the derived optimum and ask
whether any remaining knob in the model can move its metric — by *deriving*
the candidate edge, not by sweeping. Below, phase 1 found a strictly better
policy; phase 2's optimum survived three derived edges unchanged. Both are
pinned and confirmed on paired seeds.

## Agent A — Expansion (`p1max`)

The phase-1 optimum, composed across its two scales.

| segment | until | threshold | ratio | cadence |
|---|---|---|---|---|
| opening (1a) | tick 260 | 0.20 | 0.15 | 21 |
| race (1b) | — | 0.36 | 0.005 | 1 |

**Derivation.** The opening is ungated (IH's `0.38·cap` gate blocks its first
send to tick ~60), and the race uses the near-1-tick optimum with the regen
reserve the model pins at 0.36. Why compose instead of running the race
rhythm throughout: the ungated opening gains early frontier, and the frontier
compounds into the cap — so the composed agent's crossing is *below* the pure
1-tick race optimum, not merely equal. Model: 5,503 @260 / 7,799.

**Confirmation** (`sweep_opening.py`, six tribeless seeds,
`results/opening_race.json`):

| brain | t60 | t130 | t260 | t520 | race crossing |
|---|---|---|---|---|---|
| IH (race rhythm) | 52 | 493 | 2,400 | 10,972 | 7,825 |
| graft (1a∘1b) | 521 | 1,917 | 5,178 | 11,219 | 7,823 |
| **p1max (maxed)** | 511 | 1,547 | **5,409** | 13,322 | **7,798** |
| Hard (nation, opening gate) | 846 | 1,722 | 5,315 | 16,504 | ~9,151 |

`p1max` is the first expansion brain to clear **both** phase-1 gates: it beats
Hard's opening (5,409 vs 5,315) *and* races faster than both IH and the pure
1-tick rhythm (7,798 < 7,802 < 7,825). Model pin:
`tests/test_analysis_model.py::test_phase1_maxed_agent_composition`.

## Agent B — Farming (`farm-p4`)

The phase-2 optimum: production's own bot constants read from
`AiAttackBehavior`, re-expressed through `nation_order`, plus the two
structural edges production cannot field — simultaneous expansion+farming and
enclosure-aware targeting. Every knob is derived in `box_tribe_farming.md`;
nothing is swept.

| arena | farm-p4 | production | margin |
|---|---|---|---|
| N=20 ×5 | 6,035 | 6,898 | −12.5% |
| N=100 ×5 | 5,660 | 6,097 | −7.2% |
| N=100 holdout ×4 | 5,762 | 6,126 | −5.9% |
| N=400 ×2 | 7,023 / 7,127 | 7,335 / 7,439 | −4.2% |

### Maxing search — three derived edges, all null or negative

Each candidate below was *derived* from the farming model, then run at N=100
on five seeds (`results/farm_edges.json`):

| edge | hypothesis | result |
|---|---|---|
| `farm-max` — unbounded parallel fronts | production's cap of 3 is binding | **bit-identical to farm-p4** (5,660/5,660): the cap never binds — budget runs out first |
| `farm-max-fast` — decision cadence 26 | finer decisions open fronts sooner | **worse** (5,686): 52 is optimal |
| `farm-weak` — weakest-first targeting | siege time falls with defender troops | **worse** (5,691), though it kills *more* tribes (87 vs 78) |

The last one is the sharpest: killing the weakest tribes maximizes *kills* but
loses the race, because the metric is reaching 80% **land** and
density-ascending targets the cheapest *land per troop* — the opposite of what
a kill-count proxy would choose. This is the framework's metric=gate
invariant paying off: a kill-count objective would have selected the losing
policy. `farm-p4` is therefore maximal over every policy knob.

### The one remaining lever: the body

`farm-p4` commands an externally-driven nation whose autopilot body is IH's
rhythm (`engine/externalBehavior.ts`, 52 / 0.38 / 0.15). Composing Agent A's
body with Agent B's orders would recover phase 1's gain — but only
**≤ 27 ticks** on a ~5,660-tick race (<0.5%), since a tribal map has little
neutral land and the race optimum beats IH by just 27 ticks. It requires an
engine behavior change (new tag + replay-loader wiring) that would alter the
externally-driven tapes. The cost outweighs a sub-0.5% edge, so it is
**flagged, not taken** — recorded here rather than done silently.

## Composed, both agents

Trigger order: aggressive opening (`tick ≤ 260`) → 1-tick race rhythm →
farm orders on tribe contact. Each stage is a no-op below its trigger, so the
stack equals Agent A on a clean map and adds Agent B's farming exactly when a
tribe borders. `framework.md`'s scaffold table is the authoritative
component view; this file is the pinnable agent-level view.
