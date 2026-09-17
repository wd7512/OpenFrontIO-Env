# Campaign evidence: two live Union Alpha campaigns, 1-1

Same model, same map, same prompt family — opposite strategies, opposite
outcomes. This is benchmark signal, not noise.

## Campaign 1: WIN (tick 503, winner "Smoke")

33 tool calls, 10 decisions. Expanded every decision with half-troop waves
(12k → 38k), tiles stalled 7,461 → 7,461 at tick 453, switched to nation-1
with 60,277 troops. The strike landed (shared border, immunity long over),
took 639+ tiles → 8,100/10,000 (81%) → production WinCheck fired.
Overview before every order: 10 for 10.
Artifacts: Downloads/openfront-campaign-20260917-1600
(first run; second run reused the name after the stale dir was cleared).

## Campaign 2: LOSS (45 decisions, no winner, 2,938 vs 7,062)

130 tool calls, all 2,253 ticks. Attacked nation-1 from tick 103 (border
contact, only 1,728 tiles) with 15–24k waves that never accumulated while
the nation outgrew it (900 → 4,300 by tick 753). One all-in wave (70k at
tick 1253) collapsed troops to 1,666; rebuilt, ground on, lost slowly.
Root cause in the harness, not the agent: the Phase 2 trigger
(borders_human AND not immune) is satisfied at first contact and invites
early grinding. Fixed: Phase 2 now requires tiles stalled across two
consecutive overviews AND the flags.

## Scripted baselines (pinned engine, deterministic)

- Passive human: nation wins ~tick 753 (test_match_full.py, through tools).
- Timid expand (5k/wave): permanent stalemate 3,315 vs 6,685 (no winner to
  tick 2,000+); nation never attacks first on easy.
- Small-wave nation attacks from contact: counter-attacked into a loss
  ~tick 2,253.
- Winning recipe (test_winning_recipe_expand_to_contact_then_strike):
  half-troop expands to the stall, then half-troop strikes → human wins.
  Reproduces campaign 1 deterministically at engine level.

## Observability fix (the actual bug)

Attack orders that fizzle (immunity, no shared border) die silently inside
AttackExecution by production design. Nation projections now carry `immune`
and `borders_human` (production Player predicates, observation only, zero
behavior change) so the agent can see preconditions instead of ordering
blind. Pinned in test_nation_projection_exposes_immune_and_border_flags.
