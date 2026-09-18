# Kiro Lit Synthesis (DRAFT skeleton — T7)

**Status:** DRAFT skeleton. No LLM calls, no network; all synthesis cells are
explicit TODO placeholders until the T6 Q01–Q180 reports land. Grounded only
in `docs/lit-review-seed.md`, `docs/paper-summary.md`,
`docs/openfrontbench-task-spec.md`, `docs/pins.md`, and
`iter_1/proposal_v1.md` — no invented citations, no fake scores.

## Q01–Q180 + theme-brief synthesis (placeholders)

Per-theme briefs live in `iter_3/research-prompts/theme-1.md … theme-10.md`;
each row below is filled from the matching T6 reports when they exist.

| Theme | Brief | Q ranges | Synthesis (TODO) |
|---|---|---|---|
| Theme 1: Harness Engineering | theme-1.md | Q01–Q06, Q61–Q66, Q151–Q156 | TODO: pending T6 reports |
| Theme 2: MCP Tool Surfaces | theme-2.md | Q07–Q12, Q73–Q78, Q91–Q96 | TODO: pending T6 reports |
| Theme 3: RTS Dynamics | theme-3.md | Q13–Q18, Q109–Q120 | TODO: pending T6 reports |
| Theme 4: Metrics, PMR and RAG | theme-4.md | Q19–Q30, Q127–Q132 | TODO: pending T6 reports |
| Theme 5: Determinism and Replay | theme-5.md | Q31–Q36, Q157–Q168 | TODO: pending T6 reports |
| Theme 6: Observation and Narration | theme-6.md | Q37–Q42, Q139–Q150 | TODO: pending T6 reports |
| Theme 7: Memory and Coach | theme-7.md | Q49–Q54, Q85–Q90, Q103–Q108 | TODO: pending T6 reports |
| Theme 8: Baselines and Comparison | theme-8.md | Q67–Q72, Q79–Q84, Q97–Q102, Q121–Q126, Q133–Q138 | TODO: pending T6 reports |
| Theme 9: Safety and Provenance | theme-9.md | Q55–Q60, Q169–Q174 | TODO: pending T6 reports |
| Theme 10: Scaling and Evaluation Design | theme-10.md | Q43–Q48, Q175–Q180 | TODO: pending T6 reports |

## Risk / limitation register (grounded stubs + TODOs)

| # | Risk / limitation | Grounding | Mitigation (TODO) |
|---|---|---|---|
| R-01 | Smoke-only coverage: `plains-human-smoke` (one human, no opponents, no victory claims); PMR/RAG `null` | README + task-spec | TODO: honest coverage labels per Q43–Q48 reports |
| R-02 | No live-model validation in keyless CI; test doubles are not LLM evidence | task-spec | TODO: pre-registration standards per Q175–Q180 reports |
| R-03 | Diary-labelling reliability unproven for RTS free text (Haiku κ=0.879 is a Civ VI precedent, not a transfer result) | paper-summary §4–5, seed §7 | TODO: adjudication + IRR targets per Q145–Q150 reports |
| R-04 | Cost blow-up at campaign scale (CivBench $31–229 / 2–8h per run precedent) | paper-summary §5 | TODO: cost modelling per Q175–Q180 reports |
| R-05 | Spawn luck mistaken for skill without paired variants + fixed seeds | task-spec, seed §6 | TODO: spawn policy per Q163–Q168 reports |
| R-06 | TODO: further risks from T6 reports go here (none fabricated) | — | TODO |

## Experiment backlog: smoke → 1v1 → solo → campaign (DRAFT)

Stage names grounded in task-spec / README / server lifecycle tools
(`start_smoke_game`, `start_1v1_game`, `start_solo_game`). Entry/exit
criteria are TODO pending T6 + T8.

| Stage | Slice (grounded) | Exit criteria (TODO) |
|---|---|---|
| E-01 smoke | `plains-human-smoke`: scripted controller, pure queries + `end_decision` ×N, `null` metrics | TODO: deterministic-replay green + truthful evidence (see Q31–Q36, Q43–Q48 reports) |
| E-02 1v1 | Built-in/scripted opponent, same seeds + tick budgets | TODO: define from Q43–Q48 and Q121–Q126 reports |
| E-03 solo | No-opponent strategic depth, diary + commitments live, PMR/RAG scored | TODO: define from Q25–Q30 and Q49–Q54 reports |
| E-04 campaign | Multi-seed suite, offline rescore, aggregate reports | TODO: define from Q157–Q162 and Q175–Q180 reports |
| E-05 ablations | No-diary baselines, commitment aids, enforced monitoring schedules, stress scenario | TODO: define from Q103–Q108-adjacent and Q139–Q150 reports |

- TODO: order and gating between E-02/E-03 from the other two synthesis
  passes (record disagreements as divergences, do not smooth over).
