# Agent Instructions

This is a generic Python project template using `uv`, `ruff`, `ty`, and `pytest`.

Requires Python 3.12 (`uv` reads `.python-version`); `harbor==0.21.0` is a required runtime dependency.

## Commands

- Install dependencies: `uv sync --dev`
- Format: `uv run ruff format`
- Lint: `uv run ruff check`
- Type check: `uv run ty check`
- Test: `uv run pytest`
- Build: `uv build`

## Rules

- Use `uv` for dependency management and command execution.
- Keep changes small and focused.
- Add or update tests for behavior changes.
- Run `uv run ruff check`, `uv run ty check`, and `uv run pytest` before finishing code changes.
- Do not add runtime dependencies unless they are required by package behavior.
- Prefer clear, boring Python over clever abstractions.
- Use `logging` (stdlib) for all output — never `print()`. Configure via `logging.basicConfig()` in entry points.

## Worktrees

- Create worktrees only under `.worktrees/` (`git worktree add .worktrees/<name> -b <branch> origin/main`).
- Before every commit, `git branch --show-current` must match the intended branch.

## Optional Agent Support

- `opencode.json` configures project-local OpenCode behavior.
- `.opencode/agents/` contains reusable OpenCode agents (`python-engineer`, `research` with CrossRef/OpenAlex/PubMed MCPs disabled by default).
- `.opencode/skills/` contains reusable workflow skills for AI-assisted development.
- `.opencode/skills-available/brooks/` contains the full opt-in brooks-lint review suite.
- `.opencode/plugins/write-size-guard.ts` prevents oversized generated writes.
- `.opencode/plugins-available/` contains optional telemetry plugins that can be copied into `.opencode/plugins/` when desired.

## Tracks

- Docker base: `docker/openfront/Dockerfile`; check via `scripts/build-openfront.sh --dry-run` (local tags only, never pushed).
- Harbor gates: `uv run openfront-harbor preflight/plan/reconcile/evidence --help` (dry-run/keyless only).
- Lit-review: `docs/lit-review/README.md`; dry-run batch only, lit-watch scoped commits.

## Conventions

- Process vs example: generic machinery takes explicit inputs and names no domain values. Domain specifics live in exactly one worked example each: `src/openfront_harbor/example.py` + `tasks/plains-smoke`, `src/openfront_mcp/episodes/smoke.py`, `docs/lit-review/iter_1/`. Process tests use synthetic fixtures; only `example_*`/smoke tests touch real files.
- Research honesty: `docs/lit-review` holds one real pass (`iter_1/`). Never add `iter_N/`, syntheses, or proposals without running the work; no placeholder scaffolding that implies done work.
- Live gates: no live harbor runs, LLM batch runs, or docker pushes until the task spec is amended. Keyless CI only.
