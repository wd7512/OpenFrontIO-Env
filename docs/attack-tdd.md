# Attack orders TDD evidence

First agent moves: `order_attack` (expand vs TerraNullius, attack vs
nations) through the production intent path, test-first throughout.

## RED

`tests/test_engine_attack.py` landed before `EngineWorker.attack`
existed: 3 failed (`AttributeError`).

## Production findings (pinned engine, verified live)

- Orders flow: stamped intent -> `Executor.createExec` -> `AttackExecution`
  (the same path live client turns take). `TerraNullius.id()` is null, so
  an attack with null targetID *is* expansion — how live clients grow.
- An order during nation spawn immunity (50 ticks) fizzles silently at
  init (`canAttackPlayer` false, execution deactivates). Live orders belong
  after tick 50.
- A nation attack with no shared border fizzles by design
  (`refreshToConquer` finds nothing -> retreat, troops returned). The human
  must expand until fronts meet before nation attacks can land.
- Added executions init at the tail of the next tick (GameImpl
  double-buffering): attacks are observable only after advancing.

## GREEN

- `engine/worker.ts`: `attack` command (`expand` -> null targetID,
  `nation-N` -> internal player id, validated); snapshot `attacks` from
  `player.outgoingAttacks()` (non-player target labelled `terra-nullius`).
- `engine.py`: `attack(target, troops)` passthrough; worker-side validation.
- `session.py`: `order_attack` with session-level validation against live
  targets; projections gain `attacks` (target/troops/retreating, no engine
  internals).
- `server.py`: `order_attack` tool (StrictInt troops).
- `live_smoke.py`: match prompt orders expand-then-advance per decision,
  capped at half current troops.
- Tool tests (`test_match_1v1.py`): bad targets/troops rejected as tool
  errors; expand-then-observe grows tiles through real tools.

Full gate: 100 passed; ruff/format/ty clean.

## Live 1v1 with orders (Union Alpha, free model, cost 0.0)

17/17 tool calls, 6 decisions, ticks 3 -> 303, exit 0. The agent issued an
expand order every decision and grew 52 -> 1,929 tiles; the nation grew to
3,164. No winner by 303 (nation wins near 750 in engine-only play).

Artifacts: /Users/williamdennis/Downloads/openfront-attack-20260917-1530
(live_result.json, redacted events).
