# 1v1 match TDD evidence

Real MCP tool `start_1v1_game` (human vs 1–4 production nations) plus live
Union Alpha match, test-first throughout.

## RED

`tests/test_match_1v1.py` landed before the tool existed:

```
Tool 'start_1v1_game' not listed, no validation will be performed
2 failed
```

## GREEN

- `src/openfront_mcp/session.py`: `GameSession.start(nations, difficulty)`
  with tool-level cap (0–4) and difficulty validation; projections add
  `nations` (stable `nation-N` ids, no engine internals) and `winner`;
  smoke projections gain empty `nations` + null `winner`.
- `src/openfront_mcp/server.py`: `start_1v1_game` (StrictInt, 1–4, rejects
  0/bools/strings at the transport); bad params are tool errors and the
  session survives for a clean start afterwards.
- `src/openfront_mcp/live_smoke.py`: `scenario="1v1"` + `max_decisions`
  (1–20) with `build_match_prompt`; scenario recorded in the payload.
- `tests/test_episode.py`: smoke key-set assertions updated for the two
  new projection keys.

Full gate: 95 passed; ruff/format/ty clean.

## Live 1v1 (Union Alpha, free model, cost 0.0)

11/11 tool calls, 6 decisions, ticks 3 → 303, exit 0, ~83s of model events.
The agent reported both sides per observation and disclosed two things
unprompted: it made one extra overview call after decision 3 (deviating
from the script), and marked unobserved decisions "Not observed" rather
than inventing numbers. No winner by tick 303 (nation 3,565 tiles and
growing; passive human static at 52) — consistent with the engine-only
1v1 where the nation wins around tick 753.

Artifacts: /Users/williamdennis/Downloads/openfront-1v1-20260917-1500
(live_result.json, redacted events).
