# Agent Instructions

This is a generic Python project template using `uv`, `ruff`, `ty`, and `pytest`.

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

## Overhaul tracks

- Python 3.12 + harbor==0.21.0 required (see pyproject when merged).
- Docker base: `docker/openfront/Dockerfile`; check via `scripts/build-openfront.sh --dry-run`.
- Harbor skeleton: `uv run openfront-harbor preflight/plan/reconcile/evidence --help`.
- Lit-review: `docs/lit-review/README.md`; dry-run batch only, lit-watch scoped commits.
- All overhaul paths are merge-guarded: skip cleanly when files are absent.
