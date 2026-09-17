# Engine worker TDD evidence

Real red/green command evidence for the JSONL engine worker
(`engine/worker.ts`) and its Python wrapper (`src/openfront_mcp/engine.py`).

Scope: one human smoke fixture on the genuine pinned `plains` test asset
(100x100, all land). The worker boots the vendored production core
(`Config`, `genTerrainFromBin`, `createGame`, `Executor`), spawns the human
through the production `SpawnExecution` (which queues the production
`PlayerExecution`), and advances the real tick loop. No `TestConfig`, no mocks.

Truthful scope note: `GameRunner` is **not** used. With one human and no bots,
nations, or win checks, `createGame` + an `Executor`-built spawn intent +
`GameImpl.executeNextTick()` reproduce the same production tick path that
`GameRunner` would drive. Adding `GameRunner` would mean standing up its turn
queue and callback plumbing for no additional simulation coverage in this
fixture. That remains a follow-up if multiplayer/turn handling is needed.

## RED

Command:

```
uv run pytest tests/test_engine_worker.py -q
```

Output (excerpt):

```
==================================== ERRORS ====================================
_________________ ERROR collecting tests/test_engine_worker.py _________________
ImportError while importing test module
'/Users/williamdennis/repos/OpenFrontIO-Env/tests/test_engine_worker.py'.
tests/test_engine_worker.py:20: in <module>
    from openfront_mcp.engine import EngineError, EngineWorker
E   ModuleNotFoundError: No module named 'openfront_mcp.engine'
=========================== short test summary info ============================
ERROR tests/test_engine_worker.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.04s
```

The behaviour test landed first; neither the Python subprocess wrapper nor the
engine worker existed yet.

## GREEN

Command:

```
uv run pytest tests/test_engine_worker.py -q
```

Output:

```
..........                                                               [100%]
10 passed in 0.63s
```

Full gate:

```
uv run pytest -q          # 53 passed in 15.24s
uv run ruff check .       # All checks passed!
uv run ruff format .      # 1 file reformatted, then clean
uv run ty check           # All checks passed!
```

### Production-derived expectation correction (1 → 2 ticks)

The RED spec guessed `EXPECTED_START_TICK = 1`, assuming a single
`executeNextTick()` would both initialise and run the spawn intent. The real
core contradicts that: `GameImpl.addExecution` pushes onto `unInitExecs`, and
`GameImpl.executeNextTick` only `init()`s those executions at the *tail* of a
tick (`src/core/game/GameImpl.ts:481-506`). A spawn intent therefore lands
terrestrially on the tick **after** it is added. The worker drives the loop
until `inSpawnPhase()` ends (bounded by `MAX_SPAWN_TICKS`) rather than
hard-coding a count, and the test constant was corrected to `2` to match
production. Production code was not altered.

### What the worker exercises

- `Config` (production, not `TestConfig`), including the unset `startingGold`
  default (`GameConfigSchema.startingGold` is optional with no default, so
  `Config.startingGoldFor` returns `0n`; snapshot gold is `"0"`).
- `genTerrainFromBin(manifest.map, map.bin)` and `manifest.map4x`/`map4x.bin`.
- `createGame(humans, [], ...)` + `Executor.createExec({type: "spawn"})` — the
  same intent path a live turn uses.
- Real `executeNextTick()` ticks; `advance(50)` grows both troops and gold via
  the production `PlayerExecution`.

### Determinism and error handling

- `test_fresh_instances_are_identical` boots the worker twice and asserts the
  start and post-`advance(50)` snapshots match exactly.
- `test_invalid_advance_is_rejected_and_engine_survives` checks `0`, `-1`,
  `1.5`, `True`, and `10**9` (including the bool-is-int edge) all raise
  `EngineError` while the worker stays usable.
- `test_missing_engine_bundle_raises_actionable_error` points `engine_dir` at an
  empty dir and asserts the message names both the engine bundle and `npm`.

Build command for the bundle (pinned deps in `engine/package.json`,
`esbuild` bundling the vendor TypeScript; vendor tree untouched):

```
cd engine && npm ci && npm run build
```

## Independent verification after dependency audit

Hermes reran the real subprocess tests and the full gate after updating
DOMPurify to 3.4.15 and nanoid to 5.1.16 (the initially selected versions had
npm advisories). No vendor files were changed.

- `npm run build`: succeeded.
- `npm audit`: found 0 vulnerabilities.
- `uv run pytest -q`: 53 passed in 15.13s.
- Ruff check/format check and ty check: passed.
- Direct real-engine smoke: tick 2, 52 owned tiles, 25,000 troops, gold 0;
  after 50 ticks: tick 52, 52 tiles, 43,407 troops, gold 5,000.

This is one human with no opponents, actions or victory check. It is not a
complete game, an MCP gameplay integration test, or an LLM evaluation.
Transport failure recovery, installed-package asset discovery and full
benchmark initialization still require follow-up tests and implementation.
