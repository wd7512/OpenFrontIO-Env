# Episode TDD evidence

Real red/green command evidence for the vertical slice: real MCP lifecycle
tools (`start_smoke_game` / `get_overview` / `end_decision` / `close_game`) and
a keyless scripted-episode CLI (`python -m openfront_mcp.benchmark`).

The spec, `tests/test_episode.py`, landed first. It drives the packaged FastMCP
server over a **real stdio transport**, with a real pinned-engine worker behind
the server lifespan, and makes the CLI (`--config examples/smoke.json
--output <dir>`) do the same over a real tool session: no engine import, no
direct `EngineWorker` calls, no mocks.

## RED — module did not exist

Command:

```
uv run pytest tests/test_episode.py -q
```

Original pre-implementation output (excerpt, captured in the first OpenCode
run before the implementation writes). A later unnecessary replay temporarily
removed and restored the module; that replay is not the TDD evidence:

```
==================================== ERRORS ====================================
____________________ ERROR collecting tests/test_episode.py ____________________
ImportError while importing test module '/Users/williamdennis/repos/OpenFrontIO-Env/tests/test_episode.py'.
Traceback:
tests/test_episode.py:33: in <module>
    from openfront_mcp import benchmark
E   ImportError: cannot import name 'benchmark' from 'openfront_mcp' (/Users/williamdennis/repos/OpenFrontIO-Env/src/openfront_mcp/__init__.py)
=========================== short test summary info ============================
ERROR tests/test_episode.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.18s
```

The behaviour spec existed; neither `openfront_mcp/session.py`, the four
lifecycle tools, nor `openfront_mcp/benchmark.py` existed yet.

## GREEN — slice complete

```
uv run pytest tests/test_episode.py -q   # 19 passed in 7.90s
uv run pytest -q                         # 72 passed in 22.95s
uv run ruff check .                      # All checks passed!
uv run ruff format --check .             # 27 files already formatted
uv run ty check                          # All checks passed!
```

Real CLI run to a fresh output directory (exit 0, all three artifacts):

```
$ uv run python -m openfront_mcp.benchmark --config examples/smoke.json --output /tmp/openfront-episode-agent-verified-20260917-002738
episode complete: outcome=decision_cap exit=0 output=/tmp/openfront-episode-agent-verified-20260917-002738
```

`result.json`: `outcome=decision_cap`, `winner=null`, `source=scripted_not_llm`,
tick 2 → 152, 7 tool calls, 0 tool errors, PMR/RAG `null` with reason
`unavailable in smoke: ...`. `manifest.json`: `vendor_pin.matches=true` at
`v0.33.14` (`577819ba0e1e13ecdbc8dede2ba33de542c88a67`, verified via
`git rev-parse HEAD` in `vendor/OpenFrontIO`), hashes of the engine bundle
`engine/dist/worker.mjs`, the 3 pinned plains map assets, config, trace and
result. A second run to a different output path produces byte-identical
`result.json`, `trace.jsonl` and `manifest.json`.

## Second RED — reviewer-found gaps, fixed test-first

An independent review found six gaps; regression tests landed first and all
failed before the fix:

- `test_overview_is_controlled_human_state_not_engine_internals` — the start
  projection leaked the engine-internal id `engine-smoke-human`. Fixed by
  projecting the stable **public** id `human-1`, asserted as an exact dict, not
  a vague string check.
- `test_end_decision_rejects_non_integer_payloads_over_real_transport` — a bare
  `int` parameter lets FastMCP coerce `"1"`, `true` and `1.5` over the wire.
  Fixed with a `pydantic.StrictInt` annotation on the tool parameter, now with
  real-transport rejection tests for string/bool/float payloads.
- `test_cli_rejects_non_finite_or_non_positive_timeouts` /
  `test_timeout_validation_rejects_non_finite_and_non_positive` — `NaN`, `±inf`,
  `0` and negatives accepted. Fixed with `_positive_finite`, which requires
  `math.isfinite` and `> 0` for both `--tool-timeout` and `--connect-timeout`.
- `test_run_episode_exits_nonzero_on_vendor_pin_mismatch` /
  `test_run_episode_exits_nonzero_on_manifest_failure` — a mismatched actual
  vendor pin or a manifest build failure was written to disk but still exited 0.
  Fixed by pre-probing pinned-artifact integrity (`_manifest_probe`), folding any
  issue into the result (`outcome=error`, reason = first problem) and gating the
  exit code on it: an unsatisfied pin or failed manifest is now a nonzero exit,
  never a successful episode.

RED output (excerpt):

```
FAILED tests/test_episode.py::test_overview_is_controlled_human_state_not_engine_internals
FAILED tests/test_episode.py::test_end_decision_rejects_non_integer_payloads_over_real_transport
FAILED tests/test_episode.py::test_cli_rejects_non_finite_or_non_positive_timeouts
FAILED tests/test_episode.py::test_timeout_validation_rejects_non_finite_and_non_positive
FAILED tests/test_episode.py::test_run_episode_exits_nonzero_on_vendor_pin_mismatch
FAILED tests/test_episode.py::test_run_episode_exits_nonzero_on_manifest_failure
6 failed, 1 passed, 12 deselected in 2.00s
```

GREEN after the fixes:

```
19 passed in 7.91s
```

### Honest reason for the unavailable metrics

The first wording claimed PMR/RAG@10 "require tool-using LLM decisions". That is
wrong: scripted tool traces are scoreable for proactive-monitoring rate. The
real reason PMR and RAG@10 are `null` in this run is that the `scripted`
controller records **no strategic-query or commitment events**, so those two
metrics have nothing to score — now stated exactly that way in
`result.json:metrics.unavailable_reason`.

## Scope and limitations

- The scenario is explicitly labelled `single-human-smoke`: one human, no
  opponents, no victory claims. It exercises the production spawn + tick path
  only.
- `end_decision` advances exactly 50 sim ticks and returns only
  `{decision, tick}`; `get_overview` returns a controlled projected state —
  never engine hashes, asset paths or internal ids.
- One engine worker per server lifespan, serialized through a lock; the closing
  lifespan reaps the worker (verified by `pgrep -f dist/worker.mjs`).
- The CLI refuses to overwrite an existing output directory, writes all three
  artifacts atomically, and keeps the transport honest: every tool
  request/result/error is traced in order with its decision id and sim tick.
- Not yet covered: LLM controllers, extra scenarios, real PMR/RAG scoring,
  multi-human games, or transport failure recovery.