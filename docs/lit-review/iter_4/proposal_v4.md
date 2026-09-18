# OpenFrontBench Proposal v4 (DRAFT roadmap skeleton — T7)

**Status:** DRAFT skeleton. No LLM calls, no network. Roadmap shape only;
every evidence claim is a TODO pointing at the T6 Q01–Q180 reports and the
three `iter_3` syntheses. Grounded in `iter_1/proposal_v1.md`,
`docs/lit-review-seed.md`, `docs/paper-summary.md`,
`docs/openfrontbench-task-spec.md`, and `docs/pins.md`.

## Executive summary (TODO)

TODO: one-paragraph summary once the three syntheses converge. Working
thesis (stub, unverified): a pinned-engine RTS harness with paused
tick-boundary PMR/RAG fills the gap named in seed §6 — no MCP benchmark
over a pinned open-source RTS with production-tick replay.

## Research questions

- **RQ1 — Harness fidelity:** does the harness reproduce production ticks
  deterministically? Covers deterministic replay / tape (`trace.jsonl` +
  accepted-action replay), manifest verification (engine/map/config/playbook
  hashes), Grid-RLE observation fidelity, and fresh-process state-hash
  checks. Grounded in task-spec suites paragraph + pins
  (`vendor/OpenFrontIO @ v0.33.14`). TODO: success thresholds from Q31–Q36
  and Q157–Q168 reports.
- **RQ2 — Agent capability:** what do tick-boundary PMR/RAG reveal about
  LLM agents? Covers PMR/RAG at paused 50-tick decision boundaries
  (`end_decision` advances exactly 50 sim ticks; queries never tick or
  consume RNG), sensorium-effect and knowing–doing-gap priors from CivBench
  (PMR 1–2%, RAG@10 48–66%, 23 runs), diary/commitment ablation path.
  TODO: porting rules and priors from Q19–Q30 and Q127–Q132 reports.
- **RQ3 — Scaling:** how do findings hold from smoke to campaign? Covers
  multi-human / diplomacy-free adversarial / combat stages (smoke → 1v1 →
  solo → campaign), paired spawn variants + fixed seeds, cost modelling
  against the CivBench $31–229 / 2–8h per-run precedent. TODO: stage gates
  from Q43–Q48 and Q175–Q180 reports.

## Principles (binding, from task-spec)

- `uv`-only Python; TDD with red/green evidence; no live evals in CI.
- Fixed seeds + repeatable manifests; full tool request/result/status/tick/
  decision logs; evaluator-only state kept separate; offline rescore.
- Five-field diary + versioned playbook; isolated per-run agent config; no
  shell/file/network tools for the playing agent beyond game MCP.
- Keyless CI: missing key fails clearly before running; no fabricated LLM
  performance; no literal Civ VI numerical-reproduction claims; smoke
  metrics honestly `null`.

## State: what exists (grounded)

- Smoke harness: scripted controller (`start_smoke_game` → `get_overview`
  → `end_decision` ×N → `close_game`) over a real MCP stdio session; writes
  `result.json` + `trace.jsonl` + `manifest.json` (see repo README).
- Worker: persistent Node/TS JSONL worker over the pinned production core
  (`engine/`, built via `npm ci && npm run build`).
- Pins: `vendor/OpenFrontIO @ v0.33.14` detached-head, recorded in
  `docs/pins.md` and verified by the manifest at runtime.
- Metrics stubs: `PMR`/`RAG@10` defined in `src/openfront_mcp/metrics.py`;
  `null` in smoke (no strategic-query or commitment events yet).
- TODO: LLM controllers, multi-human games, and real metric scoring are not
  implemented yet — claimed by nothing in this proposal.

## Roadmap (TODO details)

1. Land T6 reports for Q01–Q180; fill the three syntheses.
2. Resolve divergences; freeze v4 RQ thresholds.
3. Advance E-01 smoke → E-02 1v1 → E-03 solo → E-04 campaign per the kiro
   backlog gates.
4. Lit-watch (T8) intake feeds `iter_4/candidate-benchmark-report.md`
   rescoring; proposal_v5 tracks the working state.

## Limitations (stub)

Sample-size honesty (CivBench's 23-run precedent), playbook confound, no
random/scripted baselines yet, contamination discipline for map seeds —
TODO: expand from Q97–Q102 and Q175–Q180 reports.
