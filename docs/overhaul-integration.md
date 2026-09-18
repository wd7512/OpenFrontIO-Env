# Overhaul integration ledger

Merge-aware glue for T1–T8. CI and agent wiring skip cleanly pre-merge
(`if [ -f ...]`) and activate post-merge when files land.

## Branch → contents

- `overhaul/docker-base`: `docker/`, `docs/docker-runbook.md`, `tests/test_docker.py`.
- `overhaul/harbor-deps`: Python 3.12, `harbor==0.21.0`, `tests/test_harbor_dep.py`.
- `overhaul/harbor-skeleton`: skeleton + runner + grids + runbook
  (`src/openfront_harbor/`, `config/`, `jobs/`, `tasks/`,
  `docs/evidence-run-folders-runbook.md`).
- `overhaul/lit-review`: `docs/lit-review/` + 4 test files
  (`tests/test_lit_review.py`, `tests/test_lit_batch.py`,
  `tests/test_lit_synthesis.py`, `tests/test_lit_watch.py`).

## Merge order

T1 (docker-base) → T2 (harbor-deps) → skeleton → lit-review → this (T9).

## Known conflict points

- `pyproject.toml`: `[project.scripts]` + `requires-python` + harbor dep overlap.
- `AGENTS.md`: overhaul section vs T2 line; keep one section on merge.
- `uv.lock`: regen once at merge, not per-branch.
- `README.md`: Python 3.12 line (T2 follow-up, done here).

## Post-merge verification

- `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`.
- Full `uv run pytest` with engine build (`engine/dist/worker.mjs`).
- `bash scripts/build-openfront.sh --dry-run`.
- `uv run openfront-harbor preflight`.
- `uv run pytest tests/test_lit_review.py tests/test_lit_batch.py tests/test_lit_synthesis.py tests/test_lit_watch.py -q`.

## Live-gate policy

No live harbor run, no LLM batch, no docker push until the task spec is amended.
