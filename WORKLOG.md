# OpenFrontBench worklog

## 2026-09-18 — dev-tools hygiene check + WORKLOG started

- Ported `dev-tools check` from the custom-harbor harness as `openfront-harbor dev-tools check`: worklog format, duplicate test names, character encoding. Test-layout check deliberately not ported — `tests/` is a flat tree that does not mirror `src/`, so a mirror check needs a test-tree migration first.
- Char-encoding skips `vendor/`, `cycles/`, `raw/` (third-party / runtime data, not source).

## 2026-09-18 — renamed python-template/openfront_mcp to openfrontbench

- `src/openfront_mcp/` moved to `src/openfrontbench/` (113 references updated across source, tests, scripts, Dockerfile, runbooks); stale `src/python_template/` deleted; `tests/test_import.py` became `tests/test_package.py` against the real package; project name `openfrontbench` in `pyproject.toml`.
- Gates green (ruff, ty, 247 pytest); `uv build` emits `openfrontbench-0.1.0` with only the name-matched module inside — same single-module behaviour as before (`openfront_harbor` never shipped in the wheel either).

## 2026-09-18 — AGENTS.md and README de-templated

- AGENTS.md intro now names the repo (was generic template boilerplate); overhaul-tracks section collapsed to a two-line pointer, detail lives with the code. README title `# OpenFrontBench`, package description updated. Project name rename deferred at the time (uv_build infers the src module from it), then done as the rename above.

## 2026-09-18 — merged origin/main into research_overhaul

- Main had moved on (smoke-to-solo ladder prune, Smoke-to-Agent rename, replay website, raw folder, solo FFA cycles); merged as `7f39f37`, resolved `tests/test_live_smoke.py` toward solo-only, full suite green, PR mergeable.

## 2026-09-18 — process-vs-example refactors across harbor and benchmark

- `openfront_harbor` gates take the worked example as explicit input (`example.py` holds domain values; `plan_run`/`preflight` take ports, URL template, versions, file lists). Benchmark core takes an episode driver (`episodes/` protocol + `SmokeDriver`); `benchmark.py` is generic.

## 2026-09-18 — lit-review collapsed to iter_1, de-specified from sibling harness

- Deleted placeholder `iter_2+`, unearned syntheses/proposals, theme briefs; kept `iter_1/` (one real paper + notes + batch tooling) and generic lit-watch machinery with sandbox TODOs. Rule going forward: no `iter_N` without running the work; process kept, implementation isolated to the worked example.

## 2026-09-18 — vendor pin fixed at v0.33.14

- Pinned commit `577819ba` recorded in the submodule, `docs/pins.md`, and `pins.py`; docker build cross-checks the pin at image build time.

## 2026-09-18 — overhaul tracks T1-T9 merged into research_overhaul, PR opened

- Docker base (local-only tags, never pushed), Python 3.12 + `harbor==0.21.0`, harbor skeleton (CLI/preflight/job_spec/ledger/runner/reconcile/evidence), lit scaffold + batch runner + lit-watch, guarded CI + agent wiring. One branch (`research_overhaul`), PR #4 to main.
