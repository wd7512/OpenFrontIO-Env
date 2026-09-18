# Cursor Lit Synthesis (DRAFT skeleton — T7)

**Status:** DRAFT skeleton. No LLM calls, no network; every synthesis row is
an explicit TODO placeholder until the T6 Q01–Q180 reports land. Grounded
only in `docs/lit-review-seed.md`, `docs/paper-summary.md`, and
`iter_1/proposal_v1.md` — no invented citations, no fake scores.

## Q01–Q180 coverage map

180 numbered questions (`iter_3/detailed_research_questions.md`), grouped per
`iter_3/grouped_research_questions.md`. Report status is pending throughout.

| Theme | Q ranges | Theme brief | Report status |
|---|---|---|---|
| Theme 1: Harness Engineering | Q01–Q06, Q61–Q66, Q151–Q156 | research-prompts/theme-1.md | TODO: pending T6 |
| Theme 2: MCP Tool Surfaces | Q07–Q12, Q73–Q78, Q91–Q96 | research-prompts/theme-2.md | TODO: pending T6 |
| Theme 3: RTS Dynamics | Q13–Q18, Q109–Q120 | research-prompts/theme-3.md | TODO: pending T6 |
| Theme 4: Metrics, PMR and RAG | Q19–Q30, Q127–Q132 | research-prompts/theme-4.md | TODO: pending T6 |
| Theme 5: Determinism and Replay | Q31–Q36, Q157–Q168 | research-prompts/theme-5.md | TODO: pending T6 |
| Theme 6: Observation and Narration | Q37–Q42, Q139–Q150 | research-prompts/theme-6.md | TODO: pending T6 |
| Theme 7: Memory and Coach | Q49–Q54, Q85–Q90, Q103–Q108 | research-prompts/theme-7.md | TODO: pending T6 |
| Theme 8: Baselines and Comparison | Q67–Q72, Q79–Q84, Q97–Q102, Q121–Q126, Q133–Q138 | research-prompts/theme-8.md | TODO: pending T6 |
| Theme 9: Safety and Provenance | Q55–Q60, Q169–Q174 | research-prompts/theme-9.md | TODO: pending T6 |
| Theme 10: Scaling and Evaluation Design | Q43–Q48, Q175–Q180 | research-prompts/theme-10.md | TODO: pending T6 |

## Consensus / conflicts table (placeholders)

| # | Claim (seed-grounded stub) | Standing | Source T6 Qs |
|---|---|---|---|
| C-01 | Sensorium-effect prior: PMR 1–2% transfers to RTS tick play | TODO: confirm or conflict | Q19–Q24, Q127–Q132 |
| C-02 | Reflection–action gap prior: RAG@10 48–66% predicts commitment failures | TODO: confirm or conflict | Q25–Q30 |
| C-03 | Outcome measures compress behavioural variance (report PMR/RAG alongside wins) | TODO: confirm or conflict | Q175–Q180 |
| X-01 | TODO: first genuine conflict goes here (no fabricated disagreements) | TODO | TBD |
| X-02 | TODO: second genuine conflict goes here | TODO | TBD |

## Metric guidance: PMR / RAG@10 at tick boundaries (grounded stubs)

From `proposal_v1.md` + `src/openfront_mcp/metrics.py` + task-spec:

- **PMR** = monitoring calls / non-infrastructure calls, ported from turn
  boundaries to paused 50-tick decision boundaries; exclude infra tools;
  split voluntary vs forced/automatic monitoring in logs.
- **RAG@K** = (Y + 0.5P) / commitments over the next-K decisions (K=10);
  no-diary or zero-commitment runs score N/A, never fabricated; unsupported
  free-text labels stay pending.
- Smoke slice (`plains-human-smoke`): PMR/RAG honestly `null` until
  strategic-query and commitment events exist.
- TODO: refine window-boundary rules (episode end, agent death, tick cap,
  budget stops) from Q25–Q30 reports.
- TODO: refine null-reporting and aggregation (paired tests, bootstrap CIs)
  from Q175–Q180 reports.

## Tool-surface recommendations: 21 MCP tools → growth path (DRAFT)

Current surface grounded in `src/openfront_mcp/server.py` (21 `@mcp.tool`
tools): game lifecycle (`start_smoke_game`, `start_1v1_game`,
`start_solo_game`), pure queries (`get_overview`, …), mutating actions
(expand, attack target/fraction, build city at tile, pass), `end_decision`
(advances exactly 50 sim ticks), plus diary/playbook and infra tools.

- TODO: distractor-discipline and catalogue recommendations from Q91–Q96
  (MCPAgentBench transfer) reports.
- TODO: narration/validation recommendations from Q73–Q78 (Vox Deorum)
  reports.
- Growth path (DRAFT, ordered): smoke (current) → 1v1 → solo → campaign,
  adding monitoring/commitment tooling only with versioned-playbook updates
  and full rescore re-runs. TODO: confirm ordering against Q43–Q48 reports.
