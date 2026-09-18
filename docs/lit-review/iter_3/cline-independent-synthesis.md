# Cline-Independent Synthesis (DRAFT skeleton — T7)

**Status:** DRAFT skeleton. Live synthesis is TODO: no LLM calls and no
network access were used to build this file, so every finding row below is an
explicit placeholder. Fill each `TODO` from the T6 per-question reports once
they land; do not invent findings.

**Scope:** independent pass over Q01–Q180 reports
(`iter_3/detailed_research_questions.md`, 180 numbered questions) plus the
per-theme briefs (`iter_3/research-prompts/theme-1.md … theme-10.md`).
Seed grounding only:
`docs/lit-review-seed.md` (12-work comparison matrix),
`docs/paper-summary.md` (CivBench PMR 1–2%, RAG@10 48–66%, 23 runs),
`docs/lit-review/iter_1/proposal_v1.md` (`{proposal}` context).

## Method (independent pass)

1. Read each T6 report for Q01–Q180 independently of the other two synthesis
   passes (cursor, kiro); record per-theme findings in §2 tables first, then
   compare.
2. Anchor every claim to one of: a seed-matrix work (§2 anchor column), a
   `references.bib` key, or an explicit `TODO (unverified — see lit-watch)`.
   No invented citations.
3. Log every disagreement with the other passes in §3
   (divergences-to-resolve), not silently.
4. Convert only consensus findings into tick-boundary design implications (§4).

**TODO (method execution):** T6 reports are pending — run the batch per
`docs/lit-review/README.md` dry-run entry point, then fill §2–§4.

## Per-theme findings (10 themes, placeholder rows)

Theme map grounded in `iter_3/grouped_research_questions.md`. Anchor column
references the seed-matrix work only; finding cells stay TODO.

### Theme 1: Harness Engineering (Q01–Q06, Q61–Q66, Q151–Q156)

| Q range | Seed-matrix anchor | Finding (TODO) |
|---|---|---|
| Q01–Q06 | CivBench VI (76 MCP tools, narration) | TODO: fill from T6 reports |
| Q61–Q66 | Pinned-engine precedent (OpenFrontIO v0.33.14) | TODO: fill from T6 reports |
| Q151–Q156 | Paused decision boundaries (50 sim ticks) | TODO: fill from T6 reports |

### Theme 2: MCP Tool Surfaces (Q07–Q12, Q73–Q78, Q91–Q96)

| Q range | Seed-matrix anchor | Finding (TODO) |
|---|---|---|
| Q07–Q12 | CivBench VI 76 tools / 13 categories | TODO: fill from T6 reports |
| Q73–Q78 | Vox Deorum (MCP-server exposure, delegation) | TODO: fill from T6 reports |
| Q91–Q96 | MCPAgentBench (180 tasks, distractors) | TODO: fill from T6 reports |

### Theme 3: RTS Dynamics (Q13–Q18, Q109–Q120)

| Q range | Seed-matrix anchor | Finding (TODO) |
|---|---|---|
| Q13–Q18 | CivRealm (FreeCiv + Gymnasium) | TODO: fill from T6 reports |
| Q109–Q114 | GameBench (9 games, strategy axes) | TODO: fill from T6 reports |
| Q115–Q120 | GTBench (10 game-theoretic tasks) | TODO: fill from T6 reports |

### Theme 4: Metrics, PMR and RAG (Q19–Q30, Q127–Q132)

| Q range | Seed-matrix anchor | Finding (TODO) |
|---|---|---|
| Q19–Q24 | CivBench VI PMR 1–2% (sensorium effect) | TODO: fill from T6 reports |
| Q25–Q30 | BALROG knowing–doing gap; CivBench RAG@10 48–66% | TODO: fill from T6 reports |
| Q127–Q132 | CivBench VI porting rules (turn → tick) | TODO: fill from T6 reports |

### Theme 5: Determinism and Replay (Q31–Q36, Q157–Q168)

