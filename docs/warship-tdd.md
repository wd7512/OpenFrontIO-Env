Warship maneuver slice: order_move_warship (TDD, adapter-only)

Gap: humans retarget warships to new patrol tiles. The adapter had no
move order (positions were already projected under units). No game code
touched (vendor pristine); the order rides the production move_warship
intent (MoveWarshipExecution) through Executor.createExec.

New agent tool (auto-surfaced as game_*):
- order_move_warship unit_id x y (id must be a live human warship)

Production rules pinned by failing-then-passing tests:
- Full chain is human-identical: expand to shore, earn 600k, finish a
  port (125k), float the warship (250k) at water in the port's component.
  Pinned tiles on Britannia compact (seeded): port (540,860), warship
  water (500,880), patrol (700,1000).
- Retargets only land on water in the warship's component AND only once
  the ship has sailed off its (land) port tile — earlier orders are
  silently ignored, same as human clicks.
- The first test draft asserted mere movement, but warships drift on
  patrol uncommanded (control run proved it). Hardened: ordered end
  (733,962, dist ~50) vs no-order end (494,1008) — convergence, not
  motion, proves landing.
- Non-warship ids and bad coords reject before touching the engine.

Evidence: tests/test_engine_warship.py (4 passed), tests/test_match_warship.py
(2 passed through real MCP stdio). Full gate 157 passed, ruff + ty clean.
