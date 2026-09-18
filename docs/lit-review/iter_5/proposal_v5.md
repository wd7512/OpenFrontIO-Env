# OpenFrontBench Working Proposal v5 (DRAFT — T7)

**Status:** DRAFT. Current-working-proposal skeleton: tracks live state and
consumes proposal_v4 + the candidate-benchmark report + lit-watch digests as
they land. No LLM calls, no network; open items are explicit TODOs.

## Research questions (from proposal_v4)

- **RQ1 — Harness fidelity:** deterministic replay / tape / Grid-RLE.
  TODO: thresholds pending T6 Q31–Q36 / Q157–Q168 reports.
- **RQ2 — Agent capability:** PMR/RAG at paused 50-tick boundaries.
  TODO: priors and porting rules pending T6 Q19–Q30 / Q127–Q132 reports.
- **RQ3 — Scaling:** multi-human / diplomacy-free adversarial / combat,
  smoke → 1v1 → solo → campaign. TODO: gates pending Q43–Q48 reports.

## Principles (binding, from task-spec)

uv-only Python; TDD with red/green evidence; fixed seeds + repeatable
manifests; isolated per-run agent config; no shell/file/network tools for
the playing agent beyond game MCP; keyless CI with clear no-key failure;
honest `null` metrics in smoke; no fabricated LLM performance.

## State (what exists — grounded)

- Smoke harness + persistent Node worker + `vendor/OpenFrontIO @ v0.33.14`
  pin (see proposal_v4 §State; repo README smoke episode CLI).
- `src/openfront_mcp/server.py`: 21 MCP tools; metrics defined, `null` in
  smoke.
- T5 scaffold green (180 questions, 10 themes, 10 briefs); T6 dry-run
  runner present; T6 live reports TODO.
- Consumers: `AGENTS.md` (agent commands/rules) and repo `README.md`
  (setup, smoke CLI, limitations) are the downstream readers of this
  proposal — TODO: propagate frozen RQ thresholds there once v4 freezes.
  This proposal never rewrites the `iter_1` seed.

## Consumes

- `iter_4/proposal_v4.md` — roadmap RQs, principles, state (this file tracks
  its working copy).
- `iter_4/candidate-benchmark-report.md` — benchmark dossier; reserve slots
  scored only after verification.
- `lit-watch/` digests (T8) — new-reference intake; TODO: no digests yet,
  wire them here when T8 lands. Do not add new entries to
  `references.bib` except through lit-watch policy.

## Open items (TODO)

- TODO: fill RQ thresholds from the three `iter_3` syntheses after T6.
- TODO: first lit-watch digest link goes here.
- TODO: promotion checklist before this file leaves DRAFT (syntheses
  converged, divergences resolved, rescoring frozen).
