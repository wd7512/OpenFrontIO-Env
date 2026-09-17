Combat parity slice: tribes, cancel attack, boats (TDD, adapter-only)

Gap: humans can attack tribes, retreat attacks, and launch/recall boats.
The adapter exposed expand + nation-N only. No game code touched
(vendor pristine at 577819b); all four ride production intent paths
through Executor.createExec.

New agent tools (auto-surfaced as game_* via the MCP server name):
- order_attack target tribe-N (same AttackExecution path as nations)
- order_cancel_attack attack_id (cancel_attack -> RetreatExecution)
- order_boat_attack x y troops (boat -> TransportShipExecution)
- order_cancel_boat unit_id (cancel_boat -> BoatRetreatExecution)

New projections: tribes_list (tribe-N, stable numbers across death and
late spawns), boats (id, troops), attack ids (required for cancel).

Production rules pinned by failing-then-passing tests:
- Tribe/nation attacks with no shared border retreat silent (test expands
  to contact first, same constraint as nations).
- Executions double-buffer: orders materialise after ticks run; cancel
  targets ids seen in a post-tick overview.
- Tribes (Bot type) are never immune; nations keep spawn immunity.
- Boats need shore + water; the engine validates the tile, the adapter
  checks integer bounds. Launch proven at Britannia compact (400, 1041)
  after expansion to shore; seeded spawn keeps it deterministic (0.14s).
- cancel_boat schema wants a numeric unit id; the worker resolves it.

Evidence: tests/test_engine_combat.py (8 passed: tribe hurt, bad tribe
rejected, cancel retreats, bad cancel rejected, boat launches, bad coords
rejected, cancel accepted, bad boat rejected), tests/test_match_combat.py
(3 passed through real MCP stdio). Full gate 128 passed, ruff + ty clean.
