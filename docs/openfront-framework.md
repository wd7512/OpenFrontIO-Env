# OpenFront Framework — CivBench mirror and build plan

Companion to docs/paper-summary.md (CivBench, arXiv 2609.02459). Same 8-section shape,
mapped onto OpenFront.io. Upstream pin: v0.33.14 (577819b) at vendor/OpenFrontIO,
see docs/pins.md. Reference copy of the Civ VI implementation: ~/repos/civ6-mcp
(commit dd20190, v1.1.11) — examined 2026-09-10, findings below are from that tree.

---

## 1. Contribution & Benchmark Design (expected)

CivBench evaluates LLM agents in long-horizon, tool-mediated Civ VI via MCP:
76 tools, 300+ turn episodes, narration layer, PMR and RAG@10 metrics.

OpenFrontBench (working name) does the same for OpenFront.io:

1. **Benchmark environment** — MCP benchmark for full OpenFront games with fixed
   scenarios (map, nation count, difficulty mix, seeds), structured logs.
2. **Narration protocol** — structured text observations from the deterministic
   core; separate information availability from retrieval, as CivBench does.
3. **Behavioural metrics** — port PMR (proactive monitoring rate) and RAG@10
   (reflection-action gap); definitions adapted in section 4.
4. **Empirical characterisation** — runs across model families on shared scenarios.

Design philosophy carried over verbatim: the agent only knows what it explicitly
queries. Attention allocation becomes measurable from traces.

## 2. Agent Architecture (expected)

Single LLM agent vs built-in bot nations, same as CivBench's agent-vs-AI setup.
Shared versioned playbook: per-decision loop, checkpoints, five-field diary
(tactical / strategic / tooling / planning / hypothesis).

Tick-grid finding that shapes this: matching Easy cadence (65-100 ticks) is enough
to compete; spawn position dominates difficulty. The LLM's edge comes from when to
attack and whom, not from acting faster. So the framework uses coarse action
cadence (~50 ticks, 5s decision window) rather than per-tick control.

## 3. Reference implementation: civ6-mcp (verified)

From the ~/repos/civ6-mcp tree, the shape to mirror:

- `src/civ_mcp/server.py` (2,923 lines) — FastMCP server, lifespan pattern,
  persistent TCP connection to the live game via FireTuner. 76 tools confirmed
  by `@mcp.tool` count. Every tool returns human-readable string.
- `src/civ_mcp/narrate.py` (2,104 lines) — pure narration functions,
  data in / string out, no I/O. This is the layer to copy most closely.
- `src/civ_mcp/lua/` — one query module per domain: units, cities, map,
  diplomacy, economy, tech, religion, congress, victory, governance,
  espionage, overview, notifications. OpenFront equivalent: one module per
  core domain (territory, troops, neighbours, structures, intents).
- Supporting: `connection.py` + `tuner_client.py` (transport), `game_state.py`
  (cached state), `diary.py` (persistent memory), `end_turn.py` (autosave,
  empire warnings, victory scan), `autosave.py`, `game_launcher.py`,
  `game_lifecycle.py`, `game_over_watchdog.py`, `heartbeat.py`, `logger.py`,
  `telemetry.py`, `spatial.py`, `map_capture.py`, `spectator.py`, `web_api.py`.
- `evals/` (251-line metrics.py, 594-line civbench.py, plus runner.py,
  scenarios.py, scorer.py, prompts.py, scanners/, saves/) — harness plus
  PMR/RAG scoring. `fixtures/` demo traces, `web/` Next.js dashboard,
  `AGENTS.md` agent playbook with turn loop and strategic checkpoints.
- Transport note: Civ VI needs FireTuner TCP because the game is closed-source
  and live. OpenFront's `src/core` is deterministic pure TypeScript with no
  dependencies — we can call it directly (headless) instead of a TCP bridge,
  and reserve the browser client for verification (the option-1 split already
  proven in the phase-2 work: train headless, verify in Pixi client).

Proposed OpenFront tree:

