Diplomacy parity slice: alliances, embargo, donate (TDD, adapter-only)

Gap: humans request/extend/break alliances, reject incoming requests,
embargo players, and donate gold/troops. The adapter had nothing. No game
code touched (vendor pristine); all seven ride production intent paths
through Executor.createExec.

New agent tools (auto-surfaced as game_*):
- order_alliance_request / order_alliance_reject / order_alliance_extend /
  order_break_alliance (nation-N / tribe-N labels to internal MappedIDs)
- order_embargo target start|stop
- order_donate_gold / order_donate_troops target amount

New projections: alliances, alliance_requests (incoming/outgoing pending),
embargoes — all in adapter labels, stable across death.

Production rules pinned by failing-then-passing tests:
- Alliance answers come from recipient AI on its own schedule: the Easy
  nation AI never answers, so requests sit pending then expire. The order
  is the parity bit, not the answer — same as a human asking.
- Donations are friendly-only (canDonateGold/Troops refuse strangers):
  accepted but land nothing without an alliance. Tests use 20k amounts to
  dwarf income, proving no deduction happened.
- Every order double-buffers: requests/embargoes materialise after ticks,
  so tests read them back after a decision, not from the order response.
- Reject answers only pending incoming requests; anything else is refused
  before touching the engine.

Evidence: tests/test_engine_diplo.py (11 passed: request recorded,
bad targets, embargo round-trip, bad action, donation refusals, bad
amounts, reject/break/extend validation), tests/test_match_diplo.py
(2 passed through real MCP stdio). Full gate 151 passed, ruff + ty clean.