| Q range | Seed-matrix anchor | Finding (TODO) |
|---|---|---|
| Q31–Q36 | SWE-bench held-out scoring → offline rescore | TODO: fill from T6 reports |
| Q157–Q162 | Trace + manifest rescore architecture | TODO: fill from T6 reports |
| Q163–Q168 | Pinned small assets (plains / big_plains) | TODO: fill from T6 reports |

### Theme 6: Observation and Narration (Q37–Q42, Q139–Q150)

| Q range | Seed-matrix anchor | Finding (TODO) |
|---|---|---|
| Q37–Q42 | CivBench 29-function narration layer | TODO: fill from T6 reports |
| Q139–Q144 | CivAgent digital player (RAG memory, lookahead) | TODO: fill from T6 reports |
| Q145–Q150 | Diary labelling (Haiku κ=0.879 precedent) | TODO: fill from T6 reports |

### Theme 7: Memory and Coach (Q49–Q54, Q85–Q90, Q103–Q108)

| Q range | Seed-matrix anchor | Finding (TODO) |
|---|---|---|
| Q49–Q54 | Five-field diary + versioned playbook | TODO: fill from T6 reports |
| Q85–Q90 | Vending-Bench (20M-token coherence drift) | TODO: fill from T6 reports |
| Q103–Q108 | CICERO (Science 2022, Diplomacy) | TODO: fill from T6 reports |

### Theme 8: Baselines and Comparison (Q67–Q72, Q79–Q84, Q97–Q102, Q121–Q126, Q133–Q138)

| Q range | Seed-matrix anchor | Finding (TODO) |
|---|---|---|
| Q67–Q72 | CivRealm (general-sum, changing player counts) | TODO: fill from T6 reports |
| Q79–Q84 | BALROG (milestones across 6 envs) | TODO: fill from T6 reports |
| Q97–Q102 | SWE-bench (single-turn contrast) | TODO: fill from T6 reports |
| Q121–Q126 | SMACv2 (SC2 micro, MARL wrapper) | TODO: fill from T6 reports |
| Q133–Q138 | CivBench V (307 multiplayer games) | TODO: fill from T6 reports |

### Theme 9: Safety and Provenance (Q55–Q60, Q169–Q174)

| Q range | Seed-matrix anchor | Finding (TODO) |
|---|---|---|
| Q55–Q60 | Proxy ledgers, credential hygiene | TODO: fill from T6 reports |
| Q169–Q174 | No-assist / fair-comparison rules | TODO: fill from T6 reports |

### Theme 10: Scaling and Evaluation Design (Q43–Q48, Q175–Q180)

| Q range | Seed-matrix anchor | Finding (TODO) |
|---|---|---|
| Q43–Q48 | Smoke → 1v1 → solo → campaign ladder | TODO: fill from T6 reports |
| Q175–Q180 | Bootstrap CIs, baselines, pre-registration | TODO: fill from T6 reports |

## Divergences-to-resolve (TODO list)

- DIVERGENCE-TBD-01 — TODO: record cline-vs-cursor disagreements after both
  passes complete; resolve by re-reading cited T6 reports, not by vote.
- DIVERGENCE-TBD-02 — TODO: record cline-vs-kiro disagreements on risks and
  experiment ordering the same way.
- DIVERGENCE-TBD-03 — TODO: any taxonomy-structure disagreement between
  passes must be stated explicitly (silent divergence is a defect).

## Design implications for the tick-boundary harness (grounded stubs)

Grounded in proposal_v1 + task-spec; behavioural claims stay TODO:

- Paused boundaries (queries never tick or consume RNG; `end_decision`
  advances exactly 50 sim ticks) — TODO: confirm against Q151–Q156 reports.
- PMR/RAG ported to tick granularity; honestly `null` in smoke until
  strategic queries and commitments exist — TODO: confirm metric guidance
  against Q19–Q30 reports.
- Deterministic replay via fixed seeds, paired spawn variants, manifest
  hashes, `trace.jsonl` + offline rescore — TODO: confirm against Q31–Q36
  and Q157–Q162 reports.
- Grid-RLE + narration observation under information scarcity — TODO:
  confirm against Q37–Q42 reports.