- `src/openfront_mcp/server.py` — FastMCP server, tools against vendored core
- `src/openfront_mcp/narrate.py` — pure formatting, mirrors narrate.py
- `src/openfront_mcp/core_queries/` — per-domain readers over src/core state
- `src/openfront_mcp/diary.py`, `end_turn.py` (decision-point warnings),
  `game_state.py`, `logger.py`, `telemetry.py` — ported, trimmed
- `evals/` — scenarios (map/nations/difficulties/seeds), runner, scorer
  (PMR/RAG adapted), prompts
- `AGENTS.md` playbook — decision loop, diary fields, checkpoints

## 4. Key Metrics (ported)

- **PMR (proactive monitoring rate):** `strategic_monitoring_calls /
  non_infrastructure_calls`. CivBench aggregate: 0.96-2.13%; victory monitoring
  0.05-0.29%. OpenFront adaptation: territory/scoreboard/threat queries over
  total calls; expect the same under-monitoring failure until the playbook
  enforces schedules.
- **RAG@K (reflection-action gap):** `(Y + 0.5P) / total_commitments` over K
  decision points. CivBench: 48.2-65.8%. OpenFront adaptation: commitments like
  "attack X in N ticks", "expand to region Y", "check leader progress" —
  labelled from diary + traces, same pipeline.
- **Outcome stats first:** wins across seeds per scenario, with the tick-grid
  lesson recorded — Easy beats Impossible on some seeds, so scenarios must fix
  seeds and report per-seed outcomes, not just aggregates.

## 5. Limitations (known upfront)

- Headless-vs-browser gap: phase-2 work showed training-distribution maps
  (plains) vs real client maps (World) break policies; scenarios must be shared
  between harness and client from day one.
- Scale: full games run thousands of ticks; episodes cost time and API calls.
  Start with small maps (10-40k land tiles) where the heuristic teacher wins.
- Licence/environment: needs Node + tsx for core, Chromium for client
  verification; no commercial licence problem (OpenFront is open-source,
  unlike Civ VI).
- Metrics depend on LLM-assisted labelling (CivBench κ=0.879); same caveat here.

## 6. Cross-References

- CivBench paper + civ6-mcp repo: see docs/paper-summary.md sections 1-8.
- Tick-grid research (LLM_AGENT_RESEARCH.md in openfront-tick-grid): tick
  cadence, difficulty fairness, spawn dominance, 1v1 mode, LLM agent design
  with minimal-vs-full-map observation question still open.
- Phase-2 artefacts (playground/openfrontio-rl): browser-eval.mjs headless/
  browser split, DAgger policies, shared-map requirement.

## 7. Design Implications & Next Steps

1. Enforce monitoring schedules in the playbook from the start (CivBench shows
   guidance alone does not produce monitoring).
2. Structured commitment tracking (diary + task queue) from the start; RAG is
   the metric that will move.
3. Small shared maps first; World-scale maps are timeout-crown territory.
4. Ablations to plan: diary vs no-diary, enforced monitoring vs guidance-only,
   minimal vs full-map observations.

Build order:

1. Scaffold `src/openfront_mcp/` + `evals/` skeleton against vendored core.
2. Narration for overview, territory, neighbours, threats (minimal obs first).
3. Fixed scenarios + runner + PMR/RAG scorer.
4. Playbook AGENTS.md, then first model runs.

## 8. Summary

CivBench's contribution is a reusable shape, not just a Civ VI artefact:
MCP tools + narration layer + fixed scenarios + PMR/RAG metrics reveal that
agents under-monitor and under-execute. OpenFrontBench ports that shape onto
the vendored OpenFront core, starting small and headless, verifying in the
real client, with seeds fixed and spawn effects measured rather than averaged
away.

---

*Compiled 2026-09-10. CivBench details from docs/paper-summary.md; civ6-mcp
structure from ~/repos/civ6-mcp tree (commit dd20190); upstream pin v0.33.14
verified via git ls-remote and submodule status.*
