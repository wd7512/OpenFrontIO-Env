---
name: dev-workflow
description: Use when making a non-trivial code, test, configuration, or documentation change that should be planned, implemented, and verified end-to-end.
---

# Dev Workflow

Use this skill for disciplined Python project changes.

## Workflow

1. Scope the goal and inspect relevant files before editing.
2. Create or update tests for behavior changes.
3. Implement the smallest correct change.
4. Run formatting, linting, tests, and build checks.
5. Summarize what changed, why, and how it was verified.

## Standard Checks

```bash
uv run ruff format --check
uv run ruff check
uv run pytest
uv build
```

## Rules

- Use `uv` for all Python commands.
- Keep commits focused.
- Do not add dependencies without a clear reason.
- If evidence contradicts the plan, stop and revise the plan.
