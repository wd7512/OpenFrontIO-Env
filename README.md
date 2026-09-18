# python-template

OpenFront OpenFrontIO-Env: a keyless MCP benchmark harness over a pinned
OpenFrontIO engine core.

It uses Python 3.12, `uv`, `ruff`, `ty`, `pytest`, and optional agent support for
AI-assisted development.

## Setup (exact)

```bash
uv sync --dev
cd engine && npm ci && npm run build && cd ..   # builds engine/dist/worker.mjs from vendored core
```

The engine worker must be built before any tool or test touches the engine. The
vendored core is pinned in detached-head mode (`vendor/OpenFrontIO`), recorded
in `docs/pins.md` and verified by the manifest at runtime.

## Smoke episode CLI (no LLM, no API key)

```bash
uv run python -m openfront_mcp.benchmark --config examples/smoke.json --output <fresh-dir>
```

Exits 0 and writes three artifacts into `<fresh-dir>`:

- `result.json` — outcome (`decision_cap`), ticks, tool stats, `winner: null`,
  metrics (`PMR`/`RAG@10` are `null` in smoke — see the `unavailable_reason`).
- `trace.jsonl` — order-preserving trace of every tool request/result/error
  with decision id and sim tick.
- `manifest.json` — hash of the engine bundle, pinned map assets, config, trace
  and result, plus a live check that the actual vendor commit matches the pin.

The controller is `scripted`: `start_smoke_game` → `get_overview` →
`end_decision` ×N → `get_overview` → `close_game`, driven over a real MCP stdio
session with no direct engine access. Refuses to overwrite an existing output
dir; a tool timeout, manifest failure or vendor-pin mismatch exits nonzero with
a failure artifact.

## Development Commands

```bash
uv run ruff format
uv run ruff check
uv run ty check
uv run pytest
uv build
```

## What Is Included

- `src/` package layout
- `uv` dependency management
- `ruff` formatting and linting
- `ty` type checking
- `pytest` test discovery
- GitHub Actions CI
- Generic agent instructions in `AGENTS.md`
- Optional OpenCode config, agents, skills, and plugins under `.opencode/`

## Optional Agent Support

This template works as a normal Python project without OpenCode. If you use
AI coding agents, the repository also includes:

- `opencode.json` with conservative default permissions and useful commands
- `.opencode/agents/python-engineer.md` for focused Python implementation work
- `.opencode/agents/research.md` for read-only academic research (CrossRef/OpenAlex/PubMed MCPs, disabled by default)
- `.opencode/skills/dev-workflow` for planned, verified changes
- `.opencode/skills/grill-me` to stress-test a plan before implementation
- `.opencode/skills/code-review` for actionable code reviews
- `.opencode/skills/session-retro` to capture lessons and follow-ups
- `.opencode/skills/caveman` for terse technical communication
- `.opencode/plugins/write-size-guard.ts` to prevent oversized generated writes
- `.opencode/skills-available/brooks/` with the full opt-in brooks-lint review suite

Optional telemetry plugins live in `.opencode/plugins-available/`. Copy one into
`.opencode/plugins/` and restart OpenCode to enable it.

## Overhaul tracks

When merged from overhaul/* branches: docker via `docs/docker-runbook.md`, harbor runs via `docs/evidence-run-folders-runbook.md`, lit-review via `docs/lit-review/README.md`.

## Limitations

- The only supported scenario is `plains-human-smoke`: **one human, no
  opponents, no victory claims**. It exercises the production spawn + tick
  path, nothing more.
- `end_decision` advances exactly 50 sim ticks; `get_overview` is a pure query.
  Tools never accept paths and return a controlled projection of human state —
  no engine hashes, asset paths or internal ids.
- PMR and RAG@10 are not computed in smoke runs: the scripted controller
  records no strategic-query or commitment events. LLM controllers, multi-human
  games and real metric scoring are not implemented yet.
- Documentation and evidence for the engine worker and this episode slice live
  in `docs/engine-tdd.md` and `docs/episode-tdd.md`.
