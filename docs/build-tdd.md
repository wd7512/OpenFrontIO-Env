Build parity slice: order_build/upgrade/delete + units (TDD, adapter-only)

Gap: humans build from the PlayerBuildable menu, upgrade structures, and
delete units. The adapter had nothing. No game code touched (vendor
pristine); all three ride production intent paths through
Executor.createExec.

New agent tools (auto-surfaced as game_*):
- order_build unit x y (build_unit -> ConstructionExecution). Kebab names:
  city, defense-post, sam-launcher, missile-silo, port, factory,
  atom-bomb, hydrogen-bomb, mirv, warship. (Transport ships already have
  the boat tools, so they stay out of the menu.)
- order_upgrade_unit unit_id (upgrade_structure -> UpgradeStructureExecution)
- order_delete_unit unit_id (delete_unit -> DeleteUnitExecution)

New projection: units (id, type, level, x, y, troops, under_construction)
for all human units except transports (those live under boats).

Production rules pinned by failing-then-passing tests:
- Economy gates everything: defense post ~50k, city 125k base doubling
  per built unit (cap 1M). Broke orders are accepted but land nothing —
  same as a human clicking with no gold. Tests fund a 10k-tile economy
  first (deterministic on plains).
- Only port / missile-silo / sam-launcher / city / factory are upgradable
  (defense posts are not — production config, tested the refusal path by
  picking the wrong unit first).
- Structures construct over ticks (defense post 50); under-construction
  units can neither be upgraded nor deleted (SECURITY guards).
- Deletion has a ~150-350 tick grace period before removal.
- Nuke orders ride the same build path with the target tile; acceptance
  (not detonation) is the parity contract.

Evidence: tests/test_engine_build.py (8 passed: build, bad unit/coords
rejected, city upgrade 1->2, bad upgrade rejected, delete removes, bad
delete rejected, nuke accepted), tests/test_match_build.py (2 passed
through real MCP stdio). Full gate 138 passed, ruff + ty clean.
