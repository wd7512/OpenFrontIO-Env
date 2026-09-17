Turn recording slice: replay tape for future game-interface viewing (TDD, adapter-only)

Why: the real game UI only replays server-archived games (GameRecord with
per-tick intent turns). Local/singleplayer games record nothing, and neither
did our worker — the tape for past games does not exist and cannot be
reconstructed. This slice starts the tape so future games can be viewed.

What: every stamped human intent is buffered at submission and bucketed per
executed game tick ({turnNumber, intents}), the production archive shape.
`save_record` returns {gameId, mapDir, ticks, players, turns} and writes
record.json when OPENFRONT_RECORD_DIR is set. The live runner sets it to the
run dir; the session persists the tape every decision, so even killed runs
keep their history. Recording is observer-only: submit() adds the identical
execution down the identical path — the full suite (169) passing unchanged
is the proof.

Pinned: spawn intent taped during start (before the game handle is stored);
empty turns recorded like the server (turnNumbers dense, unique); no-env is
pure in-memory no-op.

Not yet: feeding the tape to the real client (GameRecord construction +
client serving + archive stub) — its own slice. Grid frames remain the
viewer for now.

Evidence: tests/test_engine_record.py (3 passed). Full gate 169 passed,
ruff + ty clean.
