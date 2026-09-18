# Overhaul integration ledger

Tracks how the overhaul reached `research_overhaul`, including the
mainline merge below. CI and agent wiring were merge-guarded
(`if [ -f ...]`) until everything landed.

## Branch → contents

- `overhaul/docker-base`: `docker/`, `docs/docker-runbook.md`, `tests/test_docker.py`.
- `overhaul/harbor-skeleton`: Python 3.12, `harbor==0.21.0`,
  `tests/test_harbor_dep.py`, plus skeleton + runner + grids + runbook
  (`src/openfront_harbor/`, `config/`, `jobs/`, `tasks/`,
  `docs/evidence-run-folders-runbook.md`). (The `harbor-deps` branch was
  folded into this branch's dependency commit and deleted.)
- `overhaul/lit-review`: `docs/lit-review/` (single `iter_1/` pass +
  lit-watch intake) + 3 test files (`tests/test_lit_review.py`,
  `tests/test_lit_batch.py`, `tests/test_lit_watch.py`).
- Process/example refactors (on this branch): harbor gates take the
  example as input (`example.py`); benchmark core takes an episode
  driver (`episodes/`, smoke as the example).

## Merge history

1. Tracks merged into `research_overhaul` in order: docker-base →
   harbor-skeleton → lit-review → integration wiring.
2. `origin/main` merged into `research_overhaul`: main had pruned to the
   smoke gate + EU solo experiment (deleted `prompts/match.md`,
   `prompts/campaign.md`, `prompts/smoke.md`, `src/openfront_mcp/scenarios.py`,
   `list_scenarios`; renamed the playing agent Smoke → Agent). The only
   manual resolution was `tests/test_live_smoke.py` (main's solo-only
   `run()` signature + the branch's tmp-env hardening). Research
   questions mentioning 1v1/campaign ladders stay verbatim: the prune is
   an implementation decision, and future stages remain legitimate
   research targets.

## Verification

- `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`.
- Full `uv run pytest` with engine build (`engine/dist/worker.mjs`).
- `bash scripts/build-openfront.sh --dry-run`.
- `uv run openfront-harbor preflight`.
- `uv run pytest tests/test_lit_review.py tests/test_lit_batch.py tests/test_lit_watch.py -q`.

## Live-gate policy

No live harbor run, no LLM batch, no docker push until the task spec is amended.
